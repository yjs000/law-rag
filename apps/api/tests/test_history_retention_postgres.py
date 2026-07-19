import asyncio
import importlib.util
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import asyncpg
import pytest

DATABASE_URL = os.getenv("RETENTION_TEST_DATABASE_URL")
MIGRATION_PATH = (
    Path(__file__).parents[1] / "migrations" / "versions" / "0006_history_retention_job.py"
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="RETENTION_TEST_DATABASE_URL이 설정된 PostgreSQL 통합 gate에서만 실행",
)

CONVERSATION_ID = UUID("10000000-0000-0000-0000-000000000001")
USER_ID = UUID("90000000-0000-0000-0000-000000000001")
EXPIRED_TURN_ID = UUID("20000000-0000-0000-0000-000000000001")
NEW_TURN_ID = UUID("20000000-0000-0000-0000-000000000002")
EXPORT_ID = UUID("30000000-0000-0000-0000-000000000001")


def load_migration():
    spec = importlib.util.spec_from_file_location("history_retention_postgres", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


async def drop_database_objects(connection: asyncpg.Connection) -> None:
    await connection.execute(
        """
        DROP FUNCTION IF EXISTS public.purge_expired_question_history(timestamptz);
        DROP TABLE IF EXISTS public.history_retention_runs;
        DROP TABLE IF EXISTS public.checklist_exports;
        DROP TABLE IF EXISTS public.question_history;
        DROP TABLE IF EXISTS public.conversations;
        """
    )


async def reset_database(connection: asyncpg.Connection) -> None:
    await drop_database_objects(connection)
    await connection.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN
            CREATE ROLE service_role NOLOGIN BYPASSRLS;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
            CREATE ROLE anon NOLOGIN;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
            CREATE ROLE authenticated NOLOGIN;
          END IF;
        END $$;
        CREATE TABLE public.conversations (
          id uuid PRIMARY KEY,
          user_id uuid NOT NULL,
          title text NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          last_turn_id uuid NOT NULL,
          turn_count integer NOT NULL
        );
        CREATE TABLE public.question_history (
          id uuid PRIMARY KEY,
          user_id uuid NOT NULL,
          conversation_id uuid NOT NULL
            REFERENCES public.conversations(id) ON DELETE CASCADE,
          turn_index integer NOT NULL,
          request jsonb NOT NULL,
          response jsonb NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          expires_at timestamptz NOT NULL
        );
        CREATE TABLE public.checklist_exports (
          id uuid PRIMARY KEY,
          user_id uuid NOT NULL,
          history_id uuid NOT NULL
            REFERENCES public.question_history(id) ON DELETE CASCADE,
          export_format text NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )


async def apply_migration(connection: asyncpg.Connection):
    migration = load_migration()
    statements: list[str] = []
    migration.op.execute = statements.append
    migration.upgrade()
    for statement in statements:
        await connection.execute(statement)
    return migration


@pytest.mark.asyncio
async def test_retention_is_safe_during_concurrent_turn_save_and_has_strict_acl() -> None:
    assert DATABASE_URL is not None
    admin = await asyncpg.connect(DATABASE_URL)
    writer = await asyncpg.connect(DATABASE_URL)
    purge = await asyncpg.connect(DATABASE_URL)
    try:
        await reset_database(admin)
        migration = await apply_migration(admin)
        await admin.execute(
            """
            INSERT INTO public.conversations(
              id,user_id,title,updated_at,last_turn_id,turn_count
            ) VALUES($1,$2,'active','2025-01-01',$3,1)
            """,
            CONVERSATION_ID,
            USER_ID,
            EXPIRED_TURN_ID,
        )
        await admin.execute(
            """
            INSERT INTO public.question_history(
              id,user_id,conversation_id,turn_index,request,response,created_at,expires_at
            ) VALUES($1,$2,$3,1,'{}','{}','2025-01-01','2026-01-01')
            """,
            EXPIRED_TURN_ID,
            USER_ID,
            CONVERSATION_ID,
        )
        await admin.execute(
            """
            INSERT INTO public.checklist_exports(id,user_id,history_id,export_format)
            VALUES($1,$2,$3,'pdf')
            """,
            EXPORT_ID,
            USER_ID,
            EXPIRED_TURN_ID,
        )

        writer_tx = writer.transaction()
        await writer_tx.start()
        await writer.execute(
            """UPDATE public.conversations
            SET updated_at='2026-07-19',last_turn_id=$2,turn_count=turn_count+1
            WHERE id=$1""",
            CONVERSATION_ID,
            NEW_TURN_ID,
        )

        purge_task = asyncio.create_task(
            purge.fetchrow(
                "SELECT * FROM public.purge_expired_question_history($1)",
                datetime(2026, 7, 19, tzinfo=UTC),
            )
        )
        await asyncio.sleep(0.1)
        assert not purge_task.done(), "purge는 conversation writer lock을 기다려야 한다"

        await writer.execute(
            """INSERT INTO public.question_history(
              id,user_id,conversation_id,turn_index,request,response,created_at,expires_at
            ) VALUES($1,$2,$3,2,'{}','{}','2026-07-19','2027-07-19')""",
            NEW_TURN_ID,
            USER_ID,
            CONVERSATION_ID,
        )
        await writer_tx.commit()

        first = await asyncio.wait_for(purge_task, timeout=5)
        assert first is not None
        assert first["status"] == "succeeded"
        assert first["expired_history_deleted"] == 1
        assert first["checklist_exports_deleted"] == 1
        assert first["conversations_updated"] == 1
        assert first["conversations_deleted"] == 0

        remaining = await admin.fetchrow(
            """SELECT c.turn_count,c.last_turn_id,count(q.id)::integer turn_rows
            FROM public.conversations c
            JOIN public.question_history q ON q.conversation_id=c.id
            WHERE c.id=$1 GROUP BY c.id""",
            CONVERSATION_ID,
        )
        assert remaining is not None
        assert remaining["turn_count"] == 1
        assert remaining["last_turn_id"] == NEW_TURN_ID
        assert remaining["turn_rows"] == 1

        second = await admin.fetchrow(
            "SELECT * FROM public.purge_expired_question_history($1)",
            datetime(2026, 7, 19, tzinfo=UTC),
        )
        assert second is not None
        assert second["status"] == "succeeded"
        assert second["expired_history_deleted"] == 0
        assert second["checklist_exports_deleted"] == 0

        audit_count_before_null = await admin.fetchval(
            "SELECT count(*) FROM public.history_retention_runs"
        )
        with pytest.raises(asyncpg.PostgresError) as null_error:
            await admin.fetchrow(
                "SELECT * FROM public.purge_expired_question_history($1::timestamptz)",
                None,
            )
        assert null_error.value.sqlstate == "22023"
        assert await admin.fetchval(
            "SELECT count(*) FROM public.history_retention_runs"
        ) == audit_count_before_null

        failed = await admin.fetchrow(
            "SELECT * FROM public.purge_expired_question_history($1)",
            datetime.now(UTC) + timedelta(days=1),
        )
        assert failed is not None
        assert failed["status"] == "failed"
        assert failed["error_code"] == "22023"

        privileges = await admin.fetchrow(
            """SELECT
            has_function_privilege(
              'anon',
              'public.purge_expired_question_history(timestamptz)',
              'EXECUTE'
            ) anon_fn,
            has_function_privilege(
              'authenticated',
              'public.purge_expired_question_history(timestamptz)',
              'EXECUTE'
            ) auth_fn,
            has_table_privilege(
              'anon','public.history_retention_runs','SELECT'
            ) anon_table,
            has_table_privilege(
              'authenticated','public.history_retention_runs','SELECT'
            ) auth_table,
            has_sequence_privilege(
              'anon','public.history_retention_runs_id_seq','USAGE'
            ) anon_seq,
            has_sequence_privilege(
              'authenticated','public.history_retention_runs_id_seq','USAGE'
            ) auth_seq,
            has_function_privilege(
              'service_role',
              'public.purge_expired_question_history(timestamptz)',
              'EXECUTE'
            ) service_fn"""
        )
        assert privileges is not None
        assert dict(privileges) == {
            "anon_fn": False,
            "auth_fn": False,
            "anon_table": False,
            "auth_table": False,
            "anon_seq": False,
            "auth_seq": False,
            "service_fn": True,
        }

        advisory_tx = writer.transaction()
        await advisory_tx.start()
        await writer.execute(
            """SELECT pg_catalog.pg_advisory_xact_lock(
            pg_catalog.hashtextextended('purge_expired_question_history', 0))"""
        )
        serialized_task = asyncio.create_task(
            purge.fetchrow(
                "SELECT * FROM public.purge_expired_question_history($1)",
                datetime(2026, 7, 19, tzinfo=UTC),
            )
        )
        await asyncio.sleep(0.1)
        assert not serialized_task.done(), "겹친 retention 실행은 advisory lock을 기다려야 한다"
        await advisory_tx.commit()
        serialized = await asyncio.wait_for(serialized_task, timeout=5)
        assert serialized is not None
        assert serialized["status"] == "succeeded"

        downgrade_statements: list[str] = []
        migration.op.execute = downgrade_statements.append
        migration.downgrade()
        for statement in downgrade_statements:
            await admin.execute(statement)
        assert await admin.fetchval(
            "SELECT to_regprocedure('public.purge_expired_question_history(timestamptz)')"
        ) is None
        assert await admin.fetchval(
            "SELECT to_regclass('public.history_retention_runs')"
        ) is None
    finally:
        if not writer.is_closed() and writer.is_in_transaction():
            await writer.execute("ROLLBACK")
        await purge.close()
        await writer.close()
        await drop_database_objects(admin)
        await admin.close()


@pytest.mark.asyncio
async def test_retention_avoids_delete_deadlock_and_counts_actual_export_deletes() -> None:
    assert DATABASE_URL is not None
    admin = await asyncpg.connect(DATABASE_URL)
    user_delete = await asyncpg.connect(DATABASE_URL)
    purge = await asyncpg.connect(DATABASE_URL)
    delete_conversation_id = UUID("10000000-0000-0000-0000-000000000010")
    delete_turn_id = UUID("20000000-0000-0000-0000-000000000010")
    empty_conversation_id = UUID("10000000-0000-0000-0000-000000000020")
    empty_turn_id = UUID("20000000-0000-0000-0000-000000000020")
    export_conversation_id = UUID("10000000-0000-0000-0000-000000000030")
    export_turn_id = UUID("20000000-0000-0000-0000-000000000030")
    export_id = UUID("30000000-0000-0000-0000-000000000030")
    cutoff = datetime(2026, 7, 19, tzinfo=UTC)
    try:
        await reset_database(admin)
        await apply_migration(admin)
        await admin.execute(
            """INSERT INTO public.conversations(
              id,user_id,title,updated_at,last_turn_id,turn_count
            ) VALUES($1,$2,'delete-race','2025-01-01',$3,1)""",
            delete_conversation_id,
            USER_ID,
            delete_turn_id,
        )
        await admin.execute(
            """INSERT INTO public.question_history(
              id,user_id,conversation_id,turn_index,request,response,created_at,expires_at
            ) VALUES($1,$2,$3,1,'{}','{}','2025-01-01','2026-01-01')""",
            delete_turn_id,
            USER_ID,
            delete_conversation_id,
        )

        delete_tx = user_delete.transaction()
        await delete_tx.start()
        locked_id = await user_delete.fetchval(
            """SELECT c.id FROM public.conversations c
            JOIN public.question_history q ON q.conversation_id=c.id
            WHERE q.id=$1 AND q.user_id=$2 AND c.user_id=$2
            FOR UPDATE OF c""",
            delete_turn_id,
            USER_ID,
        )
        assert locked_id == delete_conversation_id
        purge_task = asyncio.create_task(
            purge.fetchrow(
                "SELECT * FROM public.purge_expired_question_history($1)", cutoff
            )
        )
        await asyncio.sleep(0.1)
        assert not purge_task.done(), "retention은 사용자 삭제의 conversation lock을 기다려야 한다"
        await user_delete.execute(
            "DELETE FROM public.question_history WHERE id=$1 AND user_id=$2",
            delete_turn_id,
            USER_ID,
        )
        await user_delete.execute(
            "DELETE FROM public.conversations WHERE id=$1 AND user_id=$2",
            delete_conversation_id,
            USER_ID,
        )
        await delete_tx.commit()
        delete_race_result = await asyncio.wait_for(purge_task, timeout=5)
        assert delete_race_result is not None
        assert delete_race_result["status"] == "succeeded"
        assert delete_race_result["error_code"] is None

        await admin.execute(
            """INSERT INTO public.conversations(
              id,user_id,title,updated_at,last_turn_id,turn_count
            ) VALUES($1,$2,'empty','2025-01-01',$3,1)""",
            empty_conversation_id,
            USER_ID,
            empty_turn_id,
        )
        await admin.execute(
            """INSERT INTO public.question_history(
              id,user_id,conversation_id,turn_index,request,response,created_at,expires_at
            ) VALUES($1,$2,$3,1,'{}','{}','2025-01-01','2026-01-01')""",
            empty_turn_id,
            USER_ID,
            empty_conversation_id,
        )
        empty_result = await admin.fetchrow(
            "SELECT * FROM public.purge_expired_question_history($1)", cutoff
        )
        assert empty_result is not None
        assert empty_result["expired_history_deleted"] == 1
        assert empty_result["conversations_deleted"] == 1
        assert await admin.fetchval(
            "SELECT count(*) FROM public.conversations WHERE id=$1",
            empty_conversation_id,
        ) == 0

        await admin.execute(
            """INSERT INTO public.conversations(
              id,user_id,title,updated_at,last_turn_id,turn_count
            ) VALUES($1,$2,'export-race','2025-01-01',$3,1)""",
            export_conversation_id,
            USER_ID,
            export_turn_id,
        )
        await admin.execute(
            """INSERT INTO public.question_history(
              id,user_id,conversation_id,turn_index,request,response,created_at,expires_at
            ) VALUES($1,$2,$3,1,'{}','{}','2025-01-01','2026-01-01')""",
            export_turn_id,
            USER_ID,
            export_conversation_id,
        )
        await admin.execute(
            """INSERT INTO public.checklist_exports(id,user_id,history_id,export_format)
            VALUES($1,$2,$3,'pdf')""",
            export_id,
            USER_ID,
            export_turn_id,
        )
        export_tx = user_delete.transaction()
        await export_tx.start()
        await user_delete.execute(
            "DELETE FROM public.checklist_exports WHERE id=$1", export_id
        )
        export_purge_task = asyncio.create_task(
            purge.fetchrow(
                "SELECT * FROM public.purge_expired_question_history($1)", cutoff
            )
        )
        await asyncio.sleep(0.1)
        assert not export_purge_task.done(), "retention export 삭제는 사용자 DELETE 완료를 기다린다"
        await export_tx.commit()
        export_result = await asyncio.wait_for(export_purge_task, timeout=5)
        assert export_result is not None
        assert export_result["status"] == "succeeded"
        assert export_result["expired_history_deleted"] == 1
        assert export_result["checklist_exports_deleted"] == 0
        assert export_result["conversations_deleted"] == 1
    finally:
        if not user_delete.is_closed() and user_delete.is_in_transaction():
            await user_delete.execute("ROLLBACK")
        await purge.close()
        await user_delete.close()
        await drop_database_objects(admin)
        await admin.close()

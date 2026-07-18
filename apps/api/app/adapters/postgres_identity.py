from __future__ import annotations

import json
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.adapters.supabase_auth import SupabaseIdentity
from app.domain.schemas import (
    ConversationSummary,
    MockUser,
    QuestionHistoryEntry,
    QuestionRequest,
    QuestionResponse,
)


class ConsentRequiredError(Exception):
    pass


class PostgresIdentityRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def ensure_profile(
        self,
        identity: SupabaseIdentity,
        terms_version: str | None = None,
        privacy_version: str | None = None,
    ) -> MockUser:
        async with self.engine.begin() as connection:
            exists = (
                (
                    await connection.execute(
                        text(
                            """SELECT id,email,display_name,created_at,
                        EXISTS(SELECT 1 FROM user_consents
                          WHERE user_id=user_profiles.id
                            AND (:terms='' OR terms_version=:terms)
                            AND (:privacy='' OR privacy_version=:privacy)) AS consented
                        FROM user_profiles
                        WHERE auth_user_id=:auth_user_id"""
                        ),
                        {
                            "auth_user_id": identity.auth_user_id,
                            "terms": terms_version or "",
                            "privacy": privacy_version or "",
                        },
                    )
                )
                .mappings()
                .first()
            )
            if exists is None:
                if not terms_version or not privacy_version:
                    raise ConsentRequiredError
                row = (
                    (
                        await connection.execute(
                            text(
                                """INSERT INTO user_profiles(
                        auth_user_id,email,display_name,auth_provider,created_at)
                        VALUES(:auth_user_id,:email,:name,'google',:created_at)
                        RETURNING id,email,display_name,created_at"""
                            ),
                            {
                                "auth_user_id": identity.auth_user_id,
                                "email": identity.email,
                                "name": identity.display_name,
                                "created_at": identity.created_at,
                            },
                        )
                    )
                    .mappings()
                    .one()
                )
                await connection.execute(
                    text(
                        """INSERT INTO user_consents(user_id,terms_version,privacy_version)
                        VALUES(:id,:terms,:privacy)"""
                    ),
                    {"id": row["id"], "terms": terms_version, "privacy": privacy_version},
                )
            else:
                if not exists["consented"]:
                    if not terms_version or not privacy_version:
                        raise ConsentRequiredError
                    await connection.execute(
                        text(
                            """INSERT INTO user_consents(user_id,terms_version,privacy_version)
                            VALUES(:id,:terms,:privacy)"""
                        ),
                        {"id": exists["id"], "terms": terms_version, "privacy": privacy_version},
                    )
                if (
                    exists["email"] != identity.email
                    or exists["display_name"] != identity.display_name
                ):
                    await connection.execute(
                        text(
                            """UPDATE user_profiles
                            SET email=:email,display_name=:name,updated_at=now()
                            WHERE id=:id"""
                        ),
                        {
                            "id": exists["id"],
                            "email": identity.email,
                            "name": identity.display_name,
                        },
                    )
                row = {
                    **exists,
                    "email": identity.email,
                    "display_name": identity.display_name,
                }
        return MockUser(
            id=row["id"],
            email=row["email"],
            display_name=row["display_name"],
            created_at=row["created_at"],
        )

    async def auth_user_id(self, user_id: UUID) -> UUID:
        async with self.engine.connect() as connection:
            return (
                await connection.execute(
                    text("SELECT auth_user_id FROM user_profiles WHERE id=:id"),
                    {"id": user_id},
                )
            ).scalar_one()

    async def save_question(
        self,
        user_id: UUID,
        request: QuestionRequest,
        response: QuestionResponse,
        diagnostics: dict[str, object] | None = None,
    ) -> UUID:
        conversation_id = request.conversation_id or uuid4()
        turn_id = UUID(response.request_id)
        async with self.engine.begin() as connection:
            if request.conversation_id is None:
                await connection.execute(
                    text(
                        """INSERT INTO conversations(
                        id,user_id,title,last_turn_id,turn_count)
                        VALUES(:id,:user_id,:title,:turn_id,1)"""
                    ),
                    {
                        "id": conversation_id,
                        "user_id": user_id,
                        "title": " ".join(request.question.split())[:120],
                        "turn_id": turn_id,
                    },
                )
                turn_index = 1
            else:
                turn_index = (
                    await connection.execute(
                        text(
                            """UPDATE conversations
                            SET updated_at=now(),last_turn_id=:turn_id,turn_count=turn_count+1
                            WHERE id=:id AND user_id=:user_id RETURNING turn_count"""
                        ),
                        {
                            "id": conversation_id,
                            "user_id": user_id,
                            "turn_id": turn_id,
                        },
                    )
                ).scalar_one_or_none()
                if turn_index is None:
                    raise ValueError("대화를 찾을 수 없습니다")
            response.conversation_id = conversation_id
            await connection.execute(
                text(
                    """INSERT INTO question_history(
                    id,user_id,conversation_id,turn_index,request,response,diagnostics,expires_at)
                    VALUES(:id,:user_id,:conversation_id,:turn_index,
                    CAST(:request AS jsonb),CAST(:response AS jsonb),CAST(:diagnostics AS jsonb),
                    now()+interval '1 year')"""
                ),
                {
                    "id": turn_id,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "turn_index": turn_index,
                    "request": json.dumps(request.model_dump(mode="json"), ensure_ascii=False),
                    "response": json.dumps(response.model_dump(mode="json"), ensure_ascii=False),
                    "diagnostics": json.dumps(diagnostics or {}, ensure_ascii=False),
                },
            )
        return conversation_id

    async def list_conversations(
        self,
        user_id: UUID,
        limit: int,
        cursor: tuple[datetime, UUID] | None = None,
    ) -> tuple[list[ConversationSummary], bool]:
        params: dict[str, object] = {"user_id": user_id, "fetch_limit": limit + 1}
        cursor_clause = ""
        if cursor:
            cursor_clause = "AND (c.updated_at,c.id)<(:cursor_time,:cursor_id)"
            params.update(cursor_time=cursor[0], cursor_id=cursor[1])
        async with self.engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        f"""SELECT id,title,created_at,updated_at,turn_count,last_turn_id
                        FROM conversations c WHERE user_id=:user_id {cursor_clause}
                          AND EXISTS(SELECT 1 FROM question_history q
                            WHERE q.conversation_id=c.id AND q.expires_at>now())
                        ORDER BY c.updated_at DESC,c.id DESC LIMIT :fetch_limit"""
                    ),
                    params,
                )
            ).mappings().all()
        items = [ConversationSummary.model_validate(dict(row)) for row in rows[:limit]]
        return items, len(rows) > limit

    async def list_conversation_turns(
        self,
        conversation_id: UUID,
        user_id: UUID,
        limit: int,
        cursor: tuple[int, UUID] | None = None,
    ) -> tuple[list[QuestionHistoryEntry], bool] | None:
        params: dict[str, object] = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "fetch_limit": limit + 1,
        }
        cursor_clause = ""
        if cursor:
            cursor_clause = "AND (q.turn_index,q.id)<(:cursor_index,:cursor_id)"
            params.update(cursor_index=cursor[0], cursor_id=cursor[1])
        async with self.engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        f"""SELECT q.id,q.user_id,q.request,q.response,q.created_at,q.expires_at,
                        q.conversation_id,q.turn_index
                        FROM question_history q JOIN conversations c ON c.id=q.conversation_id
                        WHERE q.conversation_id=:conversation_id AND q.user_id=:user_id
                          AND c.user_id=:user_id AND q.expires_at>now() {cursor_clause}
                        ORDER BY q.turn_index DESC,q.id DESC LIMIT :fetch_limit"""
                    ),
                    params,
                )
            ).mappings().all()
        if not rows:
            async with self.engine.connect() as connection:
                owned = (
                    await connection.execute(
                        text(
                            """SELECT 1 FROM conversations
                            WHERE id=:conversation_id AND user_id=:user_id"""
                        ),
                        {"conversation_id": conversation_id, "user_id": user_id},
                    )
                ).scalar_one_or_none()
            if owned is None:
                return None
        items = [QuestionHistoryEntry.model_validate(dict(row)) for row in rows[:limit]]
        return items, len(rows) > limit

    async def delete_conversation(self, conversation_id: UUID, user_id: UUID) -> bool:
        async with self.engine.begin() as connection:
            result = await connection.execute(
                text("DELETE FROM conversations WHERE id=:id AND user_id=:user_id"),
                {"id": conversation_id, "user_id": user_id},
            )
        return bool(result.rowcount)

    async def list_history(self, user_id: UUID) -> list[QuestionHistoryEntry]:
        async with self.engine.connect() as connection:
            rows = (
                (
                    await connection.execute(
                        text(
                            """SELECT id,user_id,request,response,created_at,expires_at,
                        conversation_id,turn_index
                        FROM question_history
                        WHERE user_id=:user_id AND expires_at>now()
                        ORDER BY created_at DESC"""
                        ),
                        {"user_id": user_id},
                    )
                )
                .mappings()
                .all()
            )
        return [QuestionHistoryEntry.model_validate(dict(row)) for row in rows]

    async def get_history(self, history_id: UUID, user_id: UUID) -> QuestionHistoryEntry | None:
        async with self.engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            """SELECT id,user_id,request,response,created_at,expires_at,
                        conversation_id,turn_index
                        FROM question_history
                        WHERE id=:id AND user_id=:user_id AND expires_at>now()"""
                        ),
                        {"id": history_id, "user_id": user_id},
                    )
                )
                .mappings()
                .first()
            )
        return QuestionHistoryEntry.model_validate(dict(row)) if row else None

    async def delete_history(self, history_id: UUID, user_id: UUID) -> bool:
        async with self.engine.begin() as connection:
            result = await connection.execute(
                text(
                    """WITH deleted AS (
                      DELETE FROM question_history WHERE id=:id AND user_id=:user_id
                      RETURNING conversation_id
                    )
                    SELECT conversation_id FROM deleted"""
                ),
                {"id": history_id, "user_id": user_id},
            )
            conversation_id = result.scalar_one_or_none()
            if conversation_id is not None:
                await connection.execute(
                    text(
                        """DELETE FROM conversations c WHERE c.id=:conversation_id
                        AND c.user_id=:user_id AND NOT EXISTS(
                          SELECT 1 FROM question_history q WHERE q.conversation_id=c.id)
                        """
                    ),
                    {"conversation_id": conversation_id, "user_id": user_id},
                )
                await connection.execute(
                    text(
                        """UPDATE conversations c SET
                        turn_count=(SELECT count(*) FROM question_history q
                          WHERE q.conversation_id=c.id),
                        updated_at=(SELECT max(created_at) FROM question_history q
                          WHERE q.conversation_id=c.id),
                        last_turn_id=(SELECT id FROM question_history q WHERE q.conversation_id=c.id
                          ORDER BY created_at DESC,id DESC LIMIT 1)
                        WHERE c.id=:conversation_id AND c.user_id=:user_id"""
                    ),
                    {"conversation_id": conversation_id, "user_id": user_id},
                )
        return conversation_id is not None

    async def record_export(self, user_id: UUID, history_id: UUID, export_format: str) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    """INSERT INTO checklist_exports(user_id,history_id,export_format)
                    VALUES(:user_id,:history_id,:format)"""
                ),
                {"user_id": user_id, "history_id": history_id, "format": export_format},
            )

    async def consume_quota(self, user_id: UUID, day: date, kind: str, limit: int) -> bool:
        async with self.engine.begin() as connection:
            count = (
                await connection.execute(
                    text(
                        """INSERT INTO account_usage(user_id,usage_date,kind,count)
                        VALUES(:user_id,:day,:kind,1)
                        ON CONFLICT(user_id,usage_date,kind) DO UPDATE
                        SET count=account_usage.count+1 WHERE account_usage.count<:limit
                        RETURNING count"""
                    ),
                    {"user_id": user_id, "day": day, "kind": kind, "limit": limit},
                )
            ).scalar_one_or_none()
        return count is not None

    async def delete_account_data(self, user_id: UUID) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM user_profiles WHERE id=:id"), {"id": user_id}
            )

    async def purge_expired(self) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(text("DELETE FROM question_history WHERE expires_at<=now()"))
            await connection.execute(
                text(
                    """UPDATE conversations c SET
                    turn_count=(SELECT count(*) FROM question_history q
                      WHERE q.conversation_id=c.id),
                    updated_at=(SELECT max(created_at) FROM question_history q
                      WHERE q.conversation_id=c.id),
                    last_turn_id=(SELECT id FROM question_history q WHERE q.conversation_id=c.id
                      ORDER BY created_at DESC,id DESC LIMIT 1)
                    WHERE EXISTS(SELECT 1 FROM question_history q WHERE q.conversation_id=c.id)"""
                )
            )
            await connection.execute(
                text(
                    """DELETE FROM conversations c WHERE NOT EXISTS(
                    SELECT 1 FROM question_history q WHERE q.conversation_id=c.id)"""
                )
            )

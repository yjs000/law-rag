"""1년 만료 질문 이력 정리 함수와 비민감 실행 감사.

Revision ID: 0006

이 migration은 scheduler를 설치하거나 등록하지 않는다. 운영 예약은 별도 승인과
pg_cron extension 가용성 확인 뒤 수행한다.
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# 0002에서 정의한 연쇄 삭제를 이 migration의 정리 계약으로 명시한다.
CASCADE_CONTRACT = (
    "checklist_exports.history_id REFERENCES question_history(id) ON DELETE CASCADE"
)

PURGE_FUNCTION = """
CREATE OR REPLACE FUNCTION public.purge_expired_question_history(
  p_cutoff_at timestamptz DEFAULT now()
) RETURNS SETOF public.history_retention_runs
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  v_run_id bigint;
  v_history_deleted integer := 0;
  v_exports_deleted integer := 0;
  v_conversations_updated integer := 0;
  v_conversations_deleted integer := 0;
  v_conversation_ids uuid[] := ARRAY[]::uuid[];
  v_error_code text;
BEGIN
  -- 두 scheduler 호출이 겹쳐도 한 transaction만 정리하도록 직렬화한다.
  PERFORM pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('purge_expired_question_history', 0)
  );

  INSERT INTO public.history_retention_runs(cutoff_at)
  VALUES(p_cutoff_at)
  RETURNING id INTO v_run_id;

  BEGIN
    IF p_cutoff_at > pg_catalog.clock_timestamp() THEN
      RAISE EXCEPTION 'retention cutoff cannot be in the future'
        USING ERRCODE = '22023';
    END IF;

    -- export 집계 뒤 새 FK 참조가 추가되어 감사 수가 어긋나는 경합을 막는다.
    PERFORM 1 FROM public.question_history
    WHERE expires_at <= p_cutoff_at
    FOR UPDATE;

    SELECT count(*)::integer INTO v_exports_deleted
    FROM public.checklist_exports e
    JOIN public.question_history q ON q.id=e.history_id
    WHERE q.expires_at <= p_cutoff_at;

    WITH deleted AS (
      DELETE FROM public.question_history
      WHERE expires_at <= p_cutoff_at
      RETURNING conversation_id
    )
    SELECT count(*)::integer,
           COALESCE(array_agg(DISTINCT conversation_id), ARRAY[]::uuid[])
    INTO v_history_deleted, v_conversation_ids
    FROM deleted;

    -- 질문 삭제가 checklist_exports를 ON DELETE CASCADE로 함께 정리한다.
    UPDATE public.conversations c SET
      turn_count=(SELECT count(*) FROM public.question_history q
        WHERE q.conversation_id=c.id),
      updated_at=(SELECT max(created_at) FROM public.question_history q
        WHERE q.conversation_id=c.id),
      last_turn_id=(SELECT id FROM public.question_history q WHERE q.conversation_id=c.id
        ORDER BY created_at DESC,id DESC LIMIT 1)
    WHERE c.id=ANY(v_conversation_ids)
      AND EXISTS(SELECT 1 FROM public.question_history q WHERE q.conversation_id=c.id);
    GET DIAGNOSTICS v_conversations_updated = ROW_COUNT;

    DELETE FROM public.conversations c
    WHERE c.id=ANY(v_conversation_ids)
      AND NOT EXISTS(SELECT 1 FROM public.question_history q WHERE q.conversation_id=c.id);
    GET DIAGNOSTICS v_conversations_deleted = ROW_COUNT;

    UPDATE public.history_retention_runs SET
      finished_at=pg_catalog.clock_timestamp(),
      status='succeeded',
      expired_history_deleted=v_history_deleted,
      checklist_exports_deleted=v_exports_deleted,
      conversations_updated=v_conversations_updated,
      conversations_deleted=v_conversations_deleted
    WHERE id=v_run_id;
  EXCEPTION WHEN OTHERS THEN
    -- 중첩 block의 데이터 변경은 rollback되고 SQLSTATE만 비민감 감사 정보로 남긴다.
    v_error_code := SQLSTATE;
    UPDATE public.history_retention_runs SET
      finished_at=pg_catalog.clock_timestamp(),
      status='failed',
      error_code=v_error_code
    WHERE id=v_run_id;
  END;

  RETURN QUERY SELECT * FROM public.history_retention_runs WHERE id=v_run_id;
END
$$
"""


def upgrade() -> None:
    statements = [
        """CREATE TABLE public.history_retention_runs (
          id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
          finished_at timestamptz,
          cutoff_at timestamptz NOT NULL,
          status text NOT NULL DEFAULT 'running'
            CHECK(status IN ('running','succeeded','failed')),
          expired_history_deleted integer NOT NULL DEFAULT 0
            CHECK(expired_history_deleted>=0),
          checklist_exports_deleted integer NOT NULL DEFAULT 0
            CHECK(checklist_exports_deleted>=0),
          conversations_updated integer NOT NULL DEFAULT 0
            CHECK(conversations_updated>=0),
          conversations_deleted integer NOT NULL DEFAULT 0
            CHECK(conversations_deleted>=0),
          error_code text,
          CHECK((status='running' AND finished_at IS NULL)
             OR (status IN ('succeeded','failed') AND finished_at IS NOT NULL)),
          CHECK((status='failed') OR error_code IS NULL)
        )""",
        "CREATE INDEX history_retention_runs_started_at ON public.history_retention_runs(started_at DESC)",
        "ALTER TABLE public.history_retention_runs ENABLE ROW LEVEL SECURITY",
        "REVOKE ALL ON TABLE public.history_retention_runs FROM PUBLIC",
        "GRANT SELECT ON TABLE public.history_retention_runs TO service_role",
        PURGE_FUNCTION,
        "REVOKE ALL ON FUNCTION public.purge_expired_question_history(timestamptz) FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION public.purge_expired_question_history(timestamptz) TO service_role",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    statements = [
        "DROP FUNCTION IF EXISTS public.purge_expired_question_history(timestamptz)",
        "DROP TABLE IF EXISTS public.history_retention_runs",
    ]
    for statement in statements:
        op.execute(statement)

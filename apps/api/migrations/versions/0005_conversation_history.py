"""대화 단위 질문 이력과 커서 페이지네이션 기반 인덱스.

Revision ID: 0005
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        """CREATE TABLE conversations (
          id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
          title text NOT NULL CHECK(char_length(title) BETWEEN 1 AND 120),
          created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
          last_turn_id uuid NOT NULL, turn_count integer NOT NULL CHECK(turn_count>0),
          UNIQUE(id,user_id)
        )""",
        "ALTER TABLE question_history ADD COLUMN conversation_id uuid",
        "ALTER TABLE question_history ADD COLUMN turn_index integer",
        """INSERT INTO conversations(id,user_id,title,created_at,updated_at,last_turn_id,turn_count)
        SELECT id,user_id,left(regexp_replace(request->>'question','\\s+',' ','g'),120),
               created_at,created_at,id,1 FROM question_history""",
        "UPDATE question_history SET conversation_id=id,turn_index=1",
        "ALTER TABLE question_history ALTER COLUMN conversation_id SET NOT NULL",
        "ALTER TABLE question_history ALTER COLUMN turn_index SET NOT NULL",
        "ALTER TABLE question_history ADD CONSTRAINT question_history_turn_index_positive CHECK(turn_index>0)",
        """ALTER TABLE question_history ADD CONSTRAINT question_history_conversation_owner_fk
        FOREIGN KEY(conversation_id,user_id) REFERENCES conversations(id,user_id) ON DELETE CASCADE""",
        "ALTER TABLE question_history ADD CONSTRAINT question_history_conversation_turn_unique UNIQUE(conversation_id,turn_index)",
        "CREATE INDEX conversations_user_updated_id ON conversations(user_id,updated_at DESC,id DESC)",
        "CREATE INDEX question_history_conversation_turn_id ON question_history(conversation_id,turn_index DESC,id DESC)",
        "ALTER TABLE conversations ENABLE ROW LEVEL SECURITY",
        """CREATE POLICY own_conversations ON conversations FOR ALL
        USING (user_id IN (SELECT id FROM user_profiles WHERE auth_user_id=auth.uid()))
        WITH CHECK (user_id IN (SELECT id FROM user_profiles WHERE auth_user_id=auth.uid()))""",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    statements = [
        "DROP POLICY IF EXISTS own_conversations ON conversations",
        "DROP INDEX IF EXISTS question_history_conversation_turn_id",
        "ALTER TABLE question_history DROP CONSTRAINT IF EXISTS question_history_conversation_turn_unique",
        "ALTER TABLE question_history DROP CONSTRAINT IF EXISTS question_history_conversation_owner_fk",
        "ALTER TABLE question_history DROP CONSTRAINT IF EXISTS question_history_turn_index_positive",
        "ALTER TABLE question_history DROP COLUMN IF EXISTS turn_index",
        "ALTER TABLE question_history DROP COLUMN IF EXISTS conversation_id",
        "DROP TABLE IF EXISTS conversations",
    ]
    for statement in statements:
        op.execute(statement)

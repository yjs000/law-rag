"""Supabase 사용자, 동의, 질문 이력과 계정별 사용량.

Revision ID: 0002
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        """CREATE TABLE user_profiles (
          id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
          email text NOT NULL, display_name text NOT NULL, auth_provider text NOT NULL CHECK(auth_provider='google'),
          created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
        )""",
        """CREATE TABLE user_consents (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
          terms_version text NOT NULL, privacy_version text NOT NULL, consented_at timestamptz NOT NULL DEFAULT now()
        )""",
        """CREATE TABLE question_history (
          id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
          request jsonb NOT NULL, response jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
          expires_at timestamptz NOT NULL
        )""",
        "CREATE INDEX question_history_user_created ON question_history(user_id,created_at DESC)",
        "CREATE INDEX question_history_expiry ON question_history(expires_at)",
        """CREATE TABLE checklist_exports (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
          history_id uuid NOT NULL REFERENCES question_history(id) ON DELETE CASCADE,
          export_format text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
        )""",
        """CREATE TABLE account_usage (
          user_id uuid NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
          usage_date date NOT NULL, kind text NOT NULL, count integer NOT NULL CHECK(count>0),
          PRIMARY KEY(user_id,usage_date,kind)
        )""",
        "ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE user_consents ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE question_history ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE checklist_exports ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE account_usage ENABLE ROW LEVEL SECURITY",
        "CREATE POLICY own_profile ON user_profiles FOR SELECT USING (id=auth.uid())",
        "CREATE POLICY own_consents ON user_consents FOR SELECT USING (user_id=auth.uid())",
        "CREATE POLICY own_history ON question_history FOR ALL USING (user_id=auth.uid()) WITH CHECK (user_id=auth.uid())",
        "CREATE POLICY own_exports ON checklist_exports FOR ALL USING (user_id=auth.uid()) WITH CHECK (user_id=auth.uid())",
        "CREATE POLICY own_usage ON account_usage FOR SELECT USING (user_id=auth.uid())",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS account_usage,checklist_exports,question_history,user_consents,user_profiles CASCADE")

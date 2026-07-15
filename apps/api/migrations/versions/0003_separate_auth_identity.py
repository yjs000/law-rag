"""Supabase provider subject와 내부 사용자 ID 분리.

Revision ID: 0003
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        "ALTER TABLE user_profiles ADD COLUMN auth_user_id uuid",
        "UPDATE user_profiles SET auth_user_id=id",
        "ALTER TABLE user_profiles ALTER COLUMN auth_user_id SET NOT NULL",
        "ALTER TABLE user_profiles ADD CONSTRAINT user_profiles_auth_user_id_key UNIQUE(auth_user_id)",
        "ALTER TABLE user_profiles DROP CONSTRAINT user_profiles_id_fkey",
        "ALTER TABLE user_profiles ADD CONSTRAINT user_profiles_auth_user_id_fkey FOREIGN KEY(auth_user_id) REFERENCES auth.users(id) ON DELETE CASCADE",
        "ALTER TABLE user_profiles ALTER COLUMN id SET DEFAULT gen_random_uuid()",
        "DROP POLICY own_profile ON user_profiles",
        "DROP POLICY own_consents ON user_consents",
        "DROP POLICY own_history ON question_history",
        "DROP POLICY own_exports ON checklist_exports",
        "DROP POLICY own_usage ON account_usage",
        "CREATE POLICY own_profile ON user_profiles FOR SELECT USING (auth_user_id=auth.uid())",
        "CREATE POLICY own_consents ON user_consents FOR SELECT USING (user_id IN (SELECT id FROM user_profiles WHERE auth_user_id=auth.uid()))",
        "CREATE POLICY own_history ON question_history FOR ALL USING (user_id IN (SELECT id FROM user_profiles WHERE auth_user_id=auth.uid())) WITH CHECK (user_id IN (SELECT id FROM user_profiles WHERE auth_user_id=auth.uid()))",
        "CREATE POLICY own_exports ON checklist_exports FOR ALL USING (user_id IN (SELECT id FROM user_profiles WHERE auth_user_id=auth.uid())) WITH CHECK (user_id IN (SELECT id FROM user_profiles WHERE auth_user_id=auth.uid()))",
        "CREATE POLICY own_usage ON account_usage FOR SELECT USING (user_id IN (SELECT id FROM user_profiles WHERE auth_user_id=auth.uid()))",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("0003 separates provider identity and is intentionally irreversible")

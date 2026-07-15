from __future__ import annotations

import json
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.adapters.supabase_auth import SupabaseIdentity
from app.domain.schemas import MockUser, QuestionHistoryEntry, QuestionRequest, QuestionResponse


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
                            """SELECT id,email,display_name,created_at FROM user_profiles
                        WHERE auth_user_id=:auth_user_id"""
                        ),
                        {"auth_user_id": identity.auth_user_id},
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
                await connection.execute(
                    text(
                        """UPDATE user_profiles SET email=:email,display_name=:name,updated_at=now()
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
        self, user_id: UUID, request: QuestionRequest, response: QuestionResponse
    ) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    """INSERT INTO question_history(id,user_id,request,response,expires_at)
                    VALUES(:id,:user_id,CAST(:request AS jsonb),CAST(:response AS jsonb),
                    now()+interval '1 year')"""
                ),
                {
                    "id": UUID(response.request_id),
                    "user_id": user_id,
                    "request": json.dumps(request.model_dump(mode="json"), ensure_ascii=False),
                    "response": json.dumps(response.model_dump(mode="json"), ensure_ascii=False),
                },
            )

    async def list_history(self, user_id: UUID) -> list[QuestionHistoryEntry]:
        await self.purge_expired()
        async with self.engine.connect() as connection:
            rows = (
                (
                    await connection.execute(
                        text(
                            """SELECT id,user_id,request,response,created_at,expires_at
                        FROM question_history WHERE user_id=:user_id ORDER BY created_at DESC"""
                        ),
                        {"user_id": user_id},
                    )
                )
                .mappings()
                .all()
            )
        return [QuestionHistoryEntry.model_validate(dict(row)) for row in rows]

    async def get_history(self, history_id: UUID, user_id: UUID) -> QuestionHistoryEntry | None:
        await self.purge_expired()
        async with self.engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            """SELECT id,user_id,request,response,created_at,expires_at
                        FROM question_history WHERE id=:id AND user_id=:user_id"""
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
                text("DELETE FROM question_history WHERE id=:id AND user_id=:user_id"),
                {"id": history_id, "user_id": user_id},
            )
        return bool(result.rowcount)

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

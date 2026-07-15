from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import httpx


@dataclass(frozen=True)
class SupabaseIdentity:
    auth_user_id: UUID
    email: str
    display_name: str
    created_at: datetime


class SupabaseAuthError(Exception):
    pass


class SupabaseAuth:
    def __init__(
        self,
        url: str,
        secret_key: str,
        timeout: float = 30,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.secret_key = secret_key
        self.timeout = timeout
        self.transport = transport

    async def verify_user(self, token: str) -> SupabaseIdentity:
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.get(
                f"{self.url}/auth/v1/user",
                headers={"apikey": self.secret_key, "Authorization": f"Bearer {token}"},
            )
        if response.status_code != 200:
            raise SupabaseAuthError("invalid user token")
        payload = response.json()
        metadata = payload.get("user_metadata") or {}
        email = payload.get("email")
        if not email:
            raise SupabaseAuthError("verified user has no email")
        return SupabaseIdentity(
            auth_user_id=UUID(payload["id"]),
            email=email.casefold(),
            display_name=(metadata.get("full_name") or metadata.get("name") or email).strip()[:80],
            created_at=datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00"))
            if payload.get("created_at")
            else datetime.now(UTC),
        )

    async def delete_user(self, user_id: UUID) -> None:
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.delete(
                f"{self.url}/auth/v1/admin/users/{user_id}",
                headers={
                    "apikey": self.secret_key,
                    "Authorization": f"Bearer {self.secret_key}",
                },
            )
        if response.status_code not in {200, 204, 404}:
            raise SupabaseAuthError("could not delete auth user")

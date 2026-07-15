from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from app.adapters.supabase_auth import SupabaseAuth, SupabaseAuthError


@pytest.mark.asyncio
async def test_verified_supabase_user_is_mapped_without_exposing_secret() -> None:
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(
            200,
            json={
                "id": "4cc78d08-f2bd-490b-9619-b9ec35b6672c",
                "email": "User@Example.com",
                "created_at": "2026-07-15T00:00:00Z",
                "user_metadata": {"full_name": "테스트 사용자"},
            },
        )

    auth = SupabaseAuth(
        "https://project.supabase.co",
        "sb_secret_test",
        transport=httpx.MockTransport(handler),
    )
    user = await auth.verify_user("user-jwt")

    assert user.auth_user_id == UUID("4cc78d08-f2bd-490b-9619-b9ec35b6672c")
    assert user.email == "user@example.com"
    assert user.display_name == "테스트 사용자"
    assert user.created_at == datetime(2026, 7, 15, tzinfo=UTC)
    assert seen_headers["authorization"] == "Bearer user-jwt"
    assert seen_headers["apikey"] == "sb_secret_test"


@pytest.mark.asyncio
async def test_invalid_supabase_token_is_rejected() -> None:
    auth = SupabaseAuth(
        "https://project.supabase.co",
        "sb_secret_test",
        transport=httpx.MockTransport(lambda _: httpx.Response(401)),
    )
    with pytest.raises(SupabaseAuthError):
        await auth.verify_user("invalid")


@pytest.mark.asyncio
async def test_missing_email_is_rejected_at_the_boundary() -> None:
    auth = SupabaseAuth(
        "https://project.supabase.co",
        "sb_secret_test",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={"id": "4cc78d08-f2bd-490b-9619-b9ec35b6672c"},
            )
        ),
    )
    with pytest.raises(SupabaseAuthError):
        await auth.verify_user("user-jwt")

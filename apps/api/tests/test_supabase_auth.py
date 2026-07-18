from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from app.adapters.supabase_auth import (
    SupabaseAuth,
    SupabaseAuthError,
    SupabaseAuthUnavailableError,
)


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
async def test_http_client_is_reused_and_can_be_closed() -> None:
    request_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            json={
                "id": "4cc78d08-f2bd-490b-9619-b9ec35b6672c",
                "email": "user@example.com",
            },
        )

    auth = SupabaseAuth(
        "https://project.supabase.co",
        "sb_secret_test",
        transport=httpx.MockTransport(handler),
    )

    await auth.verify_user("first-token")
    client = auth._client
    await auth.verify_user("second-token")

    assert request_count == 2
    assert auth._client is client
    await auth.aclose()
    assert auth._client is None


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"id": "not-a-uuid", "email": "user@example.com"},
        {
            "id": "4cc78d08-f2bd-490b-9619-b9ec35b6672c",
            "email": "user@example.com",
            "created_at": "not-a-date",
        },
        {
            "id": "4cc78d08-f2bd-490b-9619-b9ec35b6672c",
            "email": "user@example.com",
            "user_metadata": {"full_name": 123},
        },
        [],
    ],
)
async def test_malformed_verified_user_payload_is_rejected(payload: object) -> None:
    auth = SupabaseAuth(
        "https://project.supabase.co",
        "sb_secret_test",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    )

    with pytest.raises(SupabaseAuthError):
        await auth.verify_user("user-jwt")


@pytest.mark.asyncio
async def test_auth_provider_network_failure_is_distinct_from_invalid_token() -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    auth = SupabaseAuth(
        "https://project.supabase.co",
        "sb_secret_test",
        transport=httpx.MockTransport(unavailable),
    )

    with pytest.raises(SupabaseAuthUnavailableError):
        await auth.verify_user("user-jwt")


@pytest.mark.asyncio
async def test_delete_user_network_failure_is_a_controlled_auth_error() -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    auth = SupabaseAuth(
        "https://project.supabase.co",
        "sb_secret_test",
        transport=httpx.MockTransport(unavailable),
    )

    with pytest.raises(SupabaseAuthError):
        await auth.delete_user(UUID("4cc78d08-f2bd-490b-9619-b9ec35b6672c"))

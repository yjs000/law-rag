"""Shared transport dependencies that preserve ``app.main`` test seams."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Header, HTTPException

from app.adapters.mock_identity import identity_repository
from app.adapters.postgres_identity import ConsentRequiredError
from app.adapters.supabase_auth import SupabaseAuthError, SupabaseAuthUnavailableError
from app.domain.schemas import MockUser, QuestionRequest, QuestionResponse
from app.observability import emit_question_outcome


def main_module() -> Any:
    """Resolve the composition entry lazily to retain monkeypatch compatibility."""

    import app.main as main

    return main


def _require_mock_auth() -> None:
    if main_module().settings.environment == "production":
        raise HTTPException(status_code=404, detail="찾을 수 없습니다")


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    scheme, separator, token = authorization.partition(" ")
    token = token.strip()
    if (
        not separator
        or scheme.casefold() != "bearer"
        or not token
        or any(char.isspace() for char in token)
    ):
        raise HTTPException(status_code=401, detail="유효하지 않은 인증 헤더입니다")
    return token


async def _optional_user(authorization: str | None) -> MockUser | None:
    main = main_module()
    if authorization is None:
        return None
    token = _bearer_token(authorization)
    if main.supabase_auth and main.postgres_identity:
        try:
            return await main.postgres_identity.ensure_profile(
                await main.supabase_auth.verify_user(token)
            )
        except ConsentRequiredError as exc:
            raise HTTPException(status_code=409, detail="회원가입 동의가 필요합니다.") from exc
        except SupabaseAuthUnavailableError as exc:
            raise HTTPException(
                status_code=503, detail="인증 서비스를 일시적으로 사용할 수 없습니다."
            ) from exc
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=401, detail="유효하지 않은 인증 세션입니다.") from exc
    _require_mock_auth()
    user = identity_repository.user_for_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 세션입니다")
    return user


async def _authenticated_user(
    authorization: Annotated[str | None, Header()] = None,
    x_terms_version: Annotated[str | None, Header()] = None,
    x_privacy_version: Annotated[str | None, Header()] = None,
) -> MockUser:
    main = main_module()
    if main.supabase_auth and main.postgres_identity:
        try:
            user = await main.supabase_auth.verify_user(_bearer_token(authorization))
            if (x_terms_version is None) != (x_privacy_version is None):
                raise ConsentRequiredError
            if x_terms_version is not None and (
                x_terms_version != main.settings.terms_version
                or x_privacy_version != main.settings.privacy_version
            ):
                raise ConsentRequiredError
            return await main.postgres_identity.ensure_profile(
                user, x_terms_version, x_privacy_version
            )
        except ConsentRequiredError as exc:
            raise HTTPException(status_code=409, detail="회원가입 동의가 필요합니다.") from exc
        except SupabaseAuthUnavailableError as exc:
            raise HTTPException(
                status_code=503, detail="인증 서비스를 일시적으로 사용할 수 없습니다."
            ) from exc
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=401, detail="유효하지 않은 인증 세션입니다.") from exc
    _require_mock_auth()
    user = identity_repository.user_for_token(_bearer_token(authorization))
    if user is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 세션입니다")
    return user


async def _save_if_authenticated(
    user: MockUser | None,
    payload: QuestionRequest,
    response: QuestionResponse,
    diagnostics: dict[str, object] | None = None,
) -> QuestionResponse:
    main = main_module()
    emit_question_outcome(
        response.request_id, response.mode, fallback_reason=response.fallback_reason
    )
    if diagnostics is not None:
        diagnostics["outcome"] = {
            "mode": response.mode,
            "result_status": response.result_status,
            "no_results_reason": response.no_results_reason,
            "fallback_reason": (
                response.fallback_reason.value if response.fallback_reason else None
            ),
            "sections_count": len(response.sections),
            "citations_count": len(response.citations),
        }
    if user is None:
        return response
    stored_payload = payload.model_copy(update={"conversation_context": []})
    try:
        if main.postgres_identity:
            await main.postgres_identity.save_question(
                user.id, stored_payload, response, diagnostics=diagnostics
            )
        else:
            identity_repository.save_question(user.id, stored_payload, response)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다") from exc
    return response

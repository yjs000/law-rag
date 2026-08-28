"""Version 1 account, authentication, history and export HTTP transport."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from app.adapters.mock_identity import identity_repository
from app.adapters.supabase_auth import SupabaseAuthError, SupabaseAuthUnavailableError
from app.api.dependencies import (
    _authenticated_user,
    _bearer_token,
    _require_mock_auth,
    main_module,
)
from app.application.checklist_exports import render_csv, render_markdown, render_pdf
from app.domain.auth_schemas import MockGoogleLoginRequest, MockLoginResponse
from app.domain.schemas import (
    ChecklistDocument,
    ChecklistExportFormat,
    ConversationPage,
    ConversationTurnPage,
    MockUser,
    QuestionHistoryEntry,
)

router = APIRouter()


@router.post("/v1/auth/mock/google", response_model=MockLoginResponse)
async def mock_google_login(payload: MockGoogleLoginRequest) -> MockLoginResponse:
    """비운영 환경에서 목업 Google 로그인 세션을 발급한다."""
    _require_mock_auth()
    token, user = identity_repository.login_google(payload.email, payload.display_name)
    return MockLoginResponse(access_token=token, user=user)


@router.get("/v1/auth/me", response_model=MockUser)
async def current_user(
    user: Annotated[MockUser, Depends(_authenticated_user)],
) -> MockUser:
    """현재 인증된 사용자를 반환한다."""
    return user


@router.post("/v1/auth/logout", status_code=204)
async def logout(authorization: Annotated[str | None, Header()] = None) -> Response:
    """현재 인증 세션을 검증하고 목업 세션을 종료한다."""
    if main_module().supabase_auth and main_module().postgres_identity:
        try:
            await main_module().supabase_auth.verify_user(_bearer_token(authorization))
        except SupabaseAuthUnavailableError as exc:
            raise HTTPException(
                status_code=503, detail="인증 서비스를 일시적으로 사용할 수 없습니다."
            ) from exc
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=401, detail="유효하지 않은 인증 세션입니다.") from exc
        return Response(status_code=204)
    _require_mock_auth()
    token = _bearer_token(authorization)
    if identity_repository.user_for_token(token) is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 세션입니다")
    identity_repository.logout(token)
    return Response(status_code=204)


@router.delete("/v1/account", status_code=204)
async def delete_account(
    user: Annotated[MockUser, Depends(_authenticated_user)],
) -> Response:
    """인증된 사용자의 계정과 연결된 데이터를 삭제한다."""
    if main_module().supabase_auth and main_module().postgres_identity:
        try:
            auth_user_id = await main_module().postgres_identity.auth_user_id(user.id)
            await main_module().supabase_auth.delete_user(auth_user_id)
            await main_module().postgres_identity.delete_account_data(user.id)
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=502, detail="계정 삭제를 완료하지 못했습니다.") from exc
        return Response(status_code=204)
    identity_repository.delete_account(user.id)
    return Response(status_code=204)


@router.get("/v1/questions/history", response_model=list[QuestionHistoryEntry])
async def question_history(
    user: Annotated[MockUser, Depends(_authenticated_user)],
) -> list[QuestionHistoryEntry]:
    """인증된 사용자가 소유한 질문 이력을 반환한다."""
    if main_module().postgres_identity:
        return await main_module().postgres_identity.list_history(user.id)
    return identity_repository.list_history(user.id)


@router.get("/v1/conversations", response_model=ConversationPage)
async def conversations(
    user: Annotated[MockUser, Depends(_authenticated_user)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
) -> ConversationPage:
    """인증된 사용자의 대화를 페이지 단위로 반환한다."""
    decoded = _decode_conversation_cursor(cursor) if cursor else None
    items, has_more = (
        await main_module().postgres_identity.list_conversations(user.id, limit, decoded)
        if main_module().postgres_identity
        else identity_repository.list_conversations(user.id, limit, decoded)
    )
    next_cursor = (
        _encode_cursor("conversation", items[-1].updated_at.isoformat(), items[-1].id)
        if has_more and items
        else None
    )
    return ConversationPage(items=items, has_more=has_more, next_cursor=next_cursor)


@router.get("/v1/conversations/{conversation_id}/turns", response_model=ConversationTurnPage)
async def conversation_turns(
    conversation_id: UUID,
    user: Annotated[MockUser, Depends(_authenticated_user)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
) -> ConversationTurnPage:
    """인증된 사용자가 소유한 대화의 턴을 페이지 단위로 반환한다."""
    decoded = _decode_turn_cursor(cursor) if cursor else None
    result = (
        await main_module().postgres_identity.list_conversation_turns(
            conversation_id, user.id, limit, decoded
        )
        if main_module().postgres_identity
        else identity_repository.list_conversation_turns(conversation_id, user.id, limit, decoded)
    )
    if result is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
    items, has_more = result
    next_cursor = (
        _encode_cursor("turn", items[-1].turn_index or 0, items[-1].id)
        if has_more and items
        else None
    )
    return ConversationTurnPage(items=items, has_more=has_more, next_cursor=next_cursor)


@router.delete("/v1/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    user: Annotated[MockUser, Depends(_authenticated_user)],
) -> Response:
    """인증된 사용자가 소유한 대화와 포함된 턴을 삭제한다."""
    deleted = (
        await main_module().postgres_identity.delete_conversation(conversation_id, user.id)
        if main_module().postgres_identity
        else identity_repository.delete_conversation(conversation_id, user.id)
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
    return Response(status_code=204)


@router.get("/v1/questions/history/{history_id}", response_model=QuestionHistoryEntry)
async def question_history_detail(
    history_id: UUID, user: Annotated[MockUser, Depends(_authenticated_user)]
) -> QuestionHistoryEntry:
    """인증된 사용자가 소유한 질문 이력 항목을 반환한다."""
    return await _owned_history(history_id, user)


@router.delete("/v1/questions/history/{history_id}", status_code=204)
async def delete_question_history(
    history_id: UUID, user: Annotated[MockUser, Depends(_authenticated_user)]
) -> Response:
    """인증된 사용자가 소유한 질문 이력 항목을 삭제한다."""
    deleted = (
        await main_module().postgres_identity.delete_history(history_id, user.id)
        if main_module().postgres_identity
        else identity_repository.delete_history(history_id, user.id)
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="질문 이력을 찾을 수 없습니다")
    return Response(status_code=204)


@router.get("/v1/questions/history/{history_id}/checklist")
async def export_checklist(
    history_id: UUID,
    user: Annotated[MockUser, Depends(_authenticated_user)],
    export_format: Annotated[ChecklistExportFormat, Query(alias="format")] = (
        ChecklistExportFormat.MARKDOWN
    ),
) -> StreamingResponse:
    """인증된 사용자의 질문 이력에서 체크리스트 파일을 내보낸다."""
    entry = await _owned_history(history_id, user)
    document = ChecklistDocument(
        title="에너지 법령 체크리스트",
        as_of_date=entry.request.as_of_date,
        project_stage=entry.request.project_stage,
        items=entry.response.checklist,
        citations=entry.response.citations,
    )
    renderers = {
        ChecklistExportFormat.MARKDOWN: (render_markdown, "text/markdown; charset=utf-8"),
        ChecklistExportFormat.CSV: (render_csv, "text/csv; charset=utf-8"),
        ChecklistExportFormat.PDF: (render_pdf, "application/pdf"),
    }
    renderer, media_type = renderers[export_format]
    content = renderer(document)
    if main_module().postgres_identity:
        await main_module().postgres_identity.record_export(
            user.id, history_id, export_format.value
        )
    else:
        identity_repository.record_export(user.id, history_id, export_format.value)
    filename = f"checklist-{history_id}.{export_format.value}"
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _encode_cursor(kind: str, value: str | int, item_id: UUID) -> str:
    payload = json.dumps(
        {"v": 1, "kind": kind, "value": value, "id": str(item_id)},
        separators=(",", ":"),
    )
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str, kind: str) -> tuple[object, UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        if payload != {"v": 1, "kind": kind, "value": payload["value"], "id": payload["id"]}:
            raise ValueError
        return payload["value"], UUID(payload["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="유효하지 않은 페이지 커서입니다") from exc


def _decode_conversation_cursor(cursor: str) -> tuple[datetime, UUID]:
    value, item_id = _decode_cursor(cursor, "conversation")
    try:
        return datetime.fromisoformat(str(value)), item_id
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="유효하지 않은 페이지 커서입니다") from exc


def _decode_turn_cursor(cursor: str) -> tuple[int, UUID]:
    value, item_id = _decode_cursor(cursor, "turn")
    if not isinstance(value, int) or value < 1:
        raise HTTPException(status_code=400, detail="유효하지 않은 페이지 커서입니다")
    return value, item_id


async def _owned_history(history_id: UUID, user: MockUser) -> QuestionHistoryEntry:
    entry = (
        await main_module().postgres_identity.get_history(history_id, user.id)
        if main_module().postgres_identity
        else identity_repository.get_history(history_id, user.id)
    )
    if entry is None:
        # 존재 여부를 숨겨 다른 사용자의 ID 열거를 막는다.
        raise HTTPException(status_code=404, detail="질문 이력을 찾을 수 없습니다")
    return entry

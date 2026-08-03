"""Canonical identities for the Experiment D layperson question bank."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

APPROVAL_SCOPE_FIELDS = (
    "id",
    "question",
    "scenario_family_id",
    "intent",
    "technology",
    "question_style",
)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def question_scope_payload(case: Mapping[str, object]) -> dict[str, str] | None:
    """Return the fields a user approves as one question's text and scope."""

    payload: dict[str, str] = {}
    for field in APPROVAL_SCOPE_FIELDS:
        value = case.get(field)
        if not isinstance(value, str) or not value:
            return None
        payload[field] = value
    return payload


def question_scope_sha256(case: Mapping[str, object]) -> str | None:
    payload = question_scope_payload(case)
    return _canonical_sha256(payload) if payload is not None else None


def question_scope_set_sha256(cases: Sequence[Mapping[str, object]]) -> str | None:
    payloads: list[dict[str, str]] = []
    for case in cases:
        payload = question_scope_payload(case)
        if payload is None:
            return None
        payloads.append(payload)
    return _canonical_sha256(payloads)


__all__ = [
    "APPROVAL_SCOPE_FIELDS",
    "question_scope_payload",
    "question_scope_set_sha256",
    "question_scope_sha256",
]

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from law_rag_core.corpus_update_bundle import (
    embedding_text_sha256 as _embedding_text_sha256,
)
from law_rag_core.corpus_update_bundle import (
    legal_provision_v1_text,
)


@dataclass(frozen=True, slots=True)
class EmbeddingProfile:
    key: str
    provider: str
    model: str
    native_dimensions: int
    stored_dimensions: int
    document_input_type: Literal["passage"]
    query_input_type: Literal["query"]
    truncation: str
    normalization: str
    text_template_version: str
    profile_version: str


NVIDIA_NEMOTRON_512_PROFILE = EmbeddingProfile(
    key="nvidia-nemotron-3-embed-1b-512-v1",
    provider="nvidia",
    model="nvidia/nemotron-3-embed-1b",
    native_dimensions=2048,
    stored_dimensions=512,
    document_input_type="passage",
    query_input_type="query",
    truncation="first_512",
    normalization="l2",
    text_template_version="legal-provision-v1",
    profile_version="1",
)


def legal_provision_embedding_text(
    *, document_title: str, path: str, heading: str | None, content: str
) -> str:
    """Build the versioned passage text used for provision embeddings."""
    return legal_provision_v1_text(
        document_title=document_title,
        path=path,
        heading=heading,
        content=content,
    )


def embedding_text_sha256(text: str) -> str:
    return _embedding_text_sha256(text)

"""Pure source-change detection and LlamaIndex node transformations."""

from collections.abc import Callable
from typing import Any

from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.schema import TextNode

from law_rag_llamaindex.passage import (
    ProvisionRecord,
    build_node_metadata,
    build_passage_text,
    compute_source_text_sha256,
)

PipelineFactory = Callable[..., Any]


def changed_provision_ids(
    provisions: list[ProvisionRecord], existing_hashes: dict[str, str]
) -> set[str]:
    """Return new or changed provisions by comparing canonical passage hashes."""

    return {
        record["provision_id"]
        for record in provisions
        if existing_hashes.get(record["provision_id"])
        != compute_source_text_sha256(build_passage_text(record))
    }


def build_nodes(provisions: list[ProvisionRecord]) -> list[TextNode]:
    """Build deterministic LlamaIndex nodes with citation metadata."""

    nodes = []
    for record in provisions:
        passage_text = build_passage_text(record)
        source_text_sha256 = compute_source_text_sha256(passage_text)
        nodes.append(
            TextNode(
                id_=record["provision_id"],
                text=passage_text,
                metadata=build_node_metadata(record, source_text_sha256),
            )
        )
    return nodes


def run_generation_pipeline(
    provisions: list[ProvisionRecord],
    embedder: Any,
    *,
    pipeline_factory: PipelineFactory | None = None,
) -> list[TextNode]:
    """Run ``build nodes → LlamaIndex IngestionPipeline`` without a store side effect."""

    factory = pipeline_factory or IngestionPipeline
    pipeline = factory(transformations=[embedder])
    return list(pipeline.run(nodes=build_nodes(provisions)))

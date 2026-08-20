"""v2 검색용 NVIDIA query embedder를 구성한다."""

from llama_index.embeddings.nvidia import NVIDIAEmbedding

from law_rag_llamaindex.config import Settings


def build_embedder(settings: Settings) -> NVIDIAEmbedding:
    """설정된 모델과 NVIDIA 자격 증명으로 embedder를 생성한다."""
    return NVIDIAEmbedding(
        model=settings.nvidia_embedding_model,
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        truncate="END",
    )

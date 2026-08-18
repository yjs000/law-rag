from llama_index.embeddings.nvidia import NVIDIAEmbedding

from law_rag_llamaindex.config import Settings


def build_embedder(settings: Settings) -> NVIDIAEmbedding:
    return NVIDIAEmbedding(
        model=settings.nvidia_embedding_model,
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        truncate="END",
    )

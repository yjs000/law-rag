from law_rag_llamaindex.config import Settings
from law_rag_llamaindex.embedding import build_embedder


def test_build_embedder_uses_configured_model_and_endpoint():
    settings = Settings(
        _env_file=None,
        nvidia_api_key="test-key",
        nvidia_base_url="https://integrate.api.nvidia.com/v1",
        nvidia_embedding_model="nvidia/nemotron-3-embed-1b",
    )
    embedder = build_embedder(settings)
    assert embedder.model == "nvidia/nemotron-3-embed-1b"
    assert embedder.truncate == "END"

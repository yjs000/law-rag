from law_rag_llamaindex.active_index import ActiveGenerationIndexProvider
from law_rag_llamaindex.generations import GenerationCatalog


class _Repository:
    def __init__(self, catalog: GenerationCatalog) -> None:
        self.catalog = catalog

    async def active(self):
        return self.catalog.active()


async def test_active_index_cache_replaces_only_after_pointer_switch() -> None:
    catalog = GenerationCatalog()
    first = catalog.start("a" * 64, "b" * 64)
    catalog.verify(first.id, source_count=1, node_count=1)
    catalog.publish(first.id)
    stores: list[object] = []

    def create_store(generation):
        store = {"generation_id": generation.id}
        stores.append(store)
        return store

    provider = ActiveGenerationIndexProvider(
        _Repository(catalog), create_store, lambda store: store
    )

    pinned_first = await provider.active()
    again = await provider.active()

    second = catalog.start("c" * 64, "b" * 64)
    catalog.verify(second.id, source_count=1, node_count=1)
    catalog.publish(second.id)
    pinned_second = await provider.active()

    assert pinned_first.generation.id == first.id
    assert again is pinned_first
    assert pinned_second.generation.id == second.id
    assert pinned_second is not pinned_first
    assert len(stores) == 2

from unittest.mock import MagicMock

import pytest

from core.rag import VectorStore
from core.schemas import Document


def make_store(existing_count: int) -> VectorStore:
    store = VectorStore.__new__(VectorStore)
    store.embedding_client = MagicMock()
    store.index = MagicMock()
    store.get_stats = MagicMock(return_value={"total_vector_count": existing_count})
    return store


def make_documents(count: int) -> list[Document]:
    return [
        Document(content=f"document {i}", metadata={"position": i})
        for i in range(count)
    ]


@pytest.mark.parametrize("existing_count", [3, 5])
def test_add_documents_skips_when_index_covers_all_documents(existing_count):
    store = make_store(existing_count)

    store.add_documents(make_documents(3))

    store.embedding_client.embed_texts.assert_not_called()
    store.index.upsert.assert_not_called()


def test_add_documents_upserts_only_missing_documents():
    store = make_store(100)
    documents = make_documents(103)
    store.embedding_client.embed_texts.return_value = [[0.1], [0.2], [0.3]]

    store.add_documents(documents)

    store.embedding_client.embed_texts.assert_called_once_with(
        ["document 100", "document 101", "document 102"]
    )
    store.index.upsert.assert_called_once()
    vectors = store.index.upsert.call_args.kwargs["vectors"]
    assert [vector["id"].split("_", 2)[:2] for vector in vectors] == [
        ["doc", "100"],
        ["doc", "101"],
        ["doc", "102"],
    ]
    assert [vector["metadata"]["position"] for vector in vectors] == [100, 101, 102]


def test_add_documents_uploads_empty_index_in_batches():
    store = make_store(0)
    documents = make_documents(205)
    store.embedding_client.embed_texts.return_value = [[float(i)] for i in range(205)]

    store.add_documents(documents)

    store.embedding_client.embed_texts.assert_called_once_with(
        [document.content for document in documents]
    )
    assert store.index.upsert.call_count == 3
    batches = [call.kwargs["vectors"] for call in store.index.upsert.call_args_list]
    assert [len(batch) for batch in batches] == [100, 100, 5]

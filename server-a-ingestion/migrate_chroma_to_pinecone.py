"""One-time migration of the old local Chroma collection to Pinecone.

The Pinecone index must already exist with the same vector dimension as Chroma.
"""

import os
from pathlib import Path

import chromadb
from pinecone import Pinecone

from pipeline import pinecone_id


CHROMA_DIR = Path(os.getenv("CHROMA_DIR", Path(__file__).resolve().parent.parent / "shared" / "legal" / "chroma"))
NAMESPACE = os.getenv("PINECONE_NAMESPACE", "legal_units")


def main() -> None:
    api_key = os.getenv("PINECONE_API_KEY", "").strip()
    index_name = os.getenv("PINECONE_INDEX_NAME", "").strip()
    index_host = os.getenv("PINECONE_INDEX_HOST", "").strip()
    if not api_key or not index_name:
        raise RuntimeError("Cần đặt PINECONE_API_KEY và PINECONE_INDEX_NAME")

    collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_collection("legal_units")
    total = collection.count()
    if not total:
        raise RuntimeError(f"Collection Chroma rỗng: {CHROMA_DIR}")

    pc = Pinecone(api_key=api_key)
    index = pc.Index(host=index_host) if index_host else pc.Index(index_name)
    batch_size = 100
    for start in range(0, total, batch_size):
        rows = collection.get(
            limit=batch_size,
            offset=start,
            include=["embeddings", "documents", "metadatas"],
        )
        vectors = []
        for unit_id, embedding, document, metadata in zip(
            rows["ids"], rows["embeddings"], rows["documents"], rows["metadatas"]
        ):
            vectors.append(
                {
                    "id": pinecone_id(unit_id),
                    "values": embedding,
                    "metadata": {**(metadata or {}), "text": document, "original_unit_id": unit_id},
                }
            )
        index.upsert(vectors=vectors, namespace=NAMESPACE)
        print(f"[MIGRATE] {min(start + batch_size, total)}/{total}")


if __name__ == "__main__":
    main()

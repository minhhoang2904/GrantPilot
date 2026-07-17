"""Smoke test semantic retrieval trên collection legal_units."""

import argparse

from pipeline import CHROMA_DIR, FptClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Câu hỏi tiếng Việt")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("Thiếu chromadb. Chạy: pip install -r requirements.txt") from exc

    collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_collection("legal_units")
    query_embedding = FptClient().embed([args.query])[0]
    result = collection.query(query_embeddings=[query_embedding], n_results=args.top_k)

    for index, (unit_id, text, metadata, distance) in enumerate(
        zip(result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]),
        start=1,
    ):
        print(f"\n#{index} {unit_id} | cosine distance={distance:.4f}")
        print(f"Nguồn: {metadata['source_file']}, trang {metadata['page_start']}")
        print(text)


if __name__ == "__main__":
    main()

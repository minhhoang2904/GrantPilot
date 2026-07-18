"""Smoke test semantic retrieval trên Pinecone."""

import argparse
import os

from pipeline import FptClient, PINECONE_NAMESPACE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Câu hỏi tiếng Việt")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    try:
        from pinecone import Pinecone
    except ImportError as exc:
        raise RuntimeError("Thiếu pinecone. Chạy: pip install -r requirements.txt") from exc

    api_key = os.getenv("PINECONE_API_KEY", "").strip()
    index_name = os.getenv("PINECONE_INDEX_NAME", "").strip()
    index_host = os.getenv("PINECONE_INDEX_HOST", "").strip()
    if not api_key or not index_name:
        raise RuntimeError("Cần đặt PINECONE_API_KEY và PINECONE_INDEX_NAME")
    pc = Pinecone(api_key=api_key)
    index = pc.Index(host=index_host) if index_host else pc.Index(index_name)
    query_embedding = FptClient().embed([args.query])[0]
    result = index.query(
        vector=query_embedding,
        top_k=args.top_k,
        include_metadata=True,
        namespace=PINECONE_NAMESPACE,
    )

    for number, match in enumerate(result.matches, start=1):
        metadata = dict(match.metadata or {})
        print(f"\n#{number} {metadata.get('original_unit_id', match.id)} | score={match.score:.4f}")
        print(f"Nguồn: {metadata.get('source_file', '')}, trang {metadata.get('page_start', '')}")
        print(metadata.get("text", ""))


if __name__ == "__main__":
    main()

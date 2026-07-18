"""Pipeline: PDF scan -> OCR -> legal_units.jsonl -> policies.json -> Pinecone.

Chạy toàn bộ tài liệu trong data/raw:
    python pipeline.py all

Chạy riêng từng bước:
    python pipeline.py ocr
    python pipeline.py parse
    python pipeline.py mongo
    python pipeline.py embed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import requests


BASE_DIR = Path(__file__).resolve().parent
# Cho phép đặt key trong server-a-ingestion/.env; file này đã được gitignore.
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
    load_dotenv(BASE_DIR.parent / ".env")  # hỗ trợ .env ở root project
except ImportError:
    pass

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
OCR_DIR = DATA_DIR / "processed" / "ocr"
SHARED_DIR = Path(os.getenv("SHARED_DIR", BASE_DIR.parent / "shared"))
LEGAL_DIR = Path(os.getenv("LEGAL_OUTPUT_DIR", SHARED_DIR / "legal"))
LEGAL_UNITS_PATH = LEGAL_DIR / "legal_units.jsonl"
POLICIES_PATH = LEGAL_DIR / "policies.json"
POLICY_CANDIDATES_PATH = LEGAL_DIR / "policy_candidates.json"
POLICY_CACHE_DIR = DATA_DIR / "processed" / "policy_candidates"
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "legal_units")
SOURCES_PATH = BASE_DIR / "source_documents.json"

FPT_BASE_URL = os.getenv("FPT_BASE_URL", "https://mkp-api.fptcloud.com").rstrip("/")
POLICY_MODEL = os.getenv("FPT_POLICY_MODEL", "Llama-3.3-70B-Instruct")
EMBEDDING_MODEL = os.getenv("FPT_EMBEDDING_MODEL", "Vietnamese_Embedding")

OCR_PREFIX = r"^[\s\.\-:|`¡_‡]*"
ARTICLE_RE = re.compile(OCR_PREFIX + r"Đi[eêềệ]u\s+([0-9Il]+)[\.:]\s*(.+)$", re.IGNORECASE)
CHAPTER_RE = re.compile(OCR_PREFIX + r"Chương\s+([IVXLCDM]+|\d+)[\.:]?\s*(.*)$", re.IGNORECASE)
SECTION_RE = re.compile(OCR_PREFIX + r"Mục\s+(\d+)[\.:]?\s*(.*)$", re.IGNORECASE)
CLAUSE_RE = re.compile(r"^(\d{1,2})[\.\)]\s+(.+)$")
POINT_RE = re.compile(r"^([a-zđ])\)\s+(.+)$", re.IGNORECASE)


def pinecone_id(unit_id: str) -> str:
    """Pinecone IDs must be ASCII; keep the original ID in metadata."""
    return unit_id if unit_id.isascii() else "u_" + unit_id.encode("utf-8").hex()


def load_sources() -> dict[str, dict]:
    if not SOURCES_PATH.exists():
        return {}
    rows = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    return {row["file"]: row for row in rows}


def source_for(pdf: Path, sources: dict[str, dict]) -> dict:
    configured = sources.get(pdf.name, {})
    document_id = configured.get("document_id") or re.sub(r"[^a-z0-9]+", "-", pdf.stem.lower()).strip("-")
    return {
        "file": pdf.name,
        "document_id": document_id,
        "document_title": configured.get("document_title", pdf.stem),
        "document_number": configured.get("document_number", ""),
        "source_url": configured.get("source_url", ""),
        "issued_date": configured.get("issued_date"),
        "effective_from": configured.get("effective_from"),
        "effective_to": configured.get("effective_to"),
        "status": configured.get("status", "unknown"),
        "legal_status_checked_at": configured.get("legal_status_checked_at"),
    }


def pdf_files(filename: str | None = None) -> list[Path]:
    files = sorted(RAW_DIR.glob("*.pdf"))
    if filename:
        files = [path for path in files if path.name == filename]
    if not files:
        suffix = f" tên {filename}" if filename else ""
        raise FileNotFoundError(f"Không có PDF{suffix} trong {RAW_DIR}")
    return files


def normalize_ocr(text: str) -> str:
    text = text.replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ocr_pdf(pdf: Path, force: bool = False) -> Path:
    """Render từng trang bằng Poppler rồi OCR tiếng Việt bằng Tesseract."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Thiếu pytesseract/Pillow. Chạy: pip install -r requirements.txt") from exc

    if not shutil.which("pdftoppm"):
        raise RuntimeError("Thiếu Poppler (pdftoppm). macOS: brew install poppler")
    if not shutil.which("tesseract"):
        raise RuntimeError("Thiếu Tesseract. macOS: brew install tesseract tesseract-lang")

    output_dir = OCR_DIR / pdf.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    combined_path = output_dir / "pages.jsonl"
    if combined_path.exists() and not force:
        print(f"[OCR cache] {pdf.name}")
        return combined_path

    image_prefix = output_dir / "page"
    subprocess.run(
        ["pdftoppm", "-r", "300", "-png", str(pdf), str(image_prefix)],
        check=True,
    )

    pages = []
    for page_number, image_path in enumerate(sorted(output_dir.glob("page-*.png")), start=1):
        text = pytesseract.image_to_string(Image.open(image_path), lang="vie")
        pages.append({"page": page_number, "text": normalize_ocr(text)})
        image_path.unlink()  # chỉ cache text để tiết kiệm dung lượng
        print(f"[OCR] {pdf.name}: trang {page_number}")

    with combined_path.open("w", encoding="utf-8") as f:
        for page in pages:
            f.write(json.dumps(page, ensure_ascii=False) + "\n")
    return combined_path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def unit_id(document_id: str, article: str, clause: str, point: str) -> str:
    point = point.translate(str.maketrans({"đ": "d", "Đ": "D"}))
    parts = [document_id, f"art-{article}"]
    if clause:
        parts.append(f"cl-{clause}")
    if point:
        parts.append(f"pt-{point.lower()}")
    return "_".join(parts)


def parse_pages(pages: list[dict], source: dict) -> list[dict]:
    """Tách theo Chương/Mục/Điều/Khoản/Điểm, giữ số trang làm provenance."""
    units: list[dict] = []
    id_counts: dict[str, int] = defaultdict(int)
    chapter = section = article = article_title = clause = point = ""
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if not current:
            return
        current["text"] = "\n".join(current.pop("lines")).strip()
        if current["text"]:
            base_id = unit_id(source["document_id"], current["article"], current["clause"], current["point"])
            id_counts[base_id] += 1
            current["unit_id"] = base_id if id_counts[base_id] == 1 else f"{base_id}_occ-{id_counts[base_id]}"
            units.append(current)
        current = None

    def start(page: int, first_line: str) -> dict:
        return {
            "document_id": source["document_id"],
            "document_title": source["document_title"],
            "document_number": source["document_number"],
            "source_file": f"data/raw/{source['file']}",
            "source_url": source["source_url"],
            "issued_date": source.get("issued_date"),
            "effective_from": source.get("effective_from"),
            "effective_to": source.get("effective_to"),
            "document_status": source.get("status", "unknown"),
            "legal_status_checked_at": source.get("legal_status_checked_at"),
            "chapter": chapter,
            "section": section,
            "article": article,
            "article_title": article_title,
            "clause": clause,
            "point": point,
            "page_start": page,
            "page_end": page,
            "lines": [first_line],
        }

    for page in pages:
        page_number = int(page["page"])
        for raw_line in page["text"].splitlines():
            line = raw_line.strip()
            if not line or re.fullmatch(r"\d{1,3}", line):
                continue

            match = CHAPTER_RE.match(line)
            if match:
                flush()
                chapter = match.group(1)
                section = article = article_title = clause = point = ""
                continue
            match = SECTION_RE.match(line)
            if match:
                flush()
                section = match.group(1)
                article = article_title = clause = point = ""
                continue
            match = ARTICLE_RE.match(line)
            if match:
                flush()
                raw_article = match.group(1)
                article = "1" if raw_article.lower().replace("l", "i") == "i" else raw_article
                article_title = match.group(2).strip()
                clause = point = ""
                current = start(page_number, line)
                continue
            if not article:  # bỏ phần đầu văn bản trước Điều đầu tiên
                continue
            match = CLAUSE_RE.match(line)
            if match:
                flush()
                clause, point = match.group(1), ""
                current = start(page_number, line)
                continue
            match = POINT_RE.match(line)
            if match:
                flush()
                point = match.group(1).lower()
                current = start(page_number, line)
                continue

            if current is None:
                current = start(page_number, line)
            else:
                current["lines"].append(line)
                current["page_end"] = page_number
    flush()
    return units


class FptClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("FPT_API_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError("Chưa có FPT_API_KEY. Hãy đặt key mới trong biến môi trường.")
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _post(self, endpoint: str, payload: dict) -> dict:
        error: Exception | None = None
        for attempt in range(3):
            try:
                response = requests.post(
                    f"{FPT_BASE_URL}/{endpoint.lstrip('/')}",
                    headers=self.headers,
                    json=payload,
                    timeout=120,
                )
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                error = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        raise RuntimeError(f"FPT API lỗi tại {endpoint}: {error}") from error

    def extract_policies(self, source: dict, units: list[dict]) -> list[dict]:
        evidence = [u["unit_id"] for u in units]
        legal_text = "\n\n".join(f"[{u['unit_id']}]\n{u['text']}" for u in units)
        prompt = f"""Đọc nguyên văn pháp luật dưới đây và trích các chính sách hỗ trợ doanh nghiệp có thể dùng để kiểm tra điều kiện.

Chỉ trả JSON object đúng dạng:
{{"policies": [{{
  "policy_id": "id_ngan_gon_on_dinh",
  "policy_name": "tên chính sách",
  "category": "nhóm chính sách",
  "evidence_unit_ids": ["unit_id có thật"],
  "rules": {{"all": [{{"field": "tên_biến", "operator": "==|!=|>|>=|<|<=|in|contains", "value": "giá trị", "description": "giải thích"}}]}},
  "benefit_calculator": {{"type": "loại hỗ trợ", "calculation_status": "trạng thái", "note": "mức/quy tắc hoặc phần còn thiếu"}},
  "required_documents": [],
  "document_requirements_status": "known|requires_implementing_document"
}}]}}

Quy tắc: không suy diễn ngoài văn bản; không có chính sách thì trả policies rỗng; mọi evidence_unit_ids phải thuộc danh sách đã cung cấp.
Tài liệu: {source['document_title']} ({source['document_number']})

{legal_text[:30000]}"""
        payload = {
            "model": POLICY_MODEL,
            "messages": [
                {"role": "system", "content": "Bạn là chuyên viên bóc tách văn bản pháp luật Việt Nam. Chỉ xuất JSON hợp lệ."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "max_tokens": 3000,
            "stream": False,
        }
        data = self._post("chat/completions", payload)
        content = data["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
        result = json.loads(content)
        policies = result.get("policies", [])
        return [normalize_policy(p, source, evidence) for p in policies]

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = self._post(
            "embeddings",
            {"model": EMBEDDING_MODEL, "input": texts, "encoding_format": "float"},
        )
        return [item["embedding"] for item in sorted(data["data"], key=lambda item: item["index"])]


def normalize_policy(policy: dict, source: dict, valid_evidence: list[str]) -> dict:
    # LLM đôi khi trả ID ở cấp Điều (prefix) thay vì ID Khoản/Điểm đầy đủ.
    # Ánh xạ theo prefix để không làm mất policy; nếu vẫn không khớp thì
    # dùng toàn bộ units của Điều và đánh dấu cần review.
    raw_evidence = policy.get("evidence_unit_ids", []) or []
    evidence: list[str] = []
    for candidate in raw_evidence:
        if candidate in valid_evidence:
            evidence.append(candidate)
            continue
        evidence.extend(uid for uid in valid_evidence if uid.startswith(candidate + "_"))
    evidence = list(dict.fromkeys(evidence))
    evidence_repaired = False
    if not evidence:
        evidence = valid_evidence
        evidence_repaired = True
    raw_id = policy.get("policy_id") or policy.get("policy_name", "policy")
    clean_id = re.sub(r"[^a-z0-9_]+", "_", raw_id.lower()).strip("_")
    if not clean_id:
        clean_id = "policy_" + hashlib.sha1(raw_id.encode()).hexdigest()[:10]
    document_prefix = source["document_id"].replace("-", "_")
    evidence_suffix = hashlib.sha1("|".join(evidence).encode()).hexdigest()[:8]
    clean_id = f"{document_prefix}_{clean_id}_{evidence_suffix}"
    return {
        "policy_id": clean_id,
        "policy_name": policy.get("policy_name", "Chưa đặt tên"),
        "category": policy.get("category", "Khác"),
        "legal_source": {
            "document": source["document_title"],
            "document_number": source["document_number"],
            "url": source["source_url"],
            "local_file": f"data/raw/{source['file']}",
            "issued_date": source.get("issued_date"),
            "effective_from": source.get("effective_from"),
            "effective_to": source.get("effective_to"),
            "status": source.get("status", "unknown"),
            "legal_status_checked_at": source.get("legal_status_checked_at"),
        },
        "evidence_unit_ids": evidence,
        "rules": policy.get("rules", {"all": []}),
        "benefit_calculator": policy.get("benefit_calculator", {}),
        "required_documents": policy.get("required_documents", []),
        "document_requirements_status": policy.get("document_requirements_status", "requires_implementing_document"),
        "review": {
            "status": "ai_extracted_requires_review",
            "evidence_repaired": evidence_repaired,
        },
        "pipeline": {"document_id": source["document_id"], "model": POLICY_MODEL},
    }


def enrich_policy_source(policy: dict, source: dict) -> dict:
    """Cập nhật metadata văn bản cho policy lấy từ cache/ingest cũ."""
    policy = dict(policy)
    legal_source = dict(policy.get("legal_source") or {})
    legal_source.update(
        {
            "document": source["document_title"],
            "document_number": source["document_number"],
            "url": source["source_url"],
            "local_file": f"data/raw/{source['file']}",
            "issued_date": source.get("issued_date"),
            "effective_from": source.get("effective_from"),
            "effective_to": source.get("effective_to"),
            "status": source.get("status", "unknown"),
            "legal_status_checked_at": source.get("legal_status_checked_at"),
        }
    )
    policy["legal_source"] = legal_source
    pipeline = dict(policy.get("pipeline") or {})
    pipeline.setdefault("document_id", source["document_id"])
    pipeline.setdefault("model", POLICY_MODEL)
    policy["pipeline"] = pipeline
    return policy


def canonicalize_legacy_policy(policy: dict, source: dict | None) -> dict:
    """Giữ policy cũ nhưng đưa về schema chung, không coi là policy AI đã duyệt."""
    policy = dict(policy)
    policy.setdefault("evidence_unit_ids", [])
    policy.setdefault("pipeline", {"source": "legacy_manual"})
    if source:
        legal_source = dict(policy.get("legal_source") or {})
        legal_source.update(
            {
                "issued_date": source.get("issued_date"),
                "effective_from": source.get("effective_from"),
                "effective_to": source.get("effective_to"),
                "status": source.get("status", "unknown"),
                "legal_status_checked_at": source.get("legal_status_checked_at"),
            }
        )
        policy["legal_source"] = legal_source
    return policy


def run_ocr(pdfs: list[Path], force: bool = False) -> None:
    for pdf in pdfs:
        ocr_pdf(pdf, force=force)


def run_parse(pdfs: list[Path]) -> list[dict]:
    sources = load_sources()
    new_units: list[dict] = []
    selected_document_ids: set[str] = set()
    for pdf in pdfs:
        source = source_for(pdf, sources)
        selected_document_ids.add(source["document_id"])
        pages_path = OCR_DIR / pdf.stem / "pages.jsonl"
        if not pages_path.exists():
            raise FileNotFoundError(f"Thiếu OCR cache {pages_path}. Hãy chạy lệnh ocr trước.")
        units = parse_pages(read_jsonl(pages_path), source)
        new_units.extend(units)
        print(f"[PARSE] {pdf.name}: {len(units)} legal units")
    old_units = read_jsonl(LEGAL_UNITS_PATH)
    kept = [u for u in old_units if u["document_id"] not in selected_document_ids]
    all_units = kept + new_units
    write_jsonl(LEGAL_UNITS_PATH, all_units)
    return all_units


def run_mongo(pdfs: list[Path]) -> list[dict]:
    """Persist parsed legal units as immutable MongoDB document versions."""
    from mongo_store import database, ensure_indexes, ingest_document

    all_units = read_jsonl(LEGAL_UNITS_PATH)
    sources = load_sources()
    client, db = database()
    try:
        ensure_indexes(db)
        results = []
        for pdf in pdfs:
            source = source_for(pdf, sources)
            units = [u for u in all_units if u["document_id"] == source["document_id"]]
            result = ingest_document(db, pdf, source, units)
            results.append(result)
            state = "created" if result["created"] else "unchanged"
            print(f"[MONGO] {source['file']}: {state}, version={result['version']}, units={result.get('units', len(units))}")
        return results
    finally:
        client.close()


def run_policies(document_ids: set[str] | None = None, force: bool = False) -> list[dict]:
    units = read_jsonl(LEGAL_UNITS_PATH)
    if document_ids:
        units = [unit for unit in units if unit["document_id"] in document_ids]
    if not units:
        raise RuntimeError("legal_units.jsonl đang rỗng. Hãy chạy parse trước.")
    sources = {s["document_id"]: s for s in (source_for(p, load_sources()) for p in pdf_files())}
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for unit in units:
        grouped[(unit["document_id"], unit["article"])].append(unit)

    client = FptClient()
    generated: list[dict] = []
    for (document_id, article), article_units in grouped.items():
        POLICY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = POLICY_CACHE_DIR / f"{document_id}_art-{article}.json"
        fingerprint = hashlib.sha1(
            (POLICY_MODEL + json.dumps(article_units, ensure_ascii=False, sort_keys=True)).encode()
        ).hexdigest()
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        # Cache cũ được tạo trước khi bổ sung metadata ngày tháng có fingerprint
        # khác dù nội dung pháp lý không đổi; vẫn tái sử dụng để tránh gọi LLM lại.
        cache_is_usable = "policies" in cache and (
            cache.get("fingerprint") == fingerprint or "schema_version" not in cache
        )
        if not force and cache_is_usable:
            policies = [enrich_policy_source(p, sources[document_id]) for p in cache["policies"]]
            label = "POLICY cache"
        else:
            policies = client.extract_policies(sources[document_id], article_units)
            cache_path.write_text(
                json.dumps(
                    {"schema_version": 2, "fingerprint": fingerprint, "policies": policies},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            label = "POLICY"
        generated.extend(policies)
        print(f"[{label}] {document_id} Điều {article}: {len(policies)} policies")

    existing = json.loads(POLICIES_PATH.read_text(encoding="utf-8")) if POLICIES_PATH.exists() else []
    generated_documents = {document_id for document_id, _ in grouped}
    source_by_file = {source["file"]: source for source in sources.values()}
    kept = []
    for policy in existing:
        if policy.get("pipeline", {}).get("document_id") in generated_documents:
            continue
        local_file = Path(policy.get("legal_source", {}).get("local_file", "")).name
        kept.append(canonicalize_legacy_policy(policy, source_by_file.get(local_file)))
    merged = {p["policy_id"]: p for p in kept}
    merged.update({p["policy_id"]: p for p in generated})
    all_policies = list(merged.values())
    POLICIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    POLICIES_PATH.write_text(json.dumps(all_policies, ensure_ascii=False, indent=2), encoding="utf-8")
    candidates = [p for p in all_policies if p.get("review", {}).get("status") == "ai_extracted_requires_review"]
    POLICY_CANDIDATES_PATH.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[POLICY] Đã lưu {len(all_policies)} records vào {POLICIES_PATH}")
    print(f"[POLICY] Candidate records: {len(candidates)} -> {POLICY_CANDIDATES_PATH}")
    return all_policies


def run_policy_mongo(strict_document_status: bool = True) -> dict:
    """Validate and upsert policies only after legal documents/units exist in MongoDB."""
    from mongo_store import database, ensure_indexes
    from policy_quality import ingest_policies

    if not POLICIES_PATH.exists():
        raise FileNotFoundError(f"Không có policies tại {POLICIES_PATH}")
    policies = json.loads(POLICIES_PATH.read_text(encoding="utf-8"))
    client, db = database()
    try:
        ensure_indexes(db)
        result = ingest_policies(db, policies, strict_document_status=strict_document_status)
        print(f"[POLICY MONGO] {result}")
        return result
    finally:
        client.close()


def embedding_text(unit: dict) -> str:
    location = f"{unit['document_title']}"
    if unit.get("document_number"):
        location += f", số {unit['document_number']}"
    location += f"\nĐiều {unit['article']}"
    if unit.get("article_title"):
        location += f". {unit['article_title']}"
    if unit["clause"]:
        location += f"\nKhoản {unit['clause']}"
    if unit["point"]:
        location += f", điểm {unit['point']}"
    return f"{location}\n{unit.get('normalized_text') or unit['text']}"


def run_embed(batch_size: int = 32, force: bool = False) -> None:
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
    from mongo_store import database, current_units

    mongo_client, db = database()
    units = current_units(db)
    mongo_client.close()
    if not units:
        raise RuntimeError("legal_units.jsonl đang rỗng. Hãy chạy parse trước.")
    client = FptClient()
    pending = []
    for unit in units:
        fingerprint = hashlib.sha1((EMBEDDING_MODEL + embedding_text(unit)).encode()).hexdigest()
        vector_id = pinecone_id(unit["unit_id"])
        existing = index.fetch(ids=[vector_id], namespace=PINECONE_NAMESPACE)
        old_vector = existing.vectors.get(vector_id) if hasattr(existing, "vectors") else None
        old_metadata = (old_vector.metadata or {}) if old_vector else {}
        if force or old_metadata.get("embedding_fingerprint") != fingerprint:
            unit["embedding_fingerprint"] = fingerprint
            pending.append(unit)
    print(f"[EMBED] {len(units) - len(pending)} unchanged, {len(pending)} cần cập nhật")

    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        texts = [embedding_text(unit) for unit in batch]
        embeddings = client.embed(texts)
        metadatas = [
            {
                "document_id": u["document_id"],
                "article": u["article"],
                "clause": u["clause"],
                "point": u["point"],
                "page_start": u["page_start"],
                "page_end": u["page_end"],
                "source_file": u["source_file"],
                "source_url": u["source_url"],
                "document_number": u["document_number"],
                "article_title": u["article_title"],
                "issued_date": u["issued_date"] or "",
                "effective_from": u["effective_from"] or "",
                "effective_to": u["effective_to"] or "",
                "document_status": u["document_status"],
                "legal_status_checked_at": u["legal_status_checked_at"] or "",
                "version": u.get("version", 1),
                "is_current": bool(u.get("is_current", True)),
                "embedding_model": EMBEDDING_MODEL,
                "embedding_fingerprint": u["embedding_fingerprint"],
                "original_unit_id": u["unit_id"],
            }
            for u in batch
        ]
        vectors = [
            {"id": pinecone_id(u["unit_id"]), "values": vector, "metadata": {**metadata, "text": text}}
            for u, vector, metadata, text in zip(batch, embeddings, metadatas, texts)
        ]
        index.upsert(vectors=vectors, namespace=PINECONE_NAMESPACE)
        print(f"[EMBED] {min(start + batch_size, len(pending))}/{len(pending)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR và ingest văn bản pháp luật")
    parser.add_argument("stage", choices=["ocr", "parse", "mongo", "policies", "policy-mongo", "embed", "all"])
    parser.add_argument("--pdf", help="Chỉ ingest một file, ví dụ 04.signed.pdf")
    parser.add_argument("--force-ocr", action="store_true")
    parser.add_argument("--force-policy", action="store_true")
    parser.add_argument("--force-embed", action="store_true")
    parser.add_argument("--allow-unknown-document-status", action="store_true", help="Chỉ dùng cho development; production mặc định từ chối status=unknown")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    selected_pdfs = pdf_files(args.pdf)
    sources = load_sources()
    selected_document_ids = {source_for(pdf, sources)["document_id"] for pdf in selected_pdfs}

    if args.stage in {"ocr", "all"}:
        run_ocr(selected_pdfs, force=args.force_ocr)
    if args.stage in {"parse", "all"}:
        run_parse(selected_pdfs)
    if args.stage in {"mongo", "all"}:
        run_mongo(selected_pdfs)
    if args.stage in {"policies", "all"}:
        run_policies(document_ids=selected_document_ids if args.pdf else None, force=args.force_policy)
    if args.stage in {"policy-mongo", "all"}:
        run_policy_mongo(strict_document_status=not args.allow_unknown_document_status)
    if args.stage in {"embed", "all"}:
        run_embed(args.batch_size, force=args.force_embed)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
import os, json, uuid
from pathlib import Path

import fitz  # PyMuPDF
from utils import SOURCE_DIRS

# ---- 설정 ----
BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR  = BASE_DIR / "data" / "raw"
META_DIR = BASE_DIR / "data" / "meta"
META_DIR.mkdir(parents=True, exist_ok=True)

OUT_PATH = META_DIR / "prepared.jsonl"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

def iter_pdf_files():
    # data/raw/{FDA,EU,ICH,PICS,WHO,MFDS,OTHER}/*.pdf
    for src in SOURCE_DIRS:
        d = RAW_DIR / src
        if not d.exists():
            continue
        for p in d.rglob("*.pdf"):
            yield src, p

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + size)
        chunks.append(text[start:end].strip())
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks

def write_jsonl(record: dict):
    with open(OUT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def main():
    processed = 0
    for source, pdf_path in iter_pdf_files():
        doc = None
        try:
            doc = fitz.open(pdf_path)
            n_pages = len(doc)  # 닫기 전에 미리 확보
            for page_index in range(n_pages):
                try:
                    page = doc.load_page(page_index)
                    text = page.get_text("text") or ""
                except Exception as e:
                    print(f"[ERR page] {pdf_path} p.{page_index+1} -> {e}")
                    continue

                chunks = chunk_text(text)
                if not chunks:
                    continue

                for ci, ctext in enumerate(chunks):
                    rec = {
                        "id": str(uuid.uuid4()),
                        "source": source,
                        "file_path": str(pdf_path).replace("\\", "/"),
                        "page": page_index + 1,
                        "chunk_index": ci,
                        "text": ctext,
                    }
                    write_jsonl(rec)
                    processed += 1

            print(f"[OK] {source:<5} {pdf_path.name} -> pages={n_pages}")

        except Exception as e:
            print(f"[ERR open] {pdf_path} -> {e}")
        finally:
            if doc is not None:
                try:
                    doc.close()
                except:
                    pass

    print(f"✔ Done. chunks={processed}, out={OUT_PATH}")

if __name__ == "__main__":
    main()

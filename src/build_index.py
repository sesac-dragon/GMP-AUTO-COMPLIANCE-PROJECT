# -*- coding: utf-8 -*-
import os, json
from pathlib import Path

import numpy as np
import faiss  # pip install faiss-cpu
from openai import OpenAI

import utils  # (.env 강제 로드 포함)

BASE_DIR = Path(__file__).resolve().parents[1]
META_DIR = BASE_DIR / "data" / "meta"
VEC_DIR  = BASE_DIR / "vectorstore"
VEC_DIR.mkdir(parents=True, exist_ok=True)

PREPARED_JSONL = META_DIR / "prepared.jsonl"
INDEX_PATH = VEC_DIR / "gmp_faiss.index"
DOCS_META   = VEC_DIR / "docs.jsonl"

EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
DIM_MAP = {
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
}

client = OpenAI()  # utils가 .env를 이미 로드함

def read_prepared():
    if not PREPARED_JSONL.exists():
        return []
    with open(PREPARED_JSONL, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def batch(iterable, n=96):
    for i in range(0, len(iterable), n):
        yield iterable[i:i+n]

def get_dim():
    if EMBED_MODEL in DIM_MAP:
        return DIM_MAP[EMBED_MODEL]
    # 미지 모델이면 샘플로 추론 (비용 발생 주의)
    resp = client.embeddings.create(model=EMBED_MODEL, input=["dim-probe"])
    return len(resp.data[0].embedding)

def main():
    all_rows = read_prepared()
    if not all_rows:
        print(f"[WARN] No prepared data at {PREPARED_JSONL}. Run prepare_docs.py first.")
        # 빈 인덱스라도 생성
        dim = get_dim()
        index = faiss.IndexFlatL2(dim)
        faiss.write_index(index, str(INDEX_PATH))
        with open(DOCS_META, "w", encoding="utf-8") as f:
            pass
        print(f"✔ Empty index created: {INDEX_PATH} (dim={dim}, n=0)")
        return

    texts = [r["text"] for r in all_rows]
    dim = get_dim()
    index = faiss.IndexFlatL2(dim)

    vecs = []
    for bs in batch(texts, n=96):
        resp = client.embeddings.create(model=EMBED_MODEL, input=bs)
        for e in resp.data:
            vecs.append(np.array(e.embedding, dtype="float32"))

    if vecs:
        mat = np.vstack(vecs)
        index.add(mat)

    # 저장
    faiss.write_index(index, str(INDEX_PATH))
    with open(DOCS_META, "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"✔ Index built: {INDEX_PATH} (dim={dim}, n={index.ntotal})")
    print(f"✔ Meta saved:  {DOCS_META}")

if __name__ == "__main__":
    main()

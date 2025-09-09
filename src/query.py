# -*- coding: utf-8 -*-
import os, json, argparse, textwrap
from pathlib import Path

import numpy as np
import faiss
from openai import OpenAI

import utils  # (.env 강제 로드 포함)

BASE_DIR = Path(__file__).resolve().parents[1]
VEC_DIR  = BASE_DIR / "vectorstore"
INDEX_PATH = VEC_DIR / "gmp_faiss.index"
DOCS_META  = VEC_DIR / "docs.jsonl"

EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
GEN_MODEL   = os.getenv("RAG_MODEL", "gpt-4o-mini")

client = OpenAI()

def load_index_and_meta():
    if not INDEX_PATH.exists() or not DOCS_META.exists():
        raise FileNotFoundError("Index or docs meta not found. Run build_index.py first.")
    index = faiss.read_index(str(INDEX_PATH))
    metas = []
    with open(DOCS_META, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                metas.append(json.loads(line))
    return index, metas

def embed(texts):
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [np.array(e.embedding, dtype="float32") for e in resp.data]

def search(index, metas, query_vec, top_k=20, allowed_sources=None):
    if index.ntotal == 0:
        return []
    D, I = index.search(np.array([query_vec], dtype="float32"), top_k*2)
    items = []
    for idx in I[0]:
        if int(idx) < 0 or int(idx) >= len(metas):
            continue
        m = metas[int(idx)]
        if allowed_sources and m.get("source") not in allowed_sources:
            continue
        items.append(m)
        if len(items) >= top_k:
            break
    return items

def build_prompt(query, contexts):
    bullets = []
    for c in contexts:
        bullets.append(
            f"- [src:{c.get('source')}] {c.get('file_path')} (p.{c.get('page')}) :: "
            + textwrap.shorten(c.get("text","").replace("\n"," "), width=220, placeholder="…")
        )
    ctx_block = "\n".join(bullets) if bullets else "(근거 없음)"

    sys_msg = (
        "You are a compliance assistant. Answer in Korean.\n"
        "Use only the given context. If insufficient, say you don't know.\n"
        "Always cite file path and page numbers that support the answer."
    )
    user_msg = (
        f"질문: {query}\n\n"
        f"다음은 검색된 근거 조각입니다:\n{ctx_block}\n\n"
        "요청: 위 근거만 사용해 간결하게 답하고, 끝에 근거 파일경로와 페이지를 나열해 주세요."
    )
    return sys_msg, user_msg

def generate_answer(query, contexts):
    if not contexts:
        return "검색된 근거가 없습니다. 인덱스를 다시 빌드하거나, 소스 필터를 조정해 보세요."
    sys_msg, user_msg = build_prompt(query, contexts)
    resp = client.chat.completions.create(
        model=GEN_MODEL,
        temperature=0.2,
        messages=[
            {"role":"system","content":sys_msg},
            {"role":"user","content":user_msg},
        ],
    )
    return resp.choices[0].message.content

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--q", required=True, help="질문")
    parser.add_argument("--sources", nargs="*", help="예: EU FDA ICH PICS WHO MFDS")
    parser.add_argument("--topk", type=int, default=8)
    args = parser.parse_args()

    index, metas = load_index_and_meta()
    qvec = embed([args.q])[0]
    allowed = set(args.sources) if args.sources else None
    hits = search(index, metas, qvec, top_k=args.topk, allowed_sources=allowed)

    print("="*80)
    print(f"Q: {args.q}")
    if allowed:
        print(f"sources filter: {', '.join(allowed)}")
    print("-"*80)
    for i, h in enumerate(hits, 1):
        snip = textwrap.shorten(h.get("text","").replace("\n"," "), width=160, placeholder="…")
        print(f"[{i:02d}] [{h.get('source')}] {h.get('file_path')} (p.{h.get('page')}) :: {snip}")
    print("="*80)

    ans = generate_answer(args.q, hits)
    print(ans)

if __name__ == "__main__":
    main()

import os, yaml, pandas as pd, numpy as np
import streamlit as st
import faiss
from dotenv import load_dotenv
from openai import OpenAI

with open("config.yaml", "r", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

VECTOR_DIR = CFG["vector_dir"]
FAISS_PATH = os.path.join(VECTOR_DIR, "faiss.index")
META_PARQUET = os.path.join(VECTOR_DIR, "meta.parquet")

load_dotenv()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4.1-mini")

client = OpenAI()

st.set_page_config(page_title="GMP RAG", layout="wide")
st.title("🧪 GMP Guidelines RAG")
st.caption("Filter by source (FDA/EU/ICH/PIC/S/WHO), retrieve top contexts, and get an answer with inline citations.")

@st.cache_resource
def load_index():
    idx = faiss.read_index(FAISS_PATH)
    meta = pd.read_parquet(META_PARQUET)
    return idx, meta

def embed(q: str):
    v = client.embeddings.create(model=EMBEDDING_MODEL, input=[q]).data[0].embedding
    v = np.array(v, dtype="float32")
    faiss.normalize_L2(v.reshape(1, -1))
    return v

def retrieve(idx, meta, q, sources, k=6):
    v = embed(q)
    D, I = idx.search(v, k*5)
    I = I[0]; D = D[0]
    rows = meta.iloc[I].copy()
    if sources:
        rows = rows[rows["source"].isin(sources)]
    rows["score"] = [float(D[i]) for i in range(len(D))][:len(rows)]
    rows = rows.sort_values("score", ascending=False).head(k)
    return rows

def chat_answer(q, rows):
    sys = "You are a GMP expert. Answer using the provided context only. Cite sources by source and page."
    ctx_blocks = []
    for _, r in rows.iterrows():
        cite = f'[{r["source"]} | p{r["page"]} | {os.path.basename(r["path"])}]'
        ctx_blocks.append(cite + "\n" + r["text"][:1500])
    ctx = "\n\n---\n\n".join(ctx_blocks)
    prompt = f"Question:\n{q}\n\nContext:\n{ctx}\n\nAnswer in Korean. Include inline citations like [FDA p12], [EU p3]. If unsure, say so."

    chat = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role":"system","content": sys},
            {"role":"user","content": prompt}
        ],
        temperature=0.2,
    )
    return chat.choices[0].message.content

idx, meta = load_index()

with st.sidebar:
    st.subheader("Filters")
    sources = st.multiselect("Sources", ["FDA","EU","ICH","PICS","WHO"], default=["FDA","EU","ICH","PICS","WHO"])
    k = st.slider("Top-K", 2, 10, 6)

q = st.text_input("질문을 입력하세요 (예: 공정 밸리데이션 요건 비교)")
if st.button("Search") and q:
    rows = retrieve(idx, meta, q, sources, k)
    st.markdown("### Retrieved Contexts")
    for i, r in rows.reset_index(drop=True).iterrows():
        st.markdown(f"**{i+1}. {r['source']} p{r['page']}** — {os.path.basename(r['path'])}  (score={r['score']:.4f})")
        with st.expander("Show text"):
            st.write(r["text"][:1500])

    try:
        st.markdown("### Answer")
        ans = chat_answer(q, rows)
        st.write(ans)
    except Exception as e:
        st.warning("LLM 호출 실패. 컨텍스트만 표시합니다.")
        st.exception(e)

# GMP Guidelines RAG Pipeline

This project crawls GMP guideline PDFs from **gmpeye** (and subpages), classifies them by source
(**FDA**, **EU**, **ICH**, **PIC/S**, **WHO**), converts PDFs to text, chunks & embeds, and builds a FAISS vector index
for RAG (Retrieval Augmented Generation). Includes a simple CLI query and a Streamlit app.

> Created: 2025-09-04T02:48:44.397424Z

---

## 1) Quickstart

```bash
# 0) Python 3.9+ recommended
python -V

# 1) Create virtual env (optional)
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# 2) Install requirements
pip install -r requirements.txt

# 3) Copy .env.template to .env and edit values
cp .env.template .env  # (Windows PowerShell) Copy-Item .env.template .env
# Set OPENAI_API_KEY=... (if you will generate embeddings/answers via OpenAI)

# 4) Crawl (download PDFs + metadata)
python -m src.crawler

# 5) Prepare documents (PDF -> text pages JSONL)
python src/prepare_docs.py

# 6) Build vector index (chunk + embed + FAISS)
python src/build_index.py

# 7) Ask a question (CLI)
python src/query.py --q "FDA GMP의 공정 밸리데이션 요건이 뭐야?" --sources FDA

# 8) Optional: Streamlit UI
streamlit run streamlit_app.py
```

---

## 2) Project Layout

```
gmp_rag_pipeline/
  README.md
  requirements.txt
  .env.template
  config.yaml
  src/
    utils.py
    crawler.py
    prepare_docs.py
    build_index.py
    query.py
  streamlit_app.py
  data/
    raw/           # downloaded PDFs by source (FDA/EU/ICH/PICS/WHO/OTHER)
    meta/          # metadata jsonl
    prepared/      # PDF pages -> text JSONL
  vectorstore/
    faiss.index
    meta.parquet
```

---

## 3) Notes & Tips

- The site **gmpeye** hosts many guidelines mirrored from original sources (EMA, FDA, WHO, PIC/S, etc.). If strict freshness is required,
  consider periodically cross-checking with original sources as part of your update job.
- Classification uses URL path + anchor text heuristics. You can finetune the rules in `src/utils.py: classify_source()`.
- Defaults use OpenAI embeddings (`text-embedding-3-large`) and GPT model for answers. You can swap to local embeddings if you prefer
  (see comments in `build_index.py`).

---

## 4) Scheduled Runs

- Windows Task Scheduler or cron can run `crawler.py`, then `prepare_docs.py`, then `build_index.py` daily/weekly.
- The crawler is **polite** by default (rate limit & retries), but please check robots/ToS for compliance.

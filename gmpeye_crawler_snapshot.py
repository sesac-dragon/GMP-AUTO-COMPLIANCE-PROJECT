# -*- coding: utf-8 -*-
# Anaconda 실행 명령어
# python gmpeye_crawler_snapshot.py ^
#  --base "http://www.gmpeye.co.kr/gmpguidesandguidelines/gmpguides.htm" ^
#  --max-depth 2 ^
#  --polite 0.5


"""
Snapshot crawler for GMPEye GMP guidelines
-----------------------------------------
- Discovers PDF links on http://www.gmpeye.co.kr/gmpguidesandguidelines/gmpguides.htm
  including javascript:na_open_window('...pdf') patterns
- Validates as real PDFs (Content-Type + %PDF- + min size)
- Compares to prior state (sha256) → NEW / CHANGED / REMOVED detection
- If ANY update is detected, saves a FULL snapshot of ALL current PDFs under
  <OUTROOT>/<YYYY-MM-DD>/<REGULATOR>/*.pdf
- Writes changes.csv (delta summary) and manifest.csv (all files of the snapshot)

Default paths (방법 2 적용):
- OUTROOT defaults to the folder where THIS script lives
- STATE defaults to <script folder>/state.json

USAGE (Windows, Anaconda Prompt):
    cd C:\\Users\\MASTER\\Desktop\\crawler
    python gmpeye_crawler_snapshot.py \
      --base "http://www.gmpeye.co.kr/gmpguidesandguidelines/gmpguides.htm" \
      --max-depth 2 \
      --polite 0.5

Optional overrides:
    --outroot "C:\\somewhere\\archive"  --state "C:\\somewhere\\state.json"
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import hashlib
import urllib.parse as urlparse
from datetime import datetime, timezone
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

# Optional page counting
try:
    import PyPDF2
    HAVE_PYPDF2 = True
except Exception:
    HAVE_PYPDF2 = False

# ------------------------ Config ------------------------
DEFAULT_BASE = "http://www.gmpeye.co.kr/gmpguidesandguidelines/gmpguides.htm"
PDF_MAGIC = b"%PDF-"
MIN_PDF_BYTES = 2048

REGULATOR_ALIASES = {
    "usfda": "FDA",
    "fda": "FDA",
    "ema": "EMA",
    "who": "WHO",
    "ich": "ICH",
    "mfds": "MFDS",
    "pmda": "PMDA",
    "pic/s": "PICS",
    "pics": "PICS",
    "pic": "PICS",
    "ec": "EC",
    "eu": "EU",
}
FALLBACK_REGULATOR = "OTHER"

JS_LINK_RE = re.compile(
    r"javascript:\s*na_open_window\s*\(\s*'[^']*'\s*,\s*'([^']+?\.pdf)'\s*,",
    re.I,
)

# ------------------------ Utilities ------------------------

def build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET"],
        respect_retry_after_header=True,
    )
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return s

def safe_filename(name: str, max_len: int = 160) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name[:max_len]).rstrip(". ")

def regulator_from_url(url: str) -> str:
    try:
        p = urlparse.urlparse(url)
        parts = [x for x in p.path.split("/") if x]
        for seg in parts:
            key = seg.lower()
            if key in REGULATOR_ALIASES:
                return REGULATOR_ALIASES[key]
        lp = p.path.lower()
        if "usfda" in lp: return "FDA"
        if "/ich/" in lp: return "ICH"
        if "/ema/" in lp: return "EMA"
        if "/who/" in lp: return "WHO"
        if "/mfds/" in lp: return "MFDS"
        if ("pics" in lp) or ("pic/s" in lp) or ("pic" in lp): return "PICS"
    except Exception:
        pass
    return FALLBACK_REGULATOR

def is_pdf_response(resp: requests.Response, sniff: bytes) -> bool:
    ctype = (resp.headers.get("Content-Type") or "").lower()
    return sniff.startswith(PDF_MAGIC) or ("application/pdf" in ctype)

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

# ------------------------ HTML & PDF fetch ------------------------

def fetch_text(session: requests.Session, url: str, referer: Optional[str]=None, timeout: float=15.0) -> str:
    headers = {"Referer": referer} if referer else {}
    r = session.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text

def get_pdf(session: requests.Session, url: str, referer: Optional[str]=None, timeout: float=30.0) -> Optional[bytes]:
    headers = {"Accept": "application/pdf,*/*;q=0.8"}
    if referer:
        headers["Referer"] = referer
    r = session.get(url, headers=headers, stream=True, timeout=timeout)
    r.raise_for_status()
    data = r.content
    if len(data) < MIN_PDF_BYTES: return None
    if not is_pdf_response(r, data[:8]): return None
    return data

# ------------------------ Link extraction ------------------------

def extract_pdf_links(html: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: Set[str] = set()

    # <a href="...pdf"> and javascript links
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().endswith(".pdf"):
            urls.add(urlparse.urljoin(base_url, href))
        elif href.lower().startswith("javascript:"):
            m = JS_LINK_RE.search(href)
            if m:
                urls.add(urlparse.urljoin(base_url, m.group(1)))

    # onclick handlers
    for tag in soup.find_all(attrs={"onclick": True}):
        onclick = (tag.get("onclick") or "")
        m = JS_LINK_RE.search(onclick)
        if m:
            urls.add(urlparse.urljoin(base_url, m.group(1)))

    return sorted(urls)

def extract_child_links(html: str, base_url: str, same_host: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: Set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("javascript:"):  # ignore js for pages
            continue
        abs_url = urlparse.urljoin(base_url, href)
        p = urlparse.urlparse(abs_url)
        if p.scheme in ("http", "https") and p.netloc == same_host:
            if not abs_url.lower().endswith(".pdf"):
                urls.add(abs_url)
    return sorted(urls)

# ------------------------ State ------------------------

def load_state(path: Path) -> Dict[str, dict]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"files": {}, "last_run": None, "last_snapshot_dir": None}

def save_state(state: Dict[str, dict], path: Path) -> None:
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

# ------------------------ Crawl & Snapshot ------------------------

def page_count_from_bytes(b: bytes) -> Optional[int]:
    if not HAVE_PYPDF2:
        return None
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(b))
        return len(reader.pages)
    except Exception:
        return None

def crawl_and_maybe_snapshot(base_url: str, outroot: Path, state_path: Path, max_depth: int, polite: float):
    outroot.mkdir(parents=True, exist_ok=True)
    session = build_session()

    base = urlparse.urlparse(base_url)
    host = base.netloc

    # Discover PDFs via BFS
    seen_pages: Set[str] = set()
    pdf_urls: Set[str] = set()
    dq = deque([(base_url, 0, None)])

    print(f"\u25b6 Start: {base_url}")
    while dq:
        url, depth, referer = dq.popleft()
        if url in seen_pages:
            continue
        seen_pages.add(url)

        try:
            html = fetch_text(session, url, referer=referer)
        except Exception as e:
            print(f"[HTML ERR] {url} -> {e}")
            continue

        for pu in extract_pdf_links(html, url):
            pdf_urls.add(pu)

        if depth < max_depth:
            for child in extract_child_links(html, url, host):
                if child not in seen_pages:
                    dq.append((child, depth + 1, url))

        time.sleep(polite)

    print(f"Discovered {len(pdf_urls)} candidate PDF URLs")

    # Load previous state
    state = load_state(state_path)
    prev_files: Dict[str, dict] = state.get("files", {})

    # GET all PDFs → compute hash, size, pages, regulator
    current: Dict[str, dict] = {}
    failed: List[str] = []

    for idx, u in enumerate(sorted(pdf_urls), start=1):
        try:
            data = get_pdf(session, u, referer=base_url)
            if data is None:
                print(f"[NOT_PDF/SMALL] {u}")
                failed.append(u)
                continue
            h = sha256_bytes(data)
            size = len(data)
            pages = page_count_from_bytes(data)
            regulator = regulator_from_url(u)
            filename = os.path.basename(urlparse.urlparse(u).path) or "document.pdf"
            filename = safe_filename(filename)
            current[u] = {
                "url": u,
                "sha256": h,
                "size": size,
                "pages": pages,
                "regulator": regulator,
                "filename": filename,
                "bytes": data,  # hold for snapshot save
            }
            # Lightweight progress
            if idx % 20 == 0:
                print(f"  fetched {idx}/{len(pdf_urls)} ...")
        except Exception as e:
            print(f"[GET ERR] {u} -> {e}")
            failed.append(u)
        time.sleep(polite)

    # Compare current vs previous
    prev_set = set(prev_files.keys())
    curr_set = set(current.keys())

    removed = sorted(prev_set - curr_set)
    new = sorted(curr_set - prev_set)

    changed, unchanged = [], []
    for u in sorted(prev_set & curr_set):
        if prev_files[u].get("sha256") != current[u]["sha256"]:
            changed.append(u)
        else:
            unchanged.append(u)

    any_update = bool(new or changed or removed)

    print("\n=== DETECTION SUMMARY ===")
    print(f"New: {len(new)}, Changed: {len(changed)}, Removed: {len(removed)}, Failed: {len(failed)}, Unchanged: {len(unchanged)}")

    if not any_update:
        print("No changes detected. Snapshot will NOT be created.")
        state["files"] = {u: {k: v for k, v in current[u].items() if k != "bytes"} for u in current}
        save_state(state, state_path)
        return None

    # Create dated snapshot and save ALL current PDFs
    today = datetime.now().strftime("%Y-%m-%d")
    snapshot_dir = outroot / today
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    for u, meta in current.items():
        reg = meta["regulator"] or FALLBACK_REGULATOR
        reg_dir = snapshot_dir / reg
        reg_dir.mkdir(parents=True, exist_ok=True)
        save_path = reg_dir / meta["filename"]
        tmp = save_path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            f.write(meta["bytes"])
        tmp.replace(save_path)
        meta["saved_path"] = str(save_path)

    # Write changes.csv
    changes_csv = snapshot_dir / "changes.csv"
    with open(changes_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["status", "url", "regulator", "filename",
                    "old_size", "new_size", "old_pages", "new_pages", "old_saved_path"])
        for u in new:
            w.writerow(["NEW", u, current[u]["regulator"], current[u]["filename"],
                        "", current[u]["size"], "", current[u]["pages"], ""])
        for u in changed:
            old = prev_files[u]
            w.writerow(["CHANGED", u, current[u]["regulator"], current[u]["filename"],
                        old.get("size", ""), current[u]["size"],
                        old.get("pages", ""), current[u]["pages"],
                        old.get("saved_path", "")])
        for u in removed:
            old = prev_files[u]
            w.writerow(["REMOVED", u, old.get("regulator", ""), old.get("filename", ""),
                        old.get("size", ""), "", old.get("pages", ""), "", old.get("saved_path", "")])

    # Write manifest.csv (all files saved this run)
    manifest_csv = snapshot_dir / "manifest.csv"
    with open(manifest_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url", "regulator", "filename", "size", "pages", "saved_path", "sha256"])
        for u, meta in sorted(current.items()):
            w.writerow([u, meta["regulator"], meta["filename"], meta["size"], meta["pages"], meta.get("saved_path", ""), meta["sha256"]])

    # Update state (drop raw bytes)
    state["files"] = {}
    for u, meta in current.items():
        row = {k: v for k, v in meta.items() if k != "bytes"}
        state["files"][u] = row
    state["last_snapshot_dir"] = str(snapshot_dir)
    save_state(state, state_path)

    print(f"\nSnapshot created at: {snapshot_dir}")
    print(f"- changes.csv: {changes_csv}")
    print(f"- manifest.csv: {manifest_csv}")
    if failed:
        print(f"WARNING: {len(failed)} URLs failed to fetch as valid PDFs and are NOT in the snapshot. See above logs.")

    return str(snapshot_dir)

# ------------------------ Main ------------------------

def main():
    SCRIPT_DIR = Path(__file__).resolve().parent

    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE, help="Start page URL")
    # 방법 2: 기본 저장 경로/상태 파일을 스크립트 폴더로 설정
    ap.add_argument("--outroot", default=str(SCRIPT_DIR), help="Root directory to store dated snapshots")
    ap.add_argument("--state", default=str(SCRIPT_DIR / "state.json"), help="Path to state manifest JSON")
    ap.add_argument("--max-depth", type=int, default=2, help="HTML crawl depth for discovering PDFs")
    ap.add_argument("--polite", type=float, default=0.5, help="Sleep seconds between requests")
    args = ap.parse_args()

    outroot = Path(args.outroot)
    state_path = Path(args.state)
    try:
        snap = crawl_and_maybe_snapshot(args.base, outroot, state_path, args.max_depth, args.polite)
        if snap is None:
            # No change detected → distinct exit code (useful in schedulers)
            sys.exit(2)
        else:
            sys.exit(0)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

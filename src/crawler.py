# -*- coding: utf-8 -*-
import os, json, time, re
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup

from utils import hashed_filename, ensure_dirs, classify_source, utc_now_iso, SOURCE_DIRS

# -------------------- 설정 --------------------
START_URL = "http://www.gmpeye.co.kr/gmpguidesandguidelines/gmpguides.htm"
ALLOWED_NETLOCS = {"gmpeye.co.kr", "www.gmpeye.co.kr"}  # www/비-www 모두 허용
TIMEOUT = 20
RATE_SLEEP_SEC = 0.2
MAX_DEPTH = 5
MAX_PAGES = 700

# 프로젝트 루트: src 상위 폴더
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_DIR  = os.path.join(BASE_DIR, "data", "raw")
META_DIR = os.path.join(BASE_DIR, "data", "meta")
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(META_DIR, exist_ok=True)
ensure_dirs(RAW_DIR)  # FDA/EU/ICH/PICS/WHO/MFDS/OTHER 폴더 생성

META_PATH = os.path.join(META_DIR, "downloads.jsonl")

# -------------------- 세션 --------------------
session = requests.Session()
retries = Retry(total=5, backoff_factor=0.6, status_forcelist=[429, 500, 502, 503, 504])
session.mount("http://", HTTPAdapter(max_retries=retries))
session.mount("https://", HTTPAdapter(max_retries=retries))
session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; gmpeye-pdf-crawler/1.3)"})

# -------------------- 유틸 --------------------
def is_allowed(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
        return (host in ALLOWED_NETLOCS) or (host == "")
    except Exception:
        return False

# href="javascript:na_open_window('win','path.pdf',...)" 또는
# onclick="na_open_window('win','path.pdf',...)" 모두 지원
_JS_PATH_RE = re.compile(
    r"""na_open_window\d*\s*\(\s*[^,]*,\s*(['"])(?P<path>[^'"]+?)\1""",
    re.IGNORECASE | re.VERBOSE
)

def extract_from_js_attr(js: str | None, base_url: str) -> str | None:
    if not js:
        return None
    m = _JS_PATH_RE.search(js)
    if m:
        inner = m.group("path").strip()
        return urljoin(base_url, inner)
    return None

def extract_href(raw_href: str | None, base_url: str) -> str | None:
    if not raw_href:
        return None
    href = raw_href.strip()
    low = href.lower()
    if low.startswith(("mailto:", "tel:")):
        return None
    if low.startswith("javascript:"):
        return extract_from_js_attr(href, base_url)
    return urljoin(base_url, href)

def is_pdf_url(u: str) -> bool:
    try:
        path = urlparse(u).path.lower()
        return path.endswith(".pdf")
    except Exception:
        return False

def save_meta(record: dict):
    with open(META_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def load_seen_urls(meta_path: str) -> set:
    seen = set()
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if "url" in rec:
                        seen.add(rec["url"])
                except:
                    pass
    return seen

SEEN_URLS = load_seen_urls(META_PATH)

def build_context_label(a_tag, page_title: str | None) -> str:
    """링크 텍스트 + title 속성 + 페이지 제목 + 상위 컨테이너 일부"""
    pieces = []
    txt = a_tag.get_text(" ", strip=True)
    if txt:
        pieces.append(txt)
    t_attr = a_tag.get("title")
    if t_attr:
        pieces.append(t_attr)
    if page_title:
        pieces.append(page_title)
    parent = a_tag.find_parent()
    if parent:
        try:
            ptxt = parent.get_text(" ", strip=True)
            if ptxt and ptxt != txt:
                pieces.append(ptxt[:120])
        except:
            pass
    return " | ".join(pieces)

def download_pdf(pdf_url: str, label_text: str):
    if pdf_url in SEEN_URLS:
        return
    try:
        r = session.get(pdf_url, timeout=TIMEOUT)
        if r.status_code != 200:
            return

        source = classify_source(pdf_url, label_text)  # 풍부한 문맥 전달
        if source not in SOURCE_DIRS:
            source = "OTHER"

        fname = hashed_filename(pdf_url)
        dst_dir = os.path.join(RAW_DIR, source)
        os.makedirs(dst_dir, exist_ok=True)
        path = os.path.join(dst_dir, fname)

        if os.path.exists(path) and os.path.getsize(path) == len(r.content):
            SEEN_URLS.add(pdf_url)
            return

        with open(path, "wb") as f:
            f.write(r.content)

        size = os.path.getsize(path)
        rec = {
            "ts": utc_now_iso(),
            "url": pdf_url,
            "anchor": label_text,
            "source": source,
            "filepath": path.replace("\\", "/"),
            "size": size,
            "headers": dict(r.headers),
        }
        save_meta(rec)
        SEEN_URLS.add(pdf_url)
        print(f"[OK] {source:<5} {os.path.basename(path)}  ({size} bytes)")

    except Exception as e:
        print(f"[ERR] {pdf_url} -> {e}")

def crawl():
    seen_pages = set()
    q = deque([(START_URL, 0)])
    pages = 0
    print(f"▶ Start: {START_URL}")

    while q:
        url, depth = q.popleft()
        if url in seen_pages or depth > MAX_DEPTH or pages >= MAX_PAGES:
            continue
        seen_pages.add(url)
        pages += 1

        try:
            resp = session.get(url, timeout=TIMEOUT)
            ctype = resp.headers.get("Content-Type", "").lower()
            if resp.status_code != 200 or "text/html" not in ctype:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            page_title = soup.title.get_text(strip=True) if (soup.title and soup.title.get_text()) else None

            for a in soup.find_all("a"):
                full = extract_href(a.get("href"), url)
                if not full:
                    full = extract_from_js_attr(a.get("onclick"), url)
                if not full:
                    continue
                if not is_allowed(full):
                    continue

                label = build_context_label(a, page_title)

                if is_pdf_url(full):
                    download_pdf(full, label)
                    time.sleep(RATE_SLEEP_SEC)
                else:
                    q.append((full, depth + 1))

            time.sleep(RATE_SLEEP_SEC)

        except Exception as e:
            print(f"[ERR] page {url} -> {e}")

    print("✔ Done.")

if __name__ == "__main__":
    crawl()

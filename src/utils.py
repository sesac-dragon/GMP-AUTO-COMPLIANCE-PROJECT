# -*- coding: utf-8 -*-
import os, re, hashlib
from urllib.parse import urlparse, unquote
from datetime import datetime
from pathlib import Path

# ---- .env 강제 로드 (.env가 OS 환경변수보다 우선) ----
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    ROOT_DIR = Path(__file__).resolve().parents[1]
    load_dotenv(ROOT_DIR / ".env", override=True)
except Exception:
    ROOT_DIR = Path(__file__).resolve().parents[1]

SOURCE_DIRS = ["FDA", "EU", "ICH", "PICS", "WHO", "MFDS", "OTHER"]

def hashed_filename(url: str) -> str:
    """URL 기반 해시+원파일명 일부를 사용해 충돌 방지 파일명 생성"""
    path = unquote(urlparse(url).path)
    base = os.path.basename(path) or "download.pdf"
    base = re.sub(r'[\\/:*?"<>|]+', "_", base).strip()
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"{h}_{base}"[:180]

def ensure_dirs(raw_root: str):
    for d in SOURCE_DIRS:
        os.makedirs(os.path.join(raw_root, d), exist_ok=True)

def _norm(*parts: str) -> str:
    s = " ".join(p for p in parts if p)
    s = unquote(s)
    s = s.replace("%20", " ")
    return re.sub(r"\s+", " ", s).strip().lower()

def classify_source(url: str, label: str | None = None) -> str:
    """
    url, 링크 텍스트, 페이지 제목/부모 컨테이너 일부(라벨)에 기반한 규칙 분류
    규칙 우선순위: FDA > EU > ICH > PICS > WHO > MFDS
    """
    blob = _norm(url, label)

    # ----- FDA -----
    if any(k in blob for k in [
        " fda ", "us fda", "21 cfr", "part 210", "part 211", "part 11",
        "qsr", "part 820", "combination products", "field alert",
        "bioresearch monitoring", "cgmp", "investigational"
    ]):
        return "FDA"

    # ----- EU / EMA / EudraLex -----
    eu_keys = [
        "eu gmp", "eugmp", "eudralex", "volume 4",
        "part i", "part ii", "site master file",
        "annex 1", "annex 2", "annex 3", "annex 4", "annex 5", "annex 6",
        "annex 7", "annex 8", "annex 9", "annex 10", "annex 11", "annex 12",
        "annex 13", "annex 14", "annex 15", "annex 16", "annex 17", "annex 19",
        "annex 21", "annex 22",
        "qualified person", "batch release", "importation of medicinal products",
        "advanced therapy medicinal products", "atmp",
        "investigational medicinal products", "computerised systems",
        "good distribution practice", "gdp"
    ]
    if any(k in blob for k in eu_keys):
        return "EU"

    # ----- ICH -----
    if (" ich " in f" {blob} ") or any(k in blob for k in [
        "ich q", "ich m4",
        " q1", " q2", " q3", " q5", " q6", " q7", " q8", " q9",
        "q10", "q11", "q12", "q13", "q14"
    ]):
        return "ICH"

    # ----- PIC/S -----
    if any(k in blob for k in ["pic/s", "pics ", "pharmaceutical inspection co-operation", "pe 009"]):
        return "PICS"

    # ----- WHO -----
    if any(k in blob for k in ["who gmp", "world health organization", "technical report series", " trs "]):
        return "WHO"

    # ----- MFDS (식약처/국내) -----
    mfds_keys = [
        "mfds", "k-gmp", "kgmp", "korean good manufacturing practices", "kor eng",
        "pharmaceutical facilities standard decree", "enforcement regulation",
        # 한글 키워드
        "식약처", "식품의약품안전처",
        "의약품 제조 및 품질관리 기준", "의약품 제조소 시설기준", "시행규칙", "고시",
        "임상시험용 의약품", "방사성의약품", "생물학적 제제", "의약품 등의 안전에 관한 규칙"
    ]
    if any(k in blob for k in mfds_keys):
        return "MFDS"

    return "OTHER"

def utc_now_iso():
    return datetime.utcnow().isoformat() + "Z"

# 실행 방법
#conda activate [가상환경]
#cd C:\Users\MASTER\Desktop\text_extraction_chunking
#python -m pip install -r requirements.txt

#python extract_and_chunk_pdfs.py --zip "C:\Users\MASTER\Desktop\text_extraction_chunking\data.zip" ^
#  --out "C:\Users\MASTER\Desktop\text_extraction_chunking\chunks.jsonl" ^
#  --backend pypdf --chunk-by regsection --chunk-size 1400 --overlap 120 ^
#  --jurisdiction-from-path

# chunking 완료된 결과물은 json으로 바탕화면에 저장됨


# -*- coding: utf-8 -*-
"""
GMP PDF → Text → Clean → Chunk → JSONL 파이프라인 (v2 + regsection)

핵심
- 기본 추출 백엔드: pypdf 우선, 필요 시 pdfminer.six 폴백
- --backend {auto|pypdf|pdfminer}
- --chunk-by {auto,paragraph,sentence,char,regsection}
- regsection: Annex/Section/§/1.2.3/제n조 등 "조항/섹션" 경계를 인식해 블록 단위 청킹
  (너무 크면 하위 항목 ((1)/(a)/1.) 기준 2차 분할, overlap은 같은 조항 내에서만)

메타데이터 강화
- jurisdiction(EU/FDA/WHO/PIC/S/MFDS 등 경로 기반 추정 옵션)
- doc_date, doc_version(본문/파일명에서 휴리스틱 추정)
- source_url(선택: JSONL/CSV 소스맵로 주입)
- section_id, section_title, normative_strength(MUST/SHOULD/MAY)

실행 예시 (권장)
  python extract_and_chunk_pdfs.py --zip data.zip --out chunks.jsonl \
    --backend pypdf --chunk-by regsection --chunk-size 1400 --overlap 120 \
    --jurisdiction-from-path
"""

from __future__ import annotations
import argparse
import csv
import json
import logging
import hashlib
import os
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

# ---------- Logging ----------
logging.getLogger("pypdf").setLevel(logging.ERROR)

def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def slugify(text: str, maxlen: int = 80) -> str:
    s = re.sub(r"[^\w가-힣\-_. ]+", "", text).strip()
    s = re.sub(r"\s+", "_", s)
    return s[:maxlen] if len(s) > maxlen else s

def stable_hash(text: str, n: int = 16) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:n]

# ---------- Backend ----------
class PDFTextExtractor:
    """
    pypdf → pdfminer 순으로 시도 (기본).
    --backend로 강제 가능.
    """
    def __init__(self, backend: str = "auto"):
        self.backend_pref = backend  # auto|pypdf|pdfminer
        self.has_pypdf = self._check_pypdf()
        self.has_pdfminer = self._check_pdfminer()
        if backend not in {"auto", "pypdf", "pdfminer"}:
            raise ValueError("--backend must be one of auto|pypdf|pdfminer")
        if backend == "pypdf" and not self.has_pypdf:
            raise RuntimeError("pypdf is not installed")
        if backend == "pdfminer" and not self.has_pdfminer:
            raise RuntimeError("pdfminer.six is not installed")
        if backend == "auto" and not (self.has_pypdf or self.has_pdfminer):
            raise RuntimeError("Install pypdf or pdfminer.six")

    def _check_pypdf(self) -> bool:
        try:
            import pypdf  # noqa
            return True
        except Exception:
            return False

    def _check_pdfminer(self) -> bool:
        try:
            import pdfminer  # noqa
            return True
        except Exception:
            return False

    def extract_page_texts(self, pdf_path: Path) -> List[str]:
        """
        pypdf 먼저 → 비어있는 페이지가 너무 많으면 pdfminer 폴백.
        --backend=pdfminer면 pdfminer만 사용, --backend=pypdf면 pypdf만 사용.
        """
        order: List[str]
        if self.backend_pref == "pypdf":
            order = ["pypdf"]
        elif self.backend_pref == "pdfminer":
            order = ["pdfminer"]
        else:
            order = ["pypdf", "pdfminer"]

        last_exc: Optional[Exception] = None
        for be in order:
            try:
                if be == "pypdf" and self.has_pypdf:
                    texts = self._extract_with_pypdf(pdf_path)
                    # 빈 페이지가 너무 많으면 품질 저하로 간주하고 폴백
                    if texts and (sum(1 for t in texts if t and t.strip()) / max(1, len(texts)) >= 0.3):
                        return texts
                if be == "pdfminer" and self.has_pdfminer:
                    texts = self._extract_with_pdfminer(pdf_path)
                    return texts
            except KeyboardInterrupt:
                raise
            except Exception as e:
                last_exc = e
                continue
        if last_exc:
            raise last_exc
        return []

    def _extract_with_pypdf(self, pdf_path: Path) -> List[str]:
        import pypdf
        texts: List[str] = []
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f, strict=False)
            for page in reader.pages:
                try:
                    t = page.extract_text() or ""
                except Exception:
                    t = ""
                texts.append(t)
        return texts

    def _extract_with_pdfminer(self, pdf_path: Path) -> List[str]:
        from pdfminer.high_level import extract_text
        from pdfminer.pdfpage import PDFPage
        texts: List[str] = []
        # 페이지 목록을 먼저 가져와 인덱스로 개별 추출 (무한 대기 방지 일환)
        with open(pdf_path, "rb") as fp:
            page_iter = list(PDFPage.get_pages(fp))
        for i in range(len(page_iter)):
            try:
                t = extract_text(str(pdf_path), page_numbers=[i]) or ""
            except Exception:
                t = ""
            texts.append(t)
        return texts

# ---------- Normalize / Header-Footer ----------
def normalize_text(s: str) -> str:
    s = s.replace("\ufeff", "").replace("\t", " ")
    # 하이픈 줄바꿈 단어 이어붙이기 (영문 중심)
    s = re.sub(r"(\w)-\n(\w)", r"\1\2", s)
    # 다중 공백 축약
    s = re.sub(r"[ \u00A0]{2,}", " ", s)
    # 줄바꿈 정규화
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # 과도한 빈 줄 축약
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def detect_repeating_lines(
    pages: List[str], top_k: int = 3, bottom_k: int = 3, freq_threshold: float = 0.4
):
    from collections import Counter
    head_counter, foot_counter = Counter(), Counter()
    for page in pages:
        lines = [ln.strip() for ln in page.splitlines() if ln.strip()]
        if not lines:
            continue
        heads = lines[:min(top_k, len(lines))]
        foots = lines[-min(bottom_k, len(lines)):]
        for h in heads:
            head_counter[h] += 1
        for f in foots:
            foot_counter[f] += 1
    n_pages = max(1, len(pages))
    head_repeats = {l for l, c in head_counter.items() if c / n_pages >= freq_threshold}
    foot_repeats = {l for l, c in foot_counter.items() if c / n_pages >= freq_threshold}
    return head_repeats, foot_repeats

def remove_headers_footers(pages: List[str]) -> List[str]:
    head_repeats, foot_repeats = detect_repeating_lines(pages)
    cleaned = []
    for page in pages:
        lines = [ln for ln in page.splitlines()]
        while lines and lines[0].strip() in head_repeats:
            lines.pop(0)
        while lines and lines[-1].strip() in foot_repeats:
            lines.pop()
        cleaned.append("\n".join(lines))
    return cleaned

# ---------- Basic splitters ----------
_SENTENCE_SPLIT_REGEX = re.compile(
    r"(?<=[\.!\?。！？])\s+|(?<=\.)\s+|(?<=\))\s+\n|(?<=\])\s+\n"
)

def split_into_paragraphs(text: str) -> List[str]:
    paras = [p.strip() for p in text.split("\n\n")]
    return [p for p in paras if p]

def split_into_sentences(text: str) -> List[str]:
    parts = _SENTENCE_SPLIT_REGEX.split(text)
    merged, buf = [], []
    for part in parts:
        t = part.strip()
        if not t:
            continue
        buf.append(t)
        if sum(len(x) for x in buf) > 80:
            merged.append(" ".join(buf))
            buf = []
    if buf:
        merged.append(" ".join(buf))
    return merged

# ---------- RegSection (규정/조항 인지형) ----------
# 강한 헤딩(섹션 시작) 패턴
RE_STRONG_HEAD = re.compile(
    r"^(?:(Annex|Appendix|Part|Chapter|Section|Clause)\s+([\w\.\-]+)\b\s*(.*)$"
    r"|§\s*([\d\.]+)\b\s*(.*)$"
    r"|([0-9]+(?:\.[0-9]+)+)\b\s*(.+)$"
    r"|제\s*(\d+)\s*(장|절|조)\s*(.*)$)",
    re.IGNORECASE
)
# 너무 큰 섹션의 2차 분할 기준 (하위 항)
RE_SUBCLAUSE = re.compile(r"^(\(\d+\)|\([a-zA-Z]\)|[0-9]+\.)\s+.+")  # (1) (a) 1. 등

@dataclass
class RegUnit:
    section_id: Optional[str]
    section_title: Optional[str]
    text: str
    start_pos: int  # full_text 상 문자 오프셋 기준
    end_pos: int

def split_regsections(full_text: str) -> List[RegUnit]:
    """
    강한 헤딩을 기준으로 섹션 단위 분할.
    너무 큰 섹션은 하위 항으로 재분할.
    """
    lines = full_text.splitlines()
    units: List[RegUnit] = []
    cur_lines: List[str] = []
    cur_id, cur_title = None, None
    pos_offset = 0
    cur_start = 0

    def flush_unit(end_pos: int):
        nonlocal cur_lines, cur_id, cur_title, cur_start
        if not cur_lines:
            return
        text = "\n".join(cur_lines).strip()
        if text:
            units.append(RegUnit(cur_id, cur_title, text, cur_start, end_pos))
        cur_lines = []

    for ln in lines:
        m = RE_STRONG_HEAD.match(ln.strip())
        line_len = len(ln) + 1  # + newline
        if m:
            # 이전 섹션 종료
            flush_unit(pos_offset - 1)
            # ID/제목 파싱
            if m.group(1):  # Annex/Appendix/Part/Chapter/Section/Clause + 코드 + 제목
                cur_id = f"{m.group(1).title()} {m.group(2)}".strip()
                cur_title = (m.group(3) or "").strip()
            elif m.group(4):  # § 1.2.3
                cur_id = f"§ {m.group(4)}"
                cur_title = (m.group(5) or "").strip()
            elif m.group(6):  # 1.2.3 제목
                cur_id = m.group(6)
                cur_title = (m.group(7) or "").strip()
            elif m.group(8):  # 제 n (장|절|조) 제목
                cur_id = f"제{m.group(8)}{m.group(9)}"
                cur_title = (m.group(10) or "").strip()
            else:
                cur_id, cur_title = None, None
            cur_start = pos_offset
            cur_lines = [ln]
        else:
            if not cur_lines:
                # 서문/머리말 블록
                cur_id, cur_title = "PREFACE", None
                cur_start = pos_offset
            cur_lines.append(ln)
        pos_offset += line_len

    flush_unit(pos_offset)

    # 큰 섹션 재분할
    refined: List[RegUnit] = []
    for u in units:
        if len(u.text) <= 1600:
            refined.append(u)
            continue
        sublines = u.text.splitlines()
        cur_sub: List[str] = []
        sub_start_off = u.start_pos
        local_offset = 0

        def flush_sub(end_off: int):
            nonlocal cur_sub, sub_start_off
            if cur_sub:
                t = "\n".join(cur_sub).strip()
                if t:
                    refined.append(RegUnit(u.section_id, u.section_title, t, sub_start_off, end_off))
                cur_sub = []

        for ln in sublines:
            m = RE_SUBCLAUSE.match(ln.strip())
            line_len = len(ln) + 1
            if m and cur_sub:
                flush_sub(u.start_pos + local_offset - 1)
                sub_start_off = u.start_pos + local_offset
                cur_sub = [ln]
            else:
                cur_sub.append(ln)
            local_offset += line_len
        flush_sub(u.start_pos + local_offset)

    return refined

# ---------- Chunking ----------
def chunk_text_units(units: List[RegUnit], chunk_size: int, overlap: int) -> List[RegUnit]:
    """
    각 섹션(RegUnit) 내부에서만 슬라이딩 윈도우 청킹.
    섹션 경계를 넘지 않음.
    """
    chunks: List[RegUnit] = []
    for u in units:
        t = u.text
        if len(t) <= chunk_size * 1.1:
            chunks.append(u)
            continue
        step = chunk_size - overlap if overlap < chunk_size else chunk_size
        i = 0
        while i < len(t):
            sub = t[i : i + chunk_size]
            start_pos = u.start_pos + i
            end_pos = min(u.start_pos + i + len(sub), u.end_pos)
            chunks.append(RegUnit(u.section_id, u.section_title, sub, start_pos, end_pos))
            i += step
    return chunks

def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150, by: str = "auto") -> List[str]:
    """
    기본 모드(문단/문장/문자) 슬라이딩 윈도우 청킹.
    """
    text = normalize_text(text)
    if not text:
        return []
    if by == "paragraph" or (by == "auto" and len(text) > chunk_size * 1.5):
        units = split_into_paragraphs(text)
    elif by == "sentence":
        units = split_into_sentences(text)
    elif by == "char":
        units = [text]
    else:
        # auto: 문단 우선, 큰 문단은 문장 세분화
        units = split_into_paragraphs(text)
        refined = []
        for u in units:
            if len(u) > chunk_size * 1.2:
                refined.extend(split_into_sentences(u))
            else:
                refined.append(u)
        units = refined

    chunks: List[str] = []
    buf = ""
    for u in units:
        if not buf:
            buf = u
        elif len(buf) + 1 + len(u) <= chunk_size:
            buf = f"{buf}\n{u}"
        else:
            chunks.append(buf.strip())
            tail = buf[-overlap:] if overlap > 0 else ""
            buf = (tail + "\n" + u).strip()
    if buf:
        chunks.append(buf.strip())

    # 비상 문자 분할
    final_chunks: List[str] = []
    for ck in chunks:
        if len(ck) <= chunk_size * 1.5:
            final_chunks.append(ck)
        else:
            s = ck
            step = chunk_size - overlap if overlap < chunk_size else chunk_size
            i = 0
            while i < len(s):
                final_chunks.append(s[i : i + chunk_size])
                i += step
    return final_chunks

# ---------- ZIP & Files ----------
def extract_zip_to_dir(zip_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)

def find_pdfs(root: Path) -> List[Path]:
    return sorted([p for p in root.rglob("*.pdf") if p.is_file()])

# ---------- Metadata helpers ----------
def extract_doc_meta(pages: List[str], filename: str) -> Tuple[Optional[str], Optional[str]]:
    """
    앞쪽 페이지/파일명에서 발행일/버전 추정.
    """
    head_text = "\n".join(pages[:3])
    # 날짜: 2020-12-31 / 2020.12.31 / 2020/12/31 / 20 Aug 2023
    m = re.search(
        r"(20\d{2}[./\- ]\d{1,2}[./\- ]\d{1,2}|[0-3]?\d\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20\d{2})",
        head_text,
        re.IGNORECASE,
    )
    date_val = m.group(0) if m else None
    # 버전: Rev 3.1 / Version 2 / ver.1.0
    mv = re.search(r"\b(Rev(?:ision)?|Version|Ver\.?)\s*[:\-]?\s*([A-Za-z]?\d+(?:\.\d+)*)", head_text, re.IGNORECASE)
    ver_val = (mv.group(1) + " " + mv.group(2)) if mv else None
    # 파일명 보조
    if not date_val:
        mf = re.search(r"(20\d{2}[._-]\d{1,2}[._-]\d{1,2}|20\d{2})", filename)
        date_val = mf.group(0) if mf else None
    if not ver_val:
        mvf = re.search(r"(Rev(?:ision)?|Version|Ver)[._ -]*([A-Za-z]?\d+(?:\.\d+)*)", filename, re.IGNORECASE)
        ver_val = (mvf.group(1) + " " + mvf.group(2)) if mvf else None
    return date_val, ver_val

def infer_jurisdiction(path_str: str) -> Optional[str]:
    s = path_str.lower()
    if any(k in s for k in ["eu", "ema"]):
        return "EU"
    if any(k in s for k in ["usfda", "fda", "cfr", "21 cfr", "21cfr"]):
        return "US-FDA"
    if "who" in s:
        return "WHO"
    if "pic" in s:
        return "PIC/S"
    if any(k in s for k in ["mfds", "kfds", "korea"]):
        return "KR-MFDS"
    return None

def label_normative_strength(text: str) -> Optional[str]:
    """
    MUST/SHOULD/MAY 간단 라벨링 (영문/국문 키워드)
    """
    tl = " " + text.lower() + " "
    strong = sum(x in tl for x in [" shall ", " must ", " required ", " require "])
    should = sum(x in tl for x in [" should ", " recommended ", " recommend ", " ought "])
    may = sum(x in tl for x in [" may ", " can ", " optional "])
    # 한글
    strong += sum(x in text for x in ["하여야 한다", "해야 한다", "해야한다", "필수", "의무"])
    should += sum(x in text for x in ["권장", "바람직", "권고"])
    may += sum(x in text for x in ["할 수 있다", "가능"])
    if strong >= should and strong >= may and strong > 0:
        return "MUST"
    if should >= strong and should >= may and should > 0:
        return "SHOULD"
    if may > 0:
        return "MAY"
    return None

# ---------- Output record ----------
@dataclass
class ChunkRecord:
    id: str
    doc_id: str
    source_path: str
    title: str
    jurisdiction: Optional[str]
    doc_date: Optional[str]
    doc_version: Optional[str]
    source_url: Optional[str]
    section_id: Optional[str]
    section_title: Optional[str]
    normative_strength: Optional[str]
    page_start: int
    page_end: int
    chunk_index: int
    text: str

def write_jsonl(path: Path, records: Iterable[ChunkRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(
                json.dumps(
                    {
                        "id": r.id,
                        "doc_id": r.doc_id,
                        "source_path": r.source_path,
                        "title": r.title,
                        "jurisdiction": r.jurisdiction,
                        "doc_date": r.doc_date,
                        "doc_version": r.doc_version,
                        "source_url": r.source_url,
                        "section_id": r.section_id,
                        "section_title": r.section_title,
                        "normative_strength": r.normative_strength,
                        "page_start": r.page_start,
                        "page_end": r.page_end,
                        "chunk_index": r.chunk_index,
                        "text": r.text,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

# ---------- Source map (optional) ----------
def load_source_map(path: Optional[Path]) -> dict:
    """
    JSONL/CSV 지원: key(path|filename|stem) -> {source_url, doc_date, doc_version}
    """
    if not path:
        return {}
    mp: dict = {}
    if path.suffix.lower() == ".jsonl":
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                key = o.get("path") or o.get("filename") or o.get("stem")
                if key:
                    mp[str(key)] = {
                        "source_url": o.get("source_url"),
                        "doc_date": o.get("doc_date"),
                        "doc_version": o.get("doc_version"),
                    }
    elif path.suffix.lower() == ".csv":
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for o in reader:
                key = o.get("path") or o.get("filename") or o.get("stem")
                if key:
                    mp[str(key)] = {
                        "source_url": o.get("source_url"),
                        "doc_date": o.get("doc_date"),
                        "doc_version": o.get("doc_version"),
                    }
    return mp

# ---------- Build per PDF ----------
def build_chunks_for_pdf(
    pdf_path: Path,
    extractor: PDFTextExtractor,
    chunk_size: int,
    overlap: int,
    chunk_by: str,
    jurisdiction_from_path: bool,
    source_map: dict,
) -> List[ChunkRecord]:
    rel_title = pdf_path.stem
    doc_id = f"{slugify(rel_title)}-{stable_hash(str(pdf_path))}"

    try:
        pages = extractor.extract_page_texts(pdf_path)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        log(f"⚠️ 텍스트 추출 실패: {pdf_path.name} ({e})")
        return []

    if not any(p.strip() for p in pages):
        log(f"🔍 OCR 필요 가능성(빈 텍스트): {pdf_path.name}")
        return []

    # 정제 + 헤더/푸터 제거
    pages_norm = [normalize_text(p) for p in pages]
    pages_clean = remove_headers_footers(pages_norm)

    # 페이지 사이에 \n\n 를 넣어 full_text 구성
    if pages_clean:
        full_text = ("\n\n").join(pages_clean).strip()
    else:
        full_text = ""

    # 메타데이터 추정
    doc_date, doc_version = extract_doc_meta(pages_clean, pdf_path.name)
    jurisdiction = infer_jurisdiction(str(pdf_path)) if jurisdiction_from_path else None

    # 외부 소스맵 병합
    url_info = (
        source_map.get(str(pdf_path))
        or source_map.get(pdf_path.name)
        or source_map.get(pdf_path.stem)
        or {}
    )
    source_url = url_info.get("source_url")
    doc_date = url_info.get("doc_date") or doc_date
    doc_version = url_info.get("doc_version") or doc_version

    # 페이지 매핑: full_text에 삽입한 페이지 구분(\n\n) 2글자도 누적에 반영
    page_bounds: List[Tuple[int, int]] = []
    acc = 0
    for i, p in enumerate(pages_clean, 1):
        acc += len(p)
        if i < len(pages_clean):
            acc += 2  # "\n\n"
        page_bounds.append((i, acc))

    def guess_page_range(start_pos: int, end_pos: int) -> Tuple[int, int]:
        def pos_to_page(pos: int) -> int:
            for pg, cumlen in page_bounds:
                if pos <= cumlen:
                    return pg
            return len(page_bounds)
        return pos_to_page(start_pos), pos_to_page(end_pos)

    records: List[ChunkRecord] = []

    if chunk_by == "regsection":
        # 섹션/조항 인지형 분할 → 섹션 내 윈도우 청킹
        units = split_regsections(full_text)
        units = chunk_text_units(units, chunk_size, overlap)
        for idx, u in enumerate(units):
            p_s, p_e = guess_page_range(u.start_pos, u.end_pos)
            chunk_id = f"{doc_id}-{idx:04d}"
            records.append(
                ChunkRecord(
                    id=chunk_id,
                    doc_id=doc_id,
                    source_path=str(pdf_path),
                    title=rel_title,
                    jurisdiction=jurisdiction,
                    doc_date=doc_date,
                    doc_version=doc_version,
                    source_url=source_url,
                    section_id=u.section_id,
                    section_title=u.section_title,
                    normative_strength=label_normative_strength(u.text),
                    page_start=p_s,
                    page_end=p_e,
                    chunk_index=idx,
                    text=u.text,
                )
            )
        return records

    # 기본 모드(문단/문장/문자/auto)
    chunks = chunk_text(full_text, chunk_size=chunk_size, overlap=overlap, by=chunk_by)
    # 오프셋 근사 추정으로 페이지 매핑
    offset = 0
    for idx, ck in enumerate(chunks):
        start_pos = offset
        end_pos = offset + len(ck)
        p_s, p_e = guess_page_range(start_pos, end_pos)
        chunk_id = f"{doc_id}-{idx:04d}"
        records.append(
            ChunkRecord(
                id=chunk_id,
                doc_id=doc_id,
                source_path=str(pdf_path),
                title=rel_title,
                jurisdiction=jurisdiction,
                doc_date=doc_date,
                doc_version=doc_version,
                source_url=source_url,
                section_id=None,
                section_title=None,
                normative_strength=label_normative_strength(ck),
                page_start=p_s,
                page_end=p_e,
                chunk_index=idx,
                text=ck,
            )
        )
        # overlap을 고려한 다음 시작 위치
        offset = end_pos - min(overlap, len(ck))

    return records

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser(description="PDF 텍스트 추출 및 청킹 → JSONL 생성 (v2 + regsection)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--zip", type=str, help="PDF ZIP 경로")
    src.add_argument("--pdf-dir", type=str, help="PDF 폴더 경로")

    ap.add_argument("--workdir", type=str, default="./work", help="ZIP 해제 폴더")
    ap.add_argument("--out", type=str, default="./chunks.jsonl", help="출력 JSONL 경로")
    ap.add_argument("--chunk-size", type=int, default=1400, help="청크 목표 글자 수")
    ap.add_argument("--overlap", type=int, default=120, help="청크 간 겹침(문자)")
    ap.add_argument(
        "--chunk-by",
        type=str,
        default="regsection",
        choices=["auto", "paragraph", "sentence", "char", "regsection"],
        help="청킹 기준",
    )
    ap.add_argument(
        "--backend",
        type=str,
        default="auto",
        choices=["auto", "pypdf", "pdfminer"],
        help="텍스트 추출 백엔드",
    )
    ap.add_argument(
        "--jurisdiction-from-path",
        action="store_true",
        help="경로명으로 관할기관 추정(EU/FDA/WHO/PIC/S/MFDS)",
    )
    ap.add_argument(
        "--source-map",
        type=str,
        default=None,
        help="JSONL/CSV: path|filename|stem -> {source_url, doc_date, doc_version}",
    )
    args = ap.parse_args()

    # 백엔드 준비
    try:
        extractor = PDFTextExtractor(backend=args.backend)
    except Exception as e:
        log(f"❌ 백엔드 초기화 실패: {e}")
        sys.exit(1)

    # 입력 준비
    if args.zip:
        zip_path = Path(args.zip)
        if not zip_path.exists():
            log(f"❌ ZIP 없음: {zip_path}")
            sys.exit(1)
        workdir = Path(args.workdir)
        log(f"📦 ZIP 해제: {zip_path} → {workdir}")
        extract_zip_to_dir(zip_path, workdir)
        pdf_root = workdir
    else:
        pdf_root = Path(args.pdf_dir)
        if not pdf_root.exists():
            log(f"❌ 폴더 없음: {pdf_root}")
            sys.exit(1)

    source_map = load_source_map(Path(args.source_map)) if args.source_map else {}

    pdfs = find_pdfs(pdf_root)
    if not pdfs:
        log("❌ PDF가 없습니다.")
        sys.exit(1)

    log(f"📄 PDF 개수: {len(pdfs)}")
    all_records: List[ChunkRecord] = []
    for i, pdf in enumerate(pdfs, 1):
        log(f"[{i}/{len(pdfs)}] 처리중: {pdf}")
        recs = build_chunks_for_pdf(
            pdf,
            extractor,
            args.chunk_size,
            args.overlap,
            args.chunk_by,
            args.jurisdiction_from_path,
            source_map,
        )
        all_records.extend(recs)
        log(f"   → 청크 {len(recs)}개")

    out_path = Path(args.out)
    write_jsonl(out_path, all_records)
    log(f"✅ 완료: {out_path} (총 청크 {len(all_records)}개)")

if __name__ == "__main__":
    main()

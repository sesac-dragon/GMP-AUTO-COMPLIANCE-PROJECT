import argparse
import json
import os
import re
import zipfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
import hashlib
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import time
from functools import partial

# LangChain imports
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain.embeddings import HuggingFaceEmbeddings


@dataclass
class ChunkRecord:
    """데이터 클래스로 청크 레코드 구조 정의"""
    id: str
    doc_id: str
    source_path: str
    title: str
    jurisdiction: Optional[str]
    doc_date: Optional[str] 
    doc_version: Optional[str]
    section_id: Optional[str]
    section_title: Optional[str]
    page_start: int
    page_end: int
    chunk_index: int
    text: str


class SemanticPDFProcessor:
    """SemanticChunker를 사용한 PDF 처리기"""
    
    def __init__(self, 
                 model_name: str = "jhgan/ko-sroberta-multitask",
                 device: str = 'cpu',  # 병렬처리시 'cpu' 권장
                 breakpoint_threshold_type: str = "percentile",
                 breakpoint_threshold_amount: int = 70):
        """
        초기화 - 병렬처리를 위해 각 프로세스에서 개별 초기화
        """
        self.model_name = model_name
        self.device = device
        self.breakpoint_threshold_type = breakpoint_threshold_type
        self.breakpoint_threshold_amount = breakpoint_threshold_amount
        
        # 지연 초기화 - 실제 사용시에만 로드
        self._embeddings = None
        self._text_splitter = None
    
    @property
    def embeddings(self):
        if self._embeddings is None:
            print(f"[PID {os.getpid()}] Loading embeddings model: {self.model_name}")
            self._embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name,
                encode_kwargs={'normalize_embeddings': False},
                model_kwargs={'device': self.device},
            )
        return self._embeddings
    
    @property
    def text_splitter(self):
        if self._text_splitter is None:
            print(f"[PID {os.getpid()}] Initializing SemanticChunker")
            self._text_splitter = SemanticChunker(
                self.embeddings,
                breakpoint_threshold_type=self.breakpoint_threshold_type,
                breakpoint_threshold_amount=self.breakpoint_threshold_amount,
            )
        return self._text_splitter


# 전역 프로세서 변수 (각 프로세스마다 독립적으로 생성됨)
_global_processor = None

def init_worker(model_name, device, breakpoint_threshold_type, breakpoint_threshold_amount):
    """워커 프로세스 초기화 함수"""
    global _global_processor
    _global_processor = SemanticPDFProcessor(
        model_name=model_name,
        device=device,
        breakpoint_threshold_type=breakpoint_threshold_type,
        breakpoint_threshold_amount=breakpoint_threshold_amount
    )


def clean_text(text: str) -> str:
    """텍스트 정규화 및 정리"""
    text = text.replace('\ufeff', '').replace('\t', ' ')
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    text = re.sub(r'[ \u00A0]{2,}', ' ', text)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_metadata(text: str, filename: str) -> Dict[str, Optional[str]]:
    """파일명과 텍스트에서 메타데이터 추출"""
    date_pattern = r'(20\d{2}[./\-]\d{1,2}[./\-]\d{1,2}|[0-3]?\d\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20\d{2})'
    date_match = re.search(date_pattern, text[:1000], re.IGNORECASE)
    doc_date = date_match.group(0) if date_match else None
    
    if not doc_date:
        filename_date = re.search(r'(20\d{2}[._-]\d{1,2}[._-]\d{1,2}|20\d{2})', filename)
        doc_date = filename_date.group(0) if filename_date else None
    
    version_pattern = r'\b(Rev(?:ision)?|Version|Ver\.?)\s*[:\-]?\s*([A-Za-z]?\d+(?:\.\d+)*)'
    version_match = re.search(version_pattern, text[:1000], re.IGNORECASE)
    doc_version = f"{version_match.group(1)} {version_match.group(2)}" if version_match else None
    
    if not doc_version:
        filename_version = re.search(version_pattern, filename, re.IGNORECASE)
        doc_version = f"{filename_version.group(1)} {filename_version.group(2)}" if filename_version else None
    
    return {
        'doc_date': doc_date,
        'doc_version': doc_version
    }


def infer_jurisdiction(path_str: str) -> Optional[str]:
    """경로명으로부터 관할기관 추정"""
    path_lower = path_str.lower()
    
    if any(keyword in path_lower for keyword in ['eu', 'ema', 'european']):
        return 'EU'
    elif any(keyword in path_lower for keyword in ['fda', 'usfda', 'cfr', '21cfr']):
        return 'US-FDA'  
    elif 'who' in path_lower:
        return 'WHO'
    elif 'pic' in path_lower:
        return 'PIC/S'
    elif any(keyword in path_lower for keyword in ['mfds', 'kfda', 'korea']):
        return 'KR-MFDS'
    elif any(keyword in path_lower for keyword in ['ich', 'international']):
        return 'ICH'
    else:
        return None


def create_doc_id(title: str, path: str) -> str:
    """문서 ID 생성 (제목 + 경로 해시)"""
    slug = re.sub(r'[^\w가-힣\-_. ]+', '', title).strip()
    slug = re.sub(r'\s+', '_', slug)[:50]
    path_hash = hashlib.sha1(path.encode('utf-8')).hexdigest()[:12]
    return f"{slug}-{path_hash}"


def estimate_page_range(chunk_text: str, full_text: str, total_pages: int, chunk_index: int, all_chunks: List[str]) -> tuple:
    """청크의 페이지 범위를 추정"""
    chunk_start_pos = full_text.find(chunk_text[:100])
    
    if chunk_start_pos == -1:
        total_chunks = len(all_chunks)
        page_start = max(1, int((chunk_index / total_chunks) * total_pages) + 1)
        page_end = min(total_pages, int(((chunk_index + 1) / total_chunks) * total_pages) + 1)
        return page_start, page_end
    
    chunk_end_pos = chunk_start_pos + len(chunk_text)
    start_ratio = chunk_start_pos / len(full_text)
    end_ratio = chunk_end_pos / len(full_text)
    
    page_start = max(1, int(start_ratio * total_pages) + 1)
    page_end = min(total_pages, int(end_ratio * total_pages) + 1)
    
    return page_start, page_end


def process_single_pdf_worker(pdf_path_str: str) -> List[ChunkRecord]:
    """워커 프로세스에서 실행되는 단일 PDF 처리 함수"""
    global _global_processor
    
    pdf_path = Path(pdf_path_str)
    print(f"[PID {os.getpid()}] Processing: {pdf_path.name}")
    
    try:
        start_time = time.time()
        
        # PyPDFLoader로 PDF 로드
        loader = PyPDFLoader(str(pdf_path))
        pages = loader.load()
        
        if not pages:
            print(f"[PID {os.getpid()}] Warning: No pages found in {pdf_path.name}")
            return []
        
        # 전체 텍스트 결합 및 정리
        full_text = '\n\n'.join([clean_text(page.page_content) for page in pages])
        
        if not full_text.strip():
            print(f"[PID {os.getpid()}] Warning: No text content in {pdf_path.name}")
            return []
        
        # 메타데이터 추출
        title = pdf_path.stem
        doc_id = create_doc_id(title, str(pdf_path))
        metadata = extract_metadata(full_text, pdf_path.name)
        jurisdiction = infer_jurisdiction(str(pdf_path))
        
        # SemanticChunker로 의미적 청킹 수행
        chunks = _global_processor.text_splitter.split_text(full_text)
        
        # ChunkRecord 생성
        records = []
        for idx, chunk in enumerate(chunks):
            page_start, page_end = estimate_page_range(
                chunk, full_text, len(pages), idx, chunks
            )
            
            record = ChunkRecord(
                id=f"{doc_id}-{idx:04d}",
                doc_id=doc_id,
                source_path=str(pdf_path),
                title=title,
                jurisdiction=jurisdiction,
                doc_date=metadata['doc_date'],
                doc_version=metadata['doc_version'],
                section_id=None,
                section_title=None,
                page_start=page_start,
                page_end=page_end,
                chunk_index=idx,
                text=chunk.strip()
            )
            records.append(record)
        
        elapsed = time.time() - start_time
        avg_size = sum(len(chunk) for chunk in chunks) / len(chunks) if chunks else 0
        print(f"[PID {os.getpid()}] {pdf_path.name}: {len(records)} chunks, {elapsed:.1f}s, avg size: {avg_size:.0f}")
        
        return records
        
    except Exception as e:
        print(f"[PID {os.getpid()}] Error processing {pdf_path.name}: {e}")
        return []


def find_pdfs(directory: Path) -> List[Path]:
    """디렉토리에서 PDF 파일 찾기"""
    return sorted([p for p in directory.rglob("*.pdf") if p.is_file()])


def extract_zip(zip_path: Path, extract_to: Path) -> None:
    """ZIP 파일 압축 해제"""
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)


def write_jsonl(output_path: Path, records: List[ChunkRecord]) -> None:
    """JSONL 파일로 저장"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for record in records:
            record_dict = asdict(record)
            f.write(json.dumps(record_dict, ensure_ascii=False) + '\n')


def process_pdfs_parallel(pdf_files: List[Path],
                         model_name: str = "jhgan/ko-sroberta-multitask",
                         device: str = 'cpu',
                         breakpoint_threshold_type: str = "percentile",
                         breakpoint_threshold_amount: int = 70,
                         max_workers: int = None) -> List[ChunkRecord]:
    """병렬로 PDF 파일들 처리"""
    
    if max_workers is None:
        max_workers = min(mp.cpu_count(), len(pdf_files))
    
    print(f"Processing {len(pdf_files)} PDFs with {max_workers} workers")
    print(f"Model: {model_name}, Device: {device}")
    
    start_time = time.time()
    all_records = []
    
    # ProcessPoolExecutor 사용
    with ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=init_worker,
        initargs=(model_name, device, breakpoint_threshold_type, breakpoint_threshold_amount)
    ) as executor:
        
        # PDF 경로를 문자열로 변환 (Path 객체는 직렬화 문제가 있을 수 있음)
        pdf_paths_str = [str(pdf_path) for pdf_path in pdf_files]
        
        # 작업 제출
        future_to_pdf = {
            executor.submit(process_single_pdf_worker, pdf_path): pdf_path 
            for pdf_path in pdf_paths_str
        }
        
        # 결과 수집
        completed_count = 0
        for future in as_completed(future_to_pdf):
            pdf_path = future_to_pdf[future]
            try:
                records = future.result()
                all_records.extend(records)
                completed_count += 1
                
                elapsed = time.time() - start_time
                print(f"Progress: {completed_count}/{len(pdf_files)} PDFs completed, "
                      f"Elapsed: {elapsed:.1f}s, "
                      f"Total chunks: {len(all_records)}")
                
            except Exception as e:
                print(f"Error processing {pdf_path}: {e}")
    
    total_time = time.time() - start_time
    print(f"All processing completed in {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"Average time per PDF: {total_time/len(pdf_files):.1f}s")
    
    return all_records


# Jupyter notebook friendly functions
def process_zip_file_parallel(zip_path: str, 
                             output_path: str = 'semantic_chunks_parallel.jsonl',
                             model_name: str = "jhgan/ko-sroberta-multitask",
                             device: str = 'cpu',  # 병렬처리시 'cpu' 권장
                             breakpoint_threshold_type: str = "percentile",
                             breakpoint_threshold_amount: int = 70,
                             max_workers: int = None,
                             workdir: str = './temp_extract'):
    """병렬 처리로 ZIP 파일 처리 (노트북용)"""
    zip_path = Path(zip_path)
    if not zip_path.exists():
        print(f"Error: ZIP file not found: {zip_path}")
        return
    
    workdir = Path(workdir)
    print(f"Extracting ZIP: {zip_path} -> {workdir}")
    extract_zip(zip_path, workdir)
    
    # PDF 파일 찾기
    pdf_files = find_pdfs(workdir)
    if not pdf_files:
        print("Error: No PDF files found")
        return
    
    print(f"Found {len(pdf_files)} PDF files")
    
    # 병렬로 모든 PDF 처리
    all_records = process_pdfs_parallel(
        pdf_files=pdf_files,
        model_name=model_name,
        device=device,
        breakpoint_threshold_type=breakpoint_threshold_type,
        breakpoint_threshold_amount=breakpoint_threshold_amount,
        max_workers=max_workers
    )
    
    # 결과 저장
    output_path = Path(output_path)
    write_jsonl(output_path, all_records)
    
    print(f"\nCompleted! {len(all_records)} chunks saved to {output_path}")
    
    # 임시 디렉토리 정리
    if workdir.exists():
        import shutil
        shutil.rmtree(workdir)
        print(f"Cleaned up temporary directory: {workdir}")


def process_pdf_directory_parallel(pdf_dir: str, 
                                  output_path: str = 'semantic_chunks_parallel.jsonl',
                                  model_name: str = "jhgan/ko-sroberta-multitask",
                                  device: str = 'cpu',
                                  breakpoint_threshold_type: str = "percentile",
                                  breakpoint_threshold_amount: int = 70,
                                  max_workers: int = None):
    """병렬 처리로 PDF 디렉토리 처리 (노트북용)"""
    pdf_source = Path(pdf_dir)
    if not pdf_source.exists():
        print(f"Error: Directory not found: {pdf_source}")
        return
    
    # PDF 파일 찾기
    pdf_files = find_pdfs(pdf_source)
    if not pdf_files:
        print("Error: No PDF files found")
        return
    
    print(f"Found {len(pdf_files)} PDF files")
    
    # 병렬로 모든 PDF 처리
    all_records = process_pdfs_parallel(
        pdf_files=pdf_files,
        model_name=model_name,
        device=device,
        breakpoint_threshold_type=breakpoint_threshold_type,
        breakpoint_threshold_amount=breakpoint_threshold_amount,
        max_workers=max_workers
    )
    
    # 결과 저장
    output_path = Path(output_path)
    write_jsonl(output_path, all_records)
    
    print(f"\nCompleted! {len(all_records)} chunks saved to {output_path}")


# 배치 처리 함수 (메모리 효율적)
def process_pdfs_in_batches(pdf_files: List[Path],
                           batch_size: int = 4,
                           **kwargs) -> List[ChunkRecord]:
    """배치 단위로 PDF 처리 (메모리 절약)"""
    all_records = []
    total_batches = (len(pdf_files) + batch_size - 1) // batch_size
    
    for i in range(0, len(pdf_files), batch_size):
        batch = pdf_files[i:i + batch_size]
        batch_num = i // batch_size + 1
        
        print(f"\nProcessing batch {batch_num}/{total_batches} ({len(batch)} PDFs)")
        
        batch_records = process_pdfs_parallel(batch, **kwargs)
        all_records.extend(batch_records)
        
        print(f"Batch {batch_num} completed. Total chunks so far: {len(all_records)}")
    
    return all_records


# 사용 예시
if __name__ == "__main__":
    # 예시 1: ZIP 파일 처리
    process_zip_file_semantic(
        zip_path="/Users/song/Desktop/workspace/final/data/raw.zip",
        output_path="semantic_chunks.jsonl",
        breakpoint_threshold_amount=70  # 70th percentile에서 분할
    )
    
    # # 예시 2: PDF 디렉토리 처리
    # process_pdf_directory_semantic(
    #     pdf_dir="./pdfs",
    #     output_path="semantic_chunks.jsonl",
    #     breakpoint_threshold_type="percentile",
    #     breakpoint_threshold_amount=80  # 더 큰 청크를 원하면 값을 높임
    # )
    
    print("SemanticChunker PDF Processor ready!")
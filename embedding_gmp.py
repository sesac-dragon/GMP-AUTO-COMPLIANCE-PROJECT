
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
import time
from tqdm import tqdm
import uuid
import re

# LangChain and Chroma imports
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.schema import Document

class GMPTermsHandler:
    """GMP 용어집 처리기 (하드코딩된 용어 리스트)"""
    
    def __init__(self):
        self.gmp_terms = [
            # 영어 GMP 용어
            "Active pharmaceutical ingredient", "API", "Acceptance Criteria", "Accuracy", 
            "Action level", "Active ingredient", "Actual yield", "Advanced Electronic Signature",
            "Air-Lock", "Airlock", "Alert limits", "Analytical Procedure", "Antimicrobial",
            "Antiseptic", "Application", "Application-Specific Software", "Aseptic filling",
            "Aseptic techniques and manipulations", "Authorized person", "Automated System",
            "Barrier", "Batch", "Lot", "Batch Number", "Lot Number", "Batch records",
            "Bioburden", "Biocide", "Biological Indicator", "Bulk Product", "Calibration",
            "Change Control", "Change Management", "Chemical germicide", "Class of Cleanliness",
            "Clean Area", "Clean Zone", "Cleaning Validation", "Cleanroom", "Colony Forming Unit",
            "CFU", "Commercial off-the-shelf", "COTS", "Component", "Compounding",
            "Computer Hardware", "Computer System", "Computerised System", "Concurrent Validation",
            "Configuration", "Configuration Management", "Contained Area", "Containment",
            "Contamination", "Content or Potency", "Continual Improvement", "Control Number",
            "Contract Manufacturer", "Control Strategy", "Controlled Area", "Corrective Action",
            "Critical", "Critical Process Parameter", "Critical Process", "Critical equipment",
            "Critical operation", "Critical surfaces", "Critical zone", "Critical Area",
            "Cross-Contamination", "D value", "Debugging", "Decision Maker", "Decontamination",
            "Depyrogenation", "Design Space", "Design qualification", "DQ", "Detectability",
            "Detection Limit", "Deviation", "Disinfectant", "Disinfection", "Drug",
            "Drug Substance", "Drug Product", "Dynamic", "Electronic Signature",
            "Embedded System", "Endotoxin", "Environment", "Environmental monitoring programme",
            "Executive Program", "Expected", "Expiry Date", "Expiration Date", "Feedback",
            "Finished Product", "Firmware", "Functional Requirement", "Functional Specifications",
            "Functional Testing", "Good Manufacturing Practice for Medicinal Products", "GMP",
            "HEPA filter", "HVAC", "Hardware Acceptance Test Specification", "Harm", "Hazard",
            "IT Infrastructure", "Identification Test", "Impurity", "Impurity Profile",
            "In-Process Control", "Process Control", "In-process material", "Inactive ingredient",
            "Installation Qualification", "IQ", "Integration testing", "Integrity test",
            "Interface", "Intermediate", "Intermediate Precision", "Intermediate Product",
            "Intervention", "Isolator", "Knowledge Management", "Laminar flow",
            "Large-volume parenterals", "Legacy Computerised Systems", "Life Cycle Concept",
            "Life cycle", "Linearity", "Liquifiable Gases", "Loop Testing", "Manifold",
            "Manufacture", "Manufacturer", "Marketing authorization", "Master formula",
            "Master record", "Material", "Media fills", "Medicinal Product", "Microbicide",
            "Mother Liquor", "Network", "Nonfiber releasing filter", "Operating Environment",
            "Operating System", "Operational Qualification", "OQ", "Operator",
            "Out of Specification", "Outsourced Activities", "Overkill sterilization",
            "Packaging", "Packaging Material", "Parametric Release", "Performance Indicators",
            "Performance Qualification", "PQ", "Pharmaceutical", "Pharmaceutical Isolator",
            "Pharmaceutical Quality System", "PQS", "Precision", "Preventive Action",
            "Primary", "Procedure", "Procedures", "Process Aids", "Process Validation",
            "Process owner", "Product", "Product Lifecycle", "Product Realisation",
            "Production", "Prospective Validation", "Proven Acceptable Range",
            "Public Key Infrastructure", "Purity Test", "Pyrogen", "Qualification",
            "Quality", "Quality Assurance", "Quality Attribute", "Quality Control",
            "Quality Manual", "Quality Objectives", "Quality Planning", "Quality Policy",
            "Quality Risk Management", "Quality System", "Quality Unit", "Quality Units",
            "Quality by Design", "Quality control unit", "Quantitation Limit", "Quarantine",
            "Radiopharmaceutical", "Range", "Raw Data", "Raw Material",
            "Real Time Release Testing", "Reference Standard", "Reference sample",
            "Regulated User", "Release", "Repeatability", "Representative sample",
            "Reprocessing", "Reproducibility", "Requirements", "Retention sample",
            "Retest Date", "Retrospective Validation", "Return", "Revalidation",
            "Re-Validation", "Reworking", "Risk", "Risk Acceptance", "Risk Analysis",
            "Risk Assessment", "Risk Communication", "Risk Control", "Risk Evaluation",
            "Risk Identification", "Risk Management", "Risk Reduction", "Risk Review",
            "Robustness", "Sampling frequency", "Secondary", "Security", "Self-contained area",
            "Senior Management", "Severity", "Shift", "Signature", "signed", "Signed",
            "Simulated", "Solvent", "Source Code", "Specification", "Specificity",
            "Sporicidal process", "Sporocide", "Stakeholder", "Standalone System",
            "Standard operating procedure", "SOP", "Starting Material", "State of Control",
            "Sterile", "Sterile Area", "Sterile Product", "Sterilisation", "Sterility",
            "Sterility assurance level", "SAL", "Sterility test", "Sterilization",
            "Sterilizing grade filter", "Strength", "Structural Integrity", "Software",
            "Structural Testing", "System", "System Acceptance Test Specification",
            "System Software", "System Specification", "System owner", "Target Product Profile",
            "Terminal sterilization", "Theoretical", "Theoretical yield", "Third Party",
            "Trend", "ULPA filter", "Unidirectional flow", "Unplanned Change",
            "Emergency Change", "User", "Utility Software", "Validation",
            "Validation Protocol", "Validation Plan", "Validation Report",
            "Validation Master Plan", "VMP", "Vent filter", "Worst Case", "Yield",
            "System Suitability", "System Suitability Testing",
        # 한국어 GMP 용어
            "가공", "간섭", "강도", "파라메트릭릴리스", "매개변수출하승인", "개선조치",
            "검증된허용범위", "검체채취주기", "검출능력", "검출한계", "격리", "결정책임자",
            "경고한계", "경향", "계", "계획되지않은", "비상", "고성능공기필터",
            "고성능미립자공기필터", "고위경영자", "공개키기반구조", "공기조화장치",
            "공정능력", "공정밸리데이션", "공정보조제", "공정중반응물질", "공정관리",
            "공정제어", "관리상태", "관리전략", "관리구역", "관리번호", "교대", "교정",
            "교차오염", "구성", "구성설정", "구조적무결성", "구조적테스트", "구조적인검증",
            "규격", "기능규격서", "기능시험", "기능적요구사항", "기대생산량", "기록원본",
            "기존컴퓨터화시스템", "기준", "기준일탈", "기초자료", "납품물", "내독소",
            "내장형시스템", "네트워크", "다기관", "단일방향류", "대용량주사제", "대조",
            "대표검체", "독립형시스템", "동시적밸리데이션", "디버깅", "오류수정",
            "디자인스페이스", "보관", "라이프사이클", "라이프사이클개념", "로트",
            "로트번호", "루프시험", "리스크", "리스크평가", "리스크경영", "리스크허용",
            "마스터기록", "맞춤형", "멸균", "무균", "멸균법", "멸균도", "모액", "모의제품",
            "무균공정용산업아이솔레이터", "무균기술및조작법", "무균충전", "무균구역",
            "무균보증시스템", "무균복착용적격성평가", "무균성", "무균성보증수준",
            "무균시험법", "무균제품", "미생물부하", "밀폐", "밀폐구역", "봉쇄구역",
            "반복성", "반제품", "반품", "발열성물질", "발열성물질제거", "방부제",
            "방사성의약품", "배리어", "배지성능시험", "배지충전", "배치", "배치번호",
            "배합", "밸리데이션", "밸리데이션결과보고서", "밸리데이션실시계획서",
            "밸리데이션종합계획서", "벌크제품", "범위", "법적사용자", "벤트필터",
            "변경", "변경매니지먼트", "변경관리", "보관용검체", "보안", "보존품",
            "봉쇄", "불순물", "불순물프로필", "불활성성분", "사용기간", "사용자",
            "살균제", "살상제", "살상물제", "상용소프트웨어", "상용제품", "생데이터",
            "생물지표", "생물학적지표", "생물인자", "생물학적인자", "생물제너레이터",
            "생산", "서명", "설계영역", "설계에의한품질", "설계적격성평가", "설정관리",
            "구성관리", "설치적격성평가", "섬유", "섬유를방출하지않는필터", "성과지표",
            "성능적격성평가", "성분", "세척밸리데이션", "소독", "소독약", "소독제",
            "소스코드", "수득량", "수량", "수율", "수율관리기준", "수탁제조업자",
            "순도시험", "순환시험", "시방서", "시스템", "시스템규격", "시스템소프트웨어",
            "시스템승인시험규격", "시스템책임자", "시정조치", "시험방법", "실생산량",
            "실시간출하승인시험", "실행프로그램", "실험실간정밀성", "실험실내정밀성",
            "심각성", "아웃소싱활동", "아이솔레이터", "액화성가스", "약제",
            "어플리케이션", "어플리케이션특정용도의소프트웨어", "업무책임자",
            "에어로크", "엔도톡신", "역가", "예방조치", "예측적밸리데이션",
            "오버킬멸균공정", "오염", "오염제거", "완건성", "완성시험", "완전성시험",
            "완제의약품", "완제품", "요구", "요구사항", "용매", "용제", "운영시스템",
            "운영체제", "운영환경", "운전자", "운전적격성평가", "원료", "원료약품",
            "원료의약품", "원료의약품출발물질", "원본자료", "원자재", "위해",
            "위해감소", "위해검토", "위해관리", "위해분석", "위해성평가", "위해요소",
            "위해정보교환", "위해평가", "위해확인", "위험도", "유틸리티소프트웨어",
            "유효기한", "유효성분", "의약품", "의약품제조및품질관리기준",
            "의약품의제조", "이론생산량", "이론수량", "이론수율의백분율",
            "이해관계자", "인터페이스", "일탈", "자기밀폐구역", "자동화시스템",
            "작업상태", "장벽", "재가공", "재밸리데이션", "재시험날짜", "재작업",
            "재처리", "적격성평가", "적합기준", "전실", "전자서명", "절차서",
            "정량한계", "정밀성", "정산", "정확성", "제3자", "제균급필터",
            "제약아이솔레이터", "제약품질시스템", "제제", "제조", "제조기록서",
            "제조단위", "제조단위기록서", "제조번호", "제조업", "제조업자",
            "제품구현", "제품수명", "제품수명개념", "제품표준서", "조사", "조치수준",
            "주성분", "중간물질", "중간제품", "중간체", "중대성", "중요공정변수",
            "중요구역", "중요조작작업", "중요지역", "중요표면", "중요품질특성",
            "중요공정또는중요기계설비", "중요한", "지속적개선", "지식관리", "직선성",
            "참고품", "첨가제", "첨단전자서명", "청정등급", "청정실", "청정지역",
            "체계", "촉진요소", "최악조건", "최종멸균", "최종제품", "출발물질",
            "출하승인책임자", "층류", "컴퓨터시스템", "컴퓨터하드웨어", "컴퓨터화시스템",
            "콜로니형성단위", "탁송물", "배송물", "탈파이로젠", "통기구필터", "통합시험",
            "특이성", "파라메트릭릴리스", "판매승인", "펌웨어", "포자살균공정",
            "포자살균제", "포장", "포장자재", "표준작업지침서", "품질", "품질계획",
            "품질목표", "품질목표제품프로필", "품질보증", "품질위해요소관리",
            "품질관리", "품질관리부서", "품질리스크관리", "품질매뉴얼", "품질부서",
            "품질시스템", "품질체계", "프로세스능력", "피드백", "피드포워드",
            "필요요건", "하드웨어설계규격서", "하드웨어허용시험규격서", "함량",
            "함량또는역가시험", "항균제", "허용기준치", "혁신", "혼합조판인쇄라벨",
            "화학살균제", "확인시험", "환경모니터링프로그램", "환경설정", "활성성분",
            "회고적밸리데이션", "회수", "시스템적합성", "시스템적합성시험",
            "품질관리부", "품질보증부", "원부자재", "입출고관리", "실험실분석장비",
            "일반관리", "인수검사", "외관검사"
        ]
    
    
        self.term_mapping = {
            "Active pharmaceutical ingredient": ["API"],
            "Batch": ["Lot"],
            "Batch Number": ["Lot Number", "control number"],
            "Design qualification": ["DQ"],
            "Installation Qualification": ["IQ"],
            "Operational Qualification": ["OQ"],
            "Performance Qualification": ["PQ"],
            "Standard operating procedure": ["SOP"],
            "Quality Control": ["QC", "품질관리", "품질관리부"],
            "Quality Assurance": ["QA", "품질보증", "품질보증부"],
            "System Suitability": ["System Suitability Testing", "시스템적합성", "시스템적합성시험"],
            "파라메트릭릴리스": ["매개변수출하승인"],
            "로트": ["로트번호", "배치", "배치번호"],
            "멸균": ["무균"],
            "생물지표": ["생물학적지표"],
            "설정관리": ["구성관리"],
            "원부자재": ["원자재", "원료"]
        }
    
    def is_gmp_term(self, text: str) -> bool:
        """텍스트가 GMP 용어인지 확인"""
        text_lower = text.lower()
        return any(term.lower() == text_lower for term in self.gmp_terms)
    
    def get_synonyms(self, term: str) -> List[str]:
        """특정 용어의 동의어 찾기"""
        # 메인 용어인 경우
        if term in self.term_mapping:
            return self.term_mapping[term]
        
        # 동의어인 경우 메인 용어와 다른 동의어들 찾기
        for main_term, synonym_list in self.term_mapping.items():
            if term in synonym_list:
                return [main_term] + [s for s in synonym_list if s != term]
        
        return []


class GMPEmbedder:
    """GMP 문서 임베딩 생성기 (Chroma 기반)"""
    
    def __init__(self, 
                 model_name: str = "jhgan/ko-sroberta-multitask",
                 device: str = 'cpu'):
        self.model_name = model_name
        self.device = device
        
        # GMP 용어 처리기 초기화
        self.terms_handler = GMPTermsHandler()
        
        print(f"Loading embeddings model: {model_name}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            encode_kwargs={'normalize_embeddings': True},
            model_kwargs={'device': device},
        )
        print("Model loaded successfully!")
        print(f"GMP terms loaded: {len(self.terms_handler.gmp_terms)} terms")
    
    def load_chunks_from_jsonl(self, jsonl_path: str) -> List[Dict[str, Any]]:
        """JSONL 파일에서 청크 데이터 로드"""
        chunks = []
        
        print(f"Loading chunks from: {jsonl_path}")
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in tqdm(f, desc="Loading chunks"):
                chunk_data = json.loads(line.strip())
                chunks.append(chunk_data)
        
        print(f"Loaded {len(chunks)} chunks")
        return chunks
    
    def create_documents(self, chunks: List[Dict[str, Any]]) -> List[Document]:
        """청크 데이터를 LangChain Document로 변환"""
        documents = []
        
        for chunk in tqdm(chunks, desc="Creating documents"):
            # 메타데이터에서 None 값을 빈 문자열로 변환 (Chroma 호환성)
            metadata = {
                "chunk_id": chunk["id"],
                "doc_id": chunk["doc_id"],
                "source_path": chunk["source_path"],
                "title": chunk["title"],
                "jurisdiction": chunk.get("jurisdiction", ""),
                "doc_date": chunk.get("doc_date", ""),
                "doc_version": chunk.get("doc_version", ""),
                "section_id": chunk.get("section_id", ""),
                "section_title": chunk.get("section_title", ""),
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
                "chunk_index": chunk["chunk_index"]
            }
            
            # None 값을 빈 문자열로 변환
            for key, value in metadata.items():
                if value is None:
                    metadata[key] = ""
            
            doc = Document(
                page_content=chunk["text"],
                metadata=metadata
            )
            documents.append(doc)
        
        return documents
    
    def create_chroma_db(self, 
                        documents: List[Document],
                        collection_name: str = "gmp_documents_semantic",
                        persist_directory: str = "./chroma_db_gmp") -> Chroma:
        """Chroma 벡터 데이터베이스 생성 (문서만)"""
        
        print(f"Creating Chroma database with {len(documents)} documents...")
        print(f"Collection: {collection_name}")
        print(f"Persist directory: {persist_directory}")
        
        start_time = time.time()
        
        # Chroma 데이터베이스 생성
        vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            collection_name=collection_name,
            persist_directory=persist_directory
        )
        
        # 데이터베이스 영구 저장
        vectorstore.persist()
        
        elapsed_time = time.time() - start_time
        print(f"Chroma database created in {elapsed_time:.2f}s")
        
        return vectorstore
    
    def save_config(self, 
                   chunks: List[Dict[str, Any]], 
                   collection_name: str,
                   persist_directory: str):
        """설정 정보 저장"""
        
        config = {
            "model_name": self.model_name,
            "device": self.device,
            "collection_name": collection_name,
            "persist_directory": persist_directory,
            "num_chunks": len(chunks),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "jurisdictions": {}
        }
        
        # 문서 타입별 통계
        for chunk in chunks:
            jurisdiction = chunk.get("jurisdiction", "unknown")
            if jurisdiction:
                config["jurisdictions"][jurisdiction] = config["jurisdictions"].get(jurisdiction, 0) + 1
        
        config_file = Path(persist_directory) / "config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"Config saved to: {config_file}")
        return config
    
    def process_jsonl_to_chroma(self, 
                               jsonl_path: str = "semantic_chunks.jsonl",
                               collection_name: str = "gmp_documents_semantic",
                               persist_directory: str = "./chroma_db_gmp"):
        """JSONL 파일을 읽어서 Chroma DB 생성하는 전체 프로세스"""
        
        # 1. 청크 데이터 로드
        chunks = self.load_chunks_from_jsonl(jsonl_path)
        
        # 2. Document 객체로 변환
        documents = self.create_documents(chunks)
        
        # 3. Chroma DB 생성 (문서만)
        vectorstore = self.create_chroma_db(
            documents, 
            collection_name=collection_name,
            persist_directory=persist_directory
        )
        
        # 4. 설정 저장
        config = self.save_config(chunks, collection_name, persist_directory)
        
        print("\n=== Processing Complete ===")
        print(f"Document chunks processed: {len(chunks)}")
        print(f"GMP terms available: {len(self.terms_handler.gmp_terms)} terms (hardcoded)")
        print(f"Collection name: {collection_name}")
        print(f"Persist directory: {persist_directory}")
        
        return vectorstore
    
def main_embedding_only():
    embedder = GMPEmbedder()
    """임베딩 생성 실행"""
    print("\nProcessing general GMP documents...")
    embedder.process_jsonl_to_chroma(
        jsonl_path="semantic_chunks.jsonl",
        collection_name="gmp_documents_semantic",
        persist_directory="./chroma_db_gmp"
    )
# 주피터 노트북에서 실행
if __name__ == "__main__":
    main_embedding_only()
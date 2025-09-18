import os
from typing import List, Dict
from dataclasses import dataclass
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.chat_models import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()

@dataclass
class GapAnalysisResult:
    sop_content: str
    gmp_content: str
    gap_type: str
    severity: str
    original_text: str 
    sources: List[str]

class SOPGMPAnalyzer:
    def __init__(self, sop_vector_path: str, gmp_vector_path: str):
        """사용된 벡터 디비 파일 : 전처리 + 시멘틱 청킹"""
        print(f"SOP 벡터 DB 경로: {sop_vector_path}")
        print(f"GMP 벡터 DB 경로: {gmp_vector_path}")
        
        print("임베딩 모델 로딩 중...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="jhgan/ko-sroberta-multitask",
            encode_kwargs={'normalize_embeddings': True},
            model_kwargs={'device': 'cpu'},
        )
        
        try:
            self.sop_vectorstore = Chroma(
                persist_directory=sop_vector_path,
                embedding_function=self.embeddings,
                collection_name="sop_documents_semantic"
            )
            print("SOP 벡터 DB 로드 성공")
        except Exception as e:
            print(f"SOP 벡터 DB 로드 실패: {e}")
            self.sop_vectorstore = None
        
        try:
            self.gmp_vectorstore = Chroma(
                persist_directory=gmp_vector_path,
                embedding_function=self.embeddings,
                collection_name="gmp_documents_semantic"
            )
            print("GMP 벡터 DB 로드 성공")
        except Exception as e:
            print(f"GMP 벡터 DB 로드 실패: {e}")
            self.gmp_vectorstore = None
        
        self.llm = ChatOpenAI(temperature=0, model="gpt-4")
        self.check_status()
    
    def check_status(self):
        if self.sop_vectorstore:
            sop_count = self.sop_vectorstore._collection.count()
            print(f"SOP 문서 청크 수: {sop_count}")
        
        if self.gmp_vectorstore:
            gmp_count = self.gmp_vectorstore._collection.count()
            print(f"GMP 문서 청크 수: {gmp_count}")
    
    def compare_section(self, section_topic: str) -> GapAnalysisResult:
        print(f"\n분석 중: {section_topic}")
        print("-" * 50)
        
        # 검색
        sop_docs = self.sop_vectorstore.similarity_search(section_topic, k=3) if self.sop_vectorstore else []
        gmp_docs = self.gmp_vectorstore.similarity_search(section_topic, k=3) if self.gmp_vectorstore else []
        
        sop_content = "\n".join([doc.page_content for doc in sop_docs])
        gmp_content = "\n".join([doc.page_content for doc in gmp_docs])
        sop_sources = [doc.metadata.get('source', 'Unknown') for doc in sop_docs]
        gmp_sources = [doc.metadata.get('source', 'Unknown') for doc in gmp_docs]
        
        print(f"SOP 관련 문서: {len(sop_docs)}개")
        print(f"GMP 관련 문서: {len(gmp_docs)}개")
        
        if sop_docs:
            print(f"SOP 미리보기: {sop_docs[0].page_content[:100]}...")
        if gmp_docs:
            print(f"GMP 미리보기: {gmp_docs[0].page_content[:100]}...")
        
        if not sop_docs and not gmp_docs:
            return GapAnalysisResult(
                sop_content="검색 결과 없음",
                gmp_content="검색 결과 없음",
                gap_type="no_data",
                severity="unknown",
                original_text="관련 문서 없음",
                sources=[]
            )
        
        # LLM 분석
        analysis_prompt = f"""
다음 SOP 내용과 GMP/FDA 규정을 비교하여 차이점을 분석해주세요.

주제: {section_topic}

SOP 현황:
{sop_content[:1000] if sop_content else "없음"}

GMP/FDA 규정:
{gmp_content[:1000] if gmp_content else "없음"}

분류:
- missing: SOP에 GMP 요구사항이 누락됨
- different: SOP와 GMP 규정이 다름  
- compliant: SOP가 GMP 규정을 잘 준수

반드시 다음 형식으로만 답변:
Gap Type: [missing/different/compliant]
Severity: [high/medium/low]
Original text: [해당되는 GMP 문서의 원문 문장]
"""
        
        try:
            response = self.llm.invoke(analysis_prompt)
            analysis_text = response.content if hasattr(response, 'content') else str(response)
            
            print(f"LLM 분석 결과: {analysis_text[:200]}...")
            
            # 파싱
            import re
            gap_match = re.search(r'Gap Type:\s*([^\n\r]+)', analysis_text, re.IGNORECASE)
            severity_match = re.search(r'Severity:\s*([^\n\r]+)', analysis_text, re.IGNORECASE)
            original_match = re.search(r'Original text:\s*(.+?)(?=\n\w+:|$)', analysis_text, re.IGNORECASE | re.DOTALL)
            
            gap_type = gap_match.group(1).strip().lower() if gap_match else "unknown"
            severity = severity_match.group(1).strip().lower() if severity_match else "medium"
            original_text = original_match.group(1).strip() if original_match else "분석 결과 없음"
            
            return GapAnalysisResult(
                sop_content=sop_content[:500] + "..." if len(sop_content) > 500 else sop_content,
                gmp_content=gmp_content[:500] + "..." if len(gmp_content) > 500 else gmp_content,
                gap_type=gap_type,
                severity=severity,
                original_text=original_text,
                sources=sop_sources + gmp_sources
            )
            
        except Exception as e:
            print(f"분석 실패: {e}")
            return GapAnalysisResult(
                sop_content=sop_content[:500] if sop_content else "없음",
                gmp_content=gmp_content[:500] if gmp_content else "없음", 
                gap_type="error",
                severity="unknown",
                original_text=f"분석 오류: {str(e)}",
                sources=sop_sources + gmp_sources
            )
    
    def analyze_multiple_sections(self, sections: List[str]) -> List[GapAnalysisResult]:
        results = []
        for i, section in enumerate(sections, 1):
            print(f"\n[{i}/{len(sections)}] {section} 분석")
            result = self.compare_section(section)
            results.append(result)
            
            status = {"compliant": "✅", "different": "⚠️", "missing": "❌", "error": "🚨"}
            print(f"결과: {status.get(result.gap_type, '❓')} {result.gap_type} ({result.severity})")
        
        return results
    
    def generate_report(self, results: List[GapAnalysisResult]) -> str:
        total = len(results)
        compliant = sum(1 for r in results if r.gap_type == "compliant")
        high_risk = sum(1 for r in results if r.severity == "high")
        
        report = f"""
# SOP vs GMP 비교 분석 보고서

## 요약
- 전체 분석 항목: {total}개
- 규정 준수: {compliant}개 ({compliant/total*100:.1f}%)
- 고위험 항목: {high_risk}개

## 상세 분석 결과

"""
        
        for i, result in enumerate(results, 1):
            status_icon = {"compliant": "✅", "different": "⚠️", "missing": "❌", "error": "🚨"}
            icon = status_icon.get(result.gap_type, "❓")
            
            report += f"### {i}. {icon} {result.gap_type.upper()} - {result.severity.upper()}\n"
            report += f"**관련 문서 원문**: {result.original_text}\n"
            report += f"**참고 문서**: {len(set(result.sources))}개\n\n"
        
        return report

# 사용
analyzer = SOPGMPAnalyzer(
    sop_vector_path="/Users/song/Desktop/workspace/final/rag/embedding/chroma_db_sop",
    gmp_vector_path="/Users/song/Desktop/workspace/final/rag/embedding/chroma_db_gmp"
)

results = analyzer.analyze_multiple_sections([
    "규격치가 n인 경우 실험치는 n+1자리까지 구하고 사사오입하여 자리수를 정한다",
    "표준품 사용에 관한 기록",
    "로트 번호 부여 체계",
    "제품 표준서 관리자는 제품 표준서 원본의 개정 내역에 신규 원료가 적용되기 시작한 본 생산 제조번호 및 생산일을 기록한다"
])

report = analyzer.generate_report(results)
print(report)
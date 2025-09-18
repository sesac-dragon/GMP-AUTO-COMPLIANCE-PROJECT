from langchain.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

class SOPGMPComparator:
    """SOP와 GMP 가이드라인 비교 시스템"""
    """사용된 벡터 디비 파일 : 전처리 + 시멘틱 청킹"""

    def __init__(self,
                 sop_db_path="/Users/song/Desktop/workspace/final/rag/embedding/chroma_db_sop", 
                 gmp_db_path="/Users/song/Desktop/workspace/final/rag/embedding/chroma_db_gmp",
                 model_name: str = "jhgan/ko-sroberta-multitask"):
        
        # 임베딩 모델 로드
        print("Loading embedding model...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            encode_kwargs={'normalize_embeddings': True},
            model_kwargs={'device': 'cpu'},
        )
        
        # SOP 벡터DB 로드
        print(f"Loading SOP database from: {sop_db_path}")
        try:
            self.sop_vectordb = Chroma(
                persist_directory=sop_db_path,
                embedding_function=self.embeddings,
                collection_name="sop_documents_semantic"  # 실제 컬렉션명으로 수정
            )
            print("SOP database loaded successfully!")
        except Exception as e:
            print(f"Error loading SOP database: {e}")
            self.sop_vectordb = None
        
        # GMP 벡터DB 로드
        print(f"Loading GMP database from: {gmp_db_path}")
        try:
            self.gmp_vectordb = Chroma(
                persist_directory=gmp_db_path,
                embedding_function=self.embeddings,
                collection_name="gmp_documents_semantic" # 실제 컬렉션명으로 수정
            )
            print("GMP database loaded successfully!")
        except Exception as e:
            print(f"Error loading GMP database: {e}")
            self.gmp_vectordb = None
    
    def search_sop(self, topic: str, k: int = 3):
        """SOP 검색"""
        if not self.sop_vectordb:
            return []
        
        results = self.sop_vectordb.similarity_search(topic, k=k)
        return results
    
    def search_gmp(self, topic: str, k: int = 3):
        """GMP 가이드라인 검색"""
        if not self.gmp_vectordb:
            return []
        
        results = self.gmp_vectordb.similarity_search(topic, k=k)
        return results
    
    def compare_topic(self, topic: str, k: int = 3, detail_level: str = "summary"):
        """SOP와 GMP 가이드라인 비교
        
        Args:
            topic: 비교할 주제
            k: 각 DB에서 검색할 결과 수
            detail_level: 'summary' 또는 'detailed'
        """
        print(f"\n{'='*50}")
        print(f"주제: '{topic}' 비교 분석")
        print(f"{'='*50}")
        
        # SOP 검색
        sop_results = self.search_sop(topic, k)
        print(f"\n SOP 검색 결과 ({len(sop_results)}개)")

        
        if not sop_results:
            print(" SOP 검색 결과 없음")
        else:
            for i, doc in enumerate(sop_results, 1):
                title = doc.metadata.get('title', 'SOP 문서')
                doc_id = doc.metadata.get('doc_id', 'N/A')
                pages = f"{doc.metadata.get('page_start', '')}-{doc.metadata.get('page_end', '')}"
                
                print(f"{i}. {title}")
                print(f"ID: {doc_id}, 페이지: {pages}")
                
                if detail_level == "detailed":
                    print(f"내용: {doc.page_content[:600]}...")
                else:
                    print(f"내용: {doc.page_content[:650]}...")
                print()
        
        # GMP 검색
        gmp_results = self.search_gmp(topic, k)
        print(f"GMP 가이드라인 검색 결과 ({len(gmp_results)}개)")
        print("-" * 40)
        
        if not gmp_results:
            print("GMP 검색 결과 없음")
        else:
            for i, doc in enumerate(gmp_results, 1):
                title = doc.metadata.get('title', 'GMP 문서')[:500]
                jurisdiction = doc.metadata.get('jurisdiction', 'N/A')
                pages = f"{doc.metadata.get('page_start', '')}-{doc.metadata.get('page_end', '')}"
                
                print(f"{i}. [{jurisdiction}] {title}")
                print(f"페이지: {pages}")
                
                if detail_level == "detailed":
                    print(f"내용: {doc.page_content[:600]}...")
                else:
                    print(f"내용: {doc.page_content[:600]}...")
                print()
        
        # 간단한 비교 요약
        print("비교 요약")
        print("-" * 40)
        print(f"  • SOP 관련 문서: {len(sop_results)}개")
        print(f"  • GMP 관련 문서: {len(gmp_results)}개")
        
        if sop_results and gmp_results:
            print(" • 상태: ✅ 양쪽 모두 관련 내용 존재")
        elif sop_results:
            print(" • 상태: ⚠️ SOP만 존재, GMP 가이드라인 검토 필요")
        elif gmp_results:
            print(" • 상태: ⚠️ GMP만 존재, SOP 개발/보완 필요")
        else:
            print(" • 상태: ❌ 양쪽 모두 관련 내용 부족")
        
        return {
            'topic': topic,
            'sop_results': sop_results,
            'gmp_results': gmp_results,
            'sop_count': len(sop_results),
            'gmp_count': len(gmp_results)
        }
    
    def batch_compare(self, topics: list, k: int = 3, detail_level: str = "summary"):
        """여러 주제 일괄 비교"""
        results = []
        for topic in topics:
            result = self.compare_topic(topic, k, detail_level)
            results.append(result)
        
        # 전체 요약
        print(f"\n{'='*60}")
        print("전체 비교 요약")
        print(f"{'='*60}")
        
        for result in results:
            status = "✅" if result['sop_count'] > 0 and result['gmp_count'] > 0 else \
                    "⚠️" if result['sop_count'] > 0 or result['gmp_count'] > 0 else "❌"
            
            print(f"{status} {result['topic']:<20} | SOP: {result['sop_count']:<2} | GMP: {result['gmp_count']:<2}")
        
        return results


def main_comparison():
    """비교 분석 실행"""
    
    # 비교기 초기화
    comparator = SOPGMPComparator(
        sop_db_path="/Users/song/Desktop/workspace/final/rag/embedding/chroma_db_sop",  # 실제 SOP DB 경로
        gmp_db_path="/Users/song/Desktop/workspace/final/rag/embedding/chroma_db_gmp",  # 실제 GMP DB 경로
    )
    
    # 비교할 주제들
    comparison_topics = [
    "규격치가 n인 경우 실험치는 n+1자리까지 구하고 사사오입하여 자리수를 정한다",
    "표준품 사용에 관한 기록",
    "로트 번호 부여 체계",
    "제품 표준서 관리자는 제품 표준서 원본의 개정 내역에 신규 원료가 적용되기 시작한 본 생산 제조번호 및 생산일을 기록한다"
    ]
    
    # 일괄 비교 실행
    results = comparator.batch_compare(
        topics=comparison_topics,
        k=3,  # 각 주제당 3개씩 검색
        detail_level="summary"  # "detailed" 또는 "summary"
    )
    
    return results


def single_topic_analysis(topic: str):
    """단일 주제 상세 분석"""
    
    comparator = SOPGMPComparator()
    
    result = comparator.compare_topic(
        topic=topic,
        k=5,  # 더 많은 결과
        detail_level="detailed"  # 상세 정보
    )
    
    return result


if __name__ == "__main__":
    # 전체 비교 실행
    main_comparison()
"""
실제 Word 파일로 GMP 교육자료 생성 모듈 테스트 (개선 버전)
"""

from gmp_training_generator import GMPTrainingGenerator
import os
import sys


def test_with_real_files():
    """실제 Word 파일로 테스트"""
    
    print("=" * 70)
    print("📄 실제 Word 파일로 GMP 교육자료 생성 테스트 (개선 버전)")
    print("=" * 70)
    
    # 1. API 키 확인
    if not os.getenv("OPENAI_API_KEY"):
        print("\n❌ 오류: OPENAI_API_KEY가 설정되지 않았습니다.")
        print("\n해결 방법:")
        print("1. 프로젝트 폴더에 .env 파일을 생성하세요")
        print("2. 다음 내용을 입력하세요:")
        print("   OPENAI_API_KEY=your-actual-api-key-here")
        print("\n또는 터미널에서:")
        print("   export OPENAI_API_KEY='your-api-key'  # Mac/Linux")
        print("   set OPENAI_API_KEY=your-api-key       # Windows")
        sys.exit(1)
    
    # 2. Word 파일 경로 입력받기
    print("\n📂 Word 파일을 준비해주세요.")
    print("   예시: ./documents/sop.docx")
    print()
    
    sop_path = input("🔹 SOP Word 파일 경로: ").strip()
    guideline_path = input("🔹 가이드라인 Word 파일 경로: ").strip()
    
    # 따옴표 제거 (드래그앤드롭 시 생길 수 있음)
    sop_path = sop_path.strip("'").strip('"')
    guideline_path = guideline_path.strip("'").strip('"')
    
    # 3. 파일 존재 확인
    if not os.path.exists(sop_path):
        print(f"\n❌ SOP 파일을 찾을 수 없습니다: {sop_path}")
        print("💡 힌트: 파일 경로를 확인하거나 파일을 프로젝트 폴더에 복사하세요.")
        sys.exit(1)
    
    if not os.path.exists(guideline_path):
        print(f"\n❌ 가이드라인 파일을 찾을 수 없습니다: {guideline_path}")
        print("💡 힌트: 파일 경로를 확인하거나 파일을 프로젝트 폴더에 복사하세요.")
        sys.exit(1)
    
    print("\n✅ 파일 확인 완료!")
    print(f"   SOP: {os.path.basename(sop_path)}")
    print(f"   가이드라인: {os.path.basename(guideline_path)}")
    
    # 4. 옵션 설정
    print("\n⚙️  생성 옵션 설정")
    print()
    
    try:
        num_questions = input("퀴즈 문제 수 (기본값: 10): ").strip()
        num_questions = int(num_questions) if num_questions else 10
    except ValueError:
        print("⚠️  잘못된 입력입니다. 기본값 10개로 설정합니다.")
        num_questions = 10
    
    print("\n난이도 선택:")
    print("1. easy - 기본 개념 확인")
    print("2. medium - 실무 적용 수준")
    print("3. hard - 심화 분석 및 판단")
    print("4. mixed - 다양한 난이도 혼합 (추천)")
    
    difficulty_map = {
        "1": "easy",
        "2": "medium",
        "3": "hard",
        "4": "mixed",
        "": "mixed"
    }
    
    difficulty_choice = input("\n선택 (1-4, 기본값: 4): ").strip()
    difficulty = difficulty_map.get(difficulty_choice, "mixed")
    
    print(f"\n설정 완료: 문제 {num_questions}개, 난이도 {difficulty}")
    
    additional_context = input("\n추가 설명 (선택사항, Enter로 건너뛰기): ").strip()
    additional_context = additional_context if additional_context else None
    
    # 5. 생성 시작
    print("\n" + "=" * 70)
    print("🚀 교육자료 및 퀴즈 생성 시작... (개선된 버전)")
    print("=" * 70)
    print("⏳ 잠시만 기다려주세요. (보통 2분 ~ 4분 소요)")
    print("💡 개선 사항: 자동 품질 검증 + 재시도 로직 적용")
    print()
    
    try:
        # 생성기 초기화
        generator = GMPTrainingGenerator()
        
        # 진행 상황 콜백 함수 (선택사항)
        def progress_callback(message):
            print(f"   📍 {message}")
        
        # 교육자료 및 퀴즈 생성
        result = generator.generate_from_files(
            sop_file_path=sop_path,
            guideline_file_path=guideline_path,
            num_quiz_questions=num_questions,
            quiz_difficulty=difficulty,
            additional_context=additional_context,
            progress_callback=progress_callback
        )
        
        # 6. 결과 출력
        print("\n" + "=" * 70)
        print("📚 생성된 교육자료")
        print("=" * 70)
        
        tm = result.training_material
        
        print(f"\n📌 제목: {tm.title}")
        print(f"\n📝 요약:")
        print(f"   {tm.summary}")
        
        print(f"\n🎯 핵심 포인트 ({len(tm.key_points)}개):")
        for i, point in enumerate(tm.key_points, 1):
            print(f"   {i}. {point}")
        
        print(f"\n📖 상세 내용:")
        content_length = len(tm.detailed_content)
        print(f"   총 길이: {content_length:,}자")
        
        # 상세 내용 미리보기 (더 많이 출력)
        content_preview = tm.detailed_content[:1500]
        print(f"\n   [미리보기 - 처음 1500자]")
        print("   " + "-" * 66)
        for line in content_preview.split('\n'):
            print(f"   {line}")
        print("   " + "-" * 66)
        print(f"   ...(전체 내용은 JSON 파일에서 확인하세요)")
        
        print(f"\n🔗 참조 문서 ({len(tm.references)}개):")
        for ref in tm.references[:10]:  # 처음 10개만
            print(f"   - {ref}")
        if len(tm.references) > 10:
            print(f"   ... 외 {len(tm.references) - 10}개")
        
        print("\n" + "=" * 70)
        print(f"❓ 생성된 퀴즈 ({len(result.quiz_questions)}문제)")
        print("=" * 70)
        
        # 퀴즈 출력 (처음 3문제만 상세히, 나머지는 제목만)
        for i, q in enumerate(result.quiz_questions, 1):
            if i <= 3:  # 처음 3문제만 상세히
                print(f"\n[문제 {i}]")
                print(f"❓ {q.question}")
                print()
                for j, opt in enumerate(q.options, 1):
                    marker = "✅" if j-1 == q.correct_answer else "  "
                    print(f"{marker} {j}. {opt}")
                print()
                print(f"💡 해설: {q.explanation}")
                print(f"📖 참조: {q.reference_section}")
                print("-" * 70)
            else:
                # 나머지는 제목만
                if i == 4:
                    print(f"\n[나머지 문제 {i}-{len(result.quiz_questions)}]")
                print(f"   {i}. {q.question}")
        
        print("\n   💡 전체 퀴즈 내용은 JSON 파일에서 확인하세요.")
        
        # 7. JSON 파일로 저장 (분리 저장)
        print("\n" + "=" * 70)
        print("💾 JSON 파일로 저장 중...")
        print("=" * 70)
        
        training_file, quiz_file = generator.export_to_separate_json(
            result, 
            "generated_training_material"
        )
        
        print("\n" + "=" * 70)
        print("✅ 생성 완료!")
        print("=" * 70)
        print(f"\n📁 결과 파일:")
        print(f"   - {training_file}")
        print(f"   - {quiz_file}")
        print(f"\n💾 파일 크기:")
        print(f"   - 교육자료: {os.path.getsize(training_file):,} bytes")
        print(f"   - 퀴즈: {os.path.getsize(quiz_file):,} bytes")
        
        # 8. 통계 정보
        print("\n📊 생성 통계:")
        print(f"   - 교육자료 제목: {tm.title}")
        print(f"   - 핵심 포인트 수: {len(tm.key_points)}개")
        print(f"   - 상세 내용 길이: {len(tm.detailed_content):,}자")
        print(f"   - 퀴즈 문제 수: {len(result.quiz_questions)}개")
        print(f"   - 선택지 수: 각 5개 (0-4 인덱스)")
        print(f"   - 참조 문서 수: {len(tm.references)}개")
        print(f"   - 생성 시각: {result.metadata.get('generation_timestamp', 'N/A')}")
        
        # 9. 품질 평가
        print("\n🎯 품질 평가:")
        
        # 교육자료 품질
        content_score = "⭐⭐⭐⭐⭐" if content_length >= 3000 else "⭐⭐⭐⭐" if content_length >= 2000 else "⭐⭐⭐"
        print(f"   - 교육자료 상세도: {content_score} ({content_length:,}자)")
        
        keypoints_score = "⭐⭐⭐⭐⭐" if len(tm.key_points) >= 9 else "⭐⭐⭐⭐" if len(tm.key_points) >= 7 else "⭐⭐⭐"
        print(f"   - 핵심 포인트: {keypoints_score} ({len(tm.key_points)}개)")
        
        # 퀴즈 품질
        quiz_valid = all(len(q.options) == 5 and 0 <= q.correct_answer <= 4 for q in result.quiz_questions)
        quiz_score = "⭐⭐⭐⭐⭐" if quiz_valid else "⭐⭐⭐"
        print(f"   - 퀴즈 형식: {quiz_score} ({'모든 문제 5지선다' if quiz_valid else '일부 문제 형식 오류'})")
        
        explanation_lengths = [len(q.explanation) for q in result.quiz_questions]
        avg_explanation = sum(explanation_lengths) / len(explanation_lengths)
        explanation_score = "⭐⭐⭐⭐⭐" if avg_explanation >= 150 else "⭐⭐⭐⭐" if avg_explanation >= 100 else "⭐⭐⭐"
        print(f"   - 퀴즈 해설: {explanation_score} (평균 {avg_explanation:.0f}자)")
        
        print("\n" + "=" * 70)
        print("🎉 테스트 성공!")
        print("=" * 70)
        
        # 10. 다음 단계 안내
        print("\n📌 다음 단계:")
        print(f"   1. {training_file} - 교육자료 확인")
        print(f"   2. {quiz_file} - 퀴즈 확인")
        print("   3. 교육자료를 PDF나 문서로 변환")
        print("   4. React 대시보드에 통합")
        print()
        
        # 11. 개선 제안
        if content_length < 2000:
            print("💡 개선 제안:")
            print(f"   - 교육자료가 다소 짧습니다 ({content_length}자)")
            print("   - 다시 실행하면 더 상세한 버전이 생성될 수 있습니다")
            print()
        
        return result
        
    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ 오류 발생!")
        print("=" * 70)
        print(f"\n오류 내용: {str(e)}")
        print(f"\n오류 타입: {type(e).__name__}")
        
        print("\n가능한 원인:")
        print("   1. API 키가 잘못되었거나 만료됨")
        print("   2. Word 파일 형식이 올바르지 않음")
        print("   3. 네트워크 연결 문제")
        print("   4. API 사용량 초과")
        print("   5. 품질 검증 기준을 3번 시도 후에도 통과 못함")
        
        print("\n해결 방법:")
        print("   - API 키 확인: https://platform.openai.com/api-keys")
        print("   - Word 파일이 .docx 형식인지 확인")
        print("   - 인터넷 연결 상태 확인")
        print("   - 다시 시도 (재시도 로직이 자동으로 작동합니다)")
        print()
        
        import traceback
        print("\n상세 오류 로그:")
        print(traceback.format_exc())
        
        raise


def quick_check():
    """빠른 파일 확인"""
    print("\n🔍 현재 폴더의 Word 파일 목록:")
    print()
    
    try:
        docx_files = [f for f in os.listdir('.') if f.endswith('.docx') and not f.startswith('~$')]
        
        if not docx_files:
            print("   (Word 파일이 없습니다)")
            print()
            print("💡 힌트:")
            print("   1. SOP와 가이드라인 Word 파일을 이 폴더에 복사하세요")
            print("   2. 또는 파일의 전체 경로를 입력하세요")
            print()
        else:
            for i, file in enumerate(docx_files, 1):
                size = os.path.getsize(file)
                print(f"   {i}. {file} ({size:,} bytes)")
            print()
    except Exception as e:
        print(f"   ⚠️  파일 목록 조회 실패: {e}")
        print()


if __name__ == "__main__":
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 12 + "GMP 교육자료 생성 모듈 테스트 v2.0" + " " * 19 + "║")
    print("║" + " " * 15 + "(개선된 프롬프트 + 품질 검증)" + " " * 21 + "║")
    print("╚" + "=" * 68 + "╝")
    
    # 현재 폴더의 Word 파일 확인
    quick_check()
    
    # 테스트 시작
    try:
        result = test_with_real_files()
    except KeyboardInterrupt:
        print("\n\n⚠️  사용자가 취소했습니다.")
        sys.exit(0)
    except Exception:
        print("\n💡 테스트를 다시 시도하거나 도움을 요청하세요.")
        sys.exit(1)
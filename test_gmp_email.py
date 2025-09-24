# test_gmp_email.py - GMP 이메일 알림 모듈 테스트

import asyncio
import os
from datetime import datetime
from gmp_email_alert import GMPEmailNotifier, AnalysisResults

async def test_email_notification():
    """이메일 알림 테스트"""
    
    print("🧪 GMP 이메일 알림 모듈 테스트 시작")
    print("=" * 50)
    
    # 1. SMTP 설정 (실제 이메일 계정 정보 입력 필요)
    print("📧 SMTP 설정 중...")
    
    # TODO: 실제 SMTP 정보로 변경하세요
    smtp_config = {
        'server': 'smtp.gmail.com',  # Gmail 사용 시
        'port': 587,
        'username': input("Gmail 계정을 입력하세요: "),  # 실제 Gmail 주소
        'password': input("Gmail 앱 비밀번호를 입력하세요: "),  # Gmail 앱 비밀번호
        'from_email': None  # username과 동일하게 설정됨
    }
    smtp_config['from_email'] = smtp_config['username']
    
    # 수신자 이메일
    recipient_email = input("알림을 받을 이메일 주소를 입력하세요: ")
    
    try:
        # 2. 알림 서비스 초기화
        print("\n🔧 알림 서비스 초기화 중...")
        notifier = GMPEmailNotifier(smtp_config)
        
        # 3. SMTP 연결 테스트
        print("🔗 SMTP 연결 테스트 중...")
        if not notifier.test_connection():
            print("❌ SMTP 연결 실패! 설정을 확인해주세요.")
            return False
        
        print("✅ SMTP 연결 성공!")
        
        # 4. 테스트 데이터 생성 (실제 RAG 분석 결과 시뮬레이션)
        print("\n📊 테스트 데이터 생성 중...")
        
        test_results = AnalysisResults(
            task_id=f"test_gmp_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            compliance_issues=[
                {
                    "section": "제조관리 (Manufacturing)",
                    "issue": "온도 기록 주기가 FDA 가이드라인 요구사항(30분)보다 길게 설정됨 (현재: 1시간)",
                    "priority": "high",
                    "guideline_ref": "FDA 21 CFR 211.160",
                    "proposed_change": "온도 기록 주기를 1시간 간격에서 30분 간격으로 변경하여 FDA 가이드라인을 준수해야 합니다. 이는 제품 품질 보증을 위한 중요한 개정사항입니다."
                },
                {
                    "section": "품질관리 (Quality Control)",
                    "issue": "원료 샘플링 방법이 ICH Q7 가이드라인의 랜덤 샘플링 원칙과 상이함",
                    "priority": "medium",
                    "guideline_ref": "ICH Q7 Section 11.1",
                    "proposed_change": "현재의 순차적 샘플링 방식을 통계적 랜덤 샘플링 방식으로 변경하여 샘플 대표성을 향상시켜야 합니다."
                },
                {
                    "section": "문서관리 (Documentation)",
                    "issue": "배치 기록 보관 기간이 EMA 가이드라인 요구사항보다 부족",
                    "priority": "medium", 
                    "guideline_ref": "EMA/INS/GMP/594280/2007",
                    "proposed_change": "배치 기록 보관 기간을 현재 5년에서 7년으로 연장하여 EMA 요구사항을 충족해야 합니다."
                },
                {
                    "section": "위생관리 (Hygiene)",
                    "issue": "작업자 위생 점검 절차가 WHO GMP 가이드라인의 세부 요구사항 일부 누락",
                    "priority": "low",
                    "guideline_ref": "WHO Technical Report Series No. 961",
                    "proposed_change": "작업자 위생 점검 체크리스트에 손목시계 및 장신구 착용 금지 항목을 명시적으로 추가해야 합니다."
                }
            ],
            total_sections_analyzed=25,
            compliance_rate=84.7,
            analysis_completed_at=datetime.now()
        )
        
        print(f"📋 테스트 결과 요약:")
        print(f"   - 작업 ID: {test_results.task_id}")
        print(f"   - 컴플라이언스율: {test_results.compliance_rate}%")
        print(f"   - 총 이슈: {test_results.total_issues}개")
        print(f"   - 고우선순위: {test_results.high_priority_issues}개")
        
        # 5. 완료 알림 테스트
        print(f"\n📮 완료 알림 이메일 발송 중... → {recipient_email}")
        
        success = await notifier.send_completion_notification(
            user_email=recipient_email,
            results=test_results,
            dashboard_url="http://localhost:3000/results/test_dashboard"  # 테스트용 URL
        )
        
        if success:
            print("✅ 완료 알림 이메일 발송 성공!")
            print("📧 이메일함을 확인해보세요.")
        else:
            print("❌ 완료 알림 이메일 발송 실패")
            return False
        
        # 6. 실패 알림 테스트 (선택사항)
        test_failure = input("\n실패 알림도 테스트해보시겠습니까? (y/n): ").lower() == 'y'
        
        if test_failure:
            print(f"📮 실패 알림 이메일 발송 중... → {recipient_email}")
            
            failure_success = await notifier.send_failure_notification(
                user_email=recipient_email,
                task_id="test_failure_001",
                error_message="테스트 오류: SOP 파일 파싱 중 인코딩 오류 발생 (UTF-8 expected, got cp949)"
            )
            
            if failure_success:
                print("✅ 실패 알림 이메일 발송 성공!")
            else:
                print("❌ 실패 알림 이메일 발송 실패")
        
        print("\n" + "=" * 50)
        print("🎉 모든 테스트 완료!")
        print("📧 이메일함에서 다음 이메일들을 확인하세요:")
        print("   1. GMP 컴플라이언스 분석 완료 알림")
        if test_failure:
            print("   2. GMP 컴플라이언스 분석 실패 알림")
        
        return True
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {str(e)}")
        print("\n🔧 문제 해결 방법:")
        print("1. Gmail 2단계 인증 설정 후 앱 비밀번호 사용")
        print("2. 'Less secure app access' 비활성화 (앱 비밀번호 사용)")
        print("3. SMTP 설정 정보 재확인")
        return False

# 추가: Gmail 앱 비밀번호 설정 가이드
def print_gmail_setup_guide():
    """Gmail 설정 가이드"""
    print("\n" + "=" * 60)
    print("📮 Gmail SMTP 설정 가이드")
    print("=" * 60)
    print("1. Google 계정 → 보안 → 2단계 인증 활성화")
    print("2. 2단계 인증 → 앱 비밀번호 생성")
    print("3. '메일' 앱 선택 → 16자리 앱 비밀번호 생성")
    print("4. 이 앱 비밀번호를 테스트에서 사용")
    print("5. SMTP 설정:")
    print("   - 서버: smtp.gmail.com")
    print("   - 포트: 587")
    print("   - TLS: 사용")
    print("=" * 60)

# 간단 테스트 (SMTP 설정 없이 이메일 HTML만 확인)
def test_email_html_preview():
    """이메일 HTML 미리보기 테스트"""
    print("🎨 이메일 HTML 미리보기 테스트")
    
    # 테스트 데이터
    test_results = AnalysisResults(
        task_id="preview_test_001",
        compliance_issues=[
            {
                "section": "제조관리",
                "issue": "온도 기록 주기 불일치",
                "priority": "high",
                "guideline_ref": "FDA 21 CFR 211.160",
                "proposed_change": "온도 기록 주기를 30분으로 변경"
            }
        ],
        total_sections_analyzed=10,
        compliance_rate=88.5,
        analysis_completed_at=datetime.now()
    )
    
    # 가짜 설정으로 이메일 HTML 생성만 테스트
    fake_config = {
        'server': 'test',
        'port': 587,
        'username': 'test@test.com',
        'password': 'test',
        'from_email': 'test@test.com'
    }
    
    notifier = GMPEmailNotifier(fake_config)
    email_msg = notifier.create_completion_email(
        user_email="test@example.com",
        results=test_results,
        dashboard_url="http://localhost:3000/test"
    )
    
    # HTML 내용을 파일로 저장
    html_content = None
    for part in email_msg.walk():
        if part.get_content_type() == "text/html":
            html_content = part.get_payload(decode=True).decode('utf-8')
            break
    
    if html_content:
        with open('email_preview.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("✅ 이메일 HTML 미리보기 파일 생성: email_preview.html")
        print("📁 브라우저로 열어서 이메일 디자인을 확인해보세요!")
        return True
    
    return False

if __name__ == "__main__":
    print("GMP 이메일 알림 모듈 테스트")
    print("1. 실제 이메일 발송 테스트")
    print("2. HTML 미리보기만 테스트")
    print("3. Gmail 설정 가이드 보기")
    
    choice = input("\n선택하세요 (1/2/3): ")
    
    if choice == "1":
        asyncio.run(test_email_notification())
    elif choice == "2":
        test_email_html_preview()
    elif choice == "3":
        print_gmail_setup_guide()
    else:
        print("잘못된 선택입니다.")
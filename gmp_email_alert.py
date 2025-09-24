# 사용시 아래와 같이 임포트
# from gmp_email_alert import GMPEmailNotifier, AnalysisResults

#your_project/
#├── gmp_email_alert.py       # ← 지금 저장
#├── rag_analysis.py          # 나중에 개발
#├── dashboard.py             # 나중에 개발  
#└── main.py                  # 메인 실행 파일

# GMP 컴플라이언스 이메일 알림 모듈
import smtplib
import asyncio
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AnalysisResults:
    """분석 결과 데이터 클래스"""
    task_id: str
    compliance_issues: List[Dict]
    total_sections_analyzed: int
    compliance_rate: float
    analysis_completed_at: datetime
    total_issues: int = 0
    high_priority_issues: int = 0
    
    def __post_init__(self):
        self.total_issues = len(self.compliance_issues)
        self.high_priority_issues = len([i for i in self.compliance_issues if i.get('priority') == 'high'])

class GMPEmailNotifier:
    """GMP 컴플라이언스 분석 완료 이메일 알림 클래스"""
    
    def __init__(self, smtp_config: Dict[str, str]):
        """
        SMTP 설정으로 이메일 알림 서비스 초기화
        
        smtp_config 예시:
        {
            'server': 'smtp.gmail.com',
            'port': 587,
            'username': 'your-email@gmail.com',
            'password': 'your-app-password',
            'from_email': 'your-email@gmail.com'
        }
        """
        self.smtp_server = smtp_config['server']
        self.smtp_port = smtp_config['port']
        self.username = smtp_config['username']
        self.password = smtp_config['password']
        self.from_email = smtp_config['from_email']
        
        logger.info(f"이메일 알림 서비스 초기화 완료: {self.smtp_server}:{self.smtp_port}")
    
    def create_completion_email(self, user_email: str, results: AnalysisResults, 
                              dashboard_url: str = None) -> MIMEMultipart:
        """완료 알림 이메일 생성"""
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"✅ GMP 컴플라이언스 분석 완료 - {results.task_id[:8]}"
        msg['From'] = self.from_email
        msg['To'] = user_email
        
        # 우선순위별 이슈 개수 계산
        medium_issues = len([i for i in results.compliance_issues if i.get('priority') == 'medium'])
        low_issues = len([i for i in results.compliance_issues if i.get('priority') == 'low'])
        
        # 컴플라이언스 상태 아이콘 결정
        if results.compliance_rate >= 95:
            status_icon = "🟢"
            status_text = "우수"
            status_color = "#28a745"
        elif results.compliance_rate >= 85:
            status_icon = "🟡"
            status_text = "양호"
            status_color = "#ffc107"
        else:
            status_icon = "🔴"
            status_text = "개선필요"
            status_color = "#dc3545"
        
        # HTML 이메일 템플릿
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>GMP 컴플라이언스 분석 완료</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 20px auto; background-color: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow: hidden;">
                
                <!-- 헤더 -->
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center;">
                    <h1 style="margin: 0; font-size: 24px; font-weight: 700;">🎯 GMP AUTO COMPLIANCE</h1>
                    <p style="margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">분석이 완료되었습니다!</p>
                </div>
                
                <!-- 메인 결과 -->
                <div style="padding: 30px;">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <div style="font-size: 48px; margin-bottom: 10px;">{status_icon}</div>
                        <h2 style="margin: 0; color: {status_color}; font-size: 32px;">{results.compliance_rate:.1f}%</h2>
                        <p style="margin: 5px 0 0 0; color: #666; font-size: 18px;">전체 컴플라이언스율 - {status_text}</p>
                    </div>
                    
                    <!-- 분석 요약 -->
                    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                        <h3 style="margin: 0 0 15px 0; color: #333; font-size: 18px;">📋 분석 요약</h3>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                            <div>
                                <div style="font-size: 14px; color: #666; margin-bottom: 3px;">작업 ID</div>
                                <div style="font-size: 16px; font-weight: 600; color: #333;">{results.task_id}</div>
                            </div>
                            <div>
                                <div style="font-size: 14px; color: #666; margin-bottom: 3px;">완료 시간</div>
                                <div style="font-size: 16px; font-weight: 600; color: #333;">{results.analysis_completed_at.strftime('%Y.%m.%d %H:%M')}</div>
                            </div>
                            <div>
                                <div style="font-size: 14px; color: #666; margin-bottom: 3px;">분석된 섹션</div>
                                <div style="font-size: 16px; font-weight: 600; color: #333;">{results.total_sections_analyzed}개</div>
                            </div>
                            <div>
                                <div style="font-size: 14px; color: #666; margin-bottom: 3px;">발견된 이슈</div>
                                <div style="font-size: 16px; font-weight: 600; color: #dc3545;">{results.total_issues}개</div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 이슈 우선순위별 분류 -->
                    {f'''
                    <div style="background-color: white; border: 1px solid #dee2e6; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                        <h3 style="margin: 0 0 15px 0; color: #333; font-size: 18px;">🔍 발견된 이슈</h3>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">
                            <div style="text-align: center; flex: 1;">
                                <div style="font-size: 24px; font-weight: bold; color: #dc3545; margin-bottom: 5px;">{results.high_priority_issues}</div>
                                <div style="font-size: 14px; color: #666;">🔴 고우선순위</div>
                            </div>
                            <div style="text-align: center; flex: 1;">
                                <div style="font-size: 24px; font-weight: bold; color: #ffc107; margin-bottom: 5px;">{medium_issues}</div>
                                <div style="font-size: 14px; color: #666;">🟡 중우선순위</div>
                            </div>
                            <div style="text-align: center; flex: 1;">
                                <div style="font-size: 24px; font-weight: bold; color: #28a745; margin-bottom: 5px;">{low_issues}</div>
                                <div style="font-size: 14px; color: #666;">🟢 저우선순위</div>
                            </div>
                        </div>
                    </div>
                    ''' if results.total_issues > 0 else ''}
                    
                    <!-- 주요 이슈 미리보기 (고우선순위만) -->
                    {self._create_issue_preview(results.compliance_issues)}
                    
                    <!-- 대시보드 링크 -->
                    <div style="text-align: center; margin: 25px 0;">
                        <a href="{dashboard_url or '#'}" 
                           style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                  color: white; text-decoration: none; padding: 15px 30px; border-radius: 8px; 
                                  font-weight: 600; font-size: 16px;">
                            📊 상세 결과 확인하기
                        </a>
                    </div>
                    
                    <!-- 다음 단계 안내 -->
                    <div style="background-color: #e7f3ff; border: 1px solid #b3d9ff; border-radius: 8px; padding: 20px; margin-top: 25px;">
                        <h4 style="margin: 0 0 10px 0; color: #0066cc;">💡 다음 단계</h4>
                        <ul style="margin: 0; padding-left: 20px; color: #333;">
                            <li style="margin-bottom: 5px;">대시보드에서 상세한 개정 제안사항을 확인하세요</li>
                            <li style="margin-bottom: 5px;">고우선순위 이슈부터 검토하여 SOP 개정을 진행하세요</li>
                            <li style="margin-bottom: 5px;">개정 완료 후 재분석을 통해 컴플라이언스를 재확인하세요</li>
                        </ul>
                    </div>
                </div>
                
                <!-- 푸터 -->
                <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #dee2e6;">
                    <p style="margin: 0; font-size: 12px; color: #666;">
                        이 이메일은 GMP AUTO COMPLIANCE 시스템에서 자동으로 발송되었습니다.<br>
                        문의사항이 있으시면 관리자에게 연락해주세요.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        return msg
    
    def _create_issue_preview(self, issues: List[Dict]) -> str:
        """고우선순위 이슈 미리보기 HTML 생성"""
        high_priority_issues = [issue for issue in issues if issue.get('priority') == 'high'][:3]  # 최대 3개
        
        if not high_priority_issues:
            return ""
        
        preview_html = '''
        <div style="background-color: #fff5f5; border: 1px solid #fed7d7; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
            <h3 style="margin: 0 0 15px 0; color: #c53030; font-size: 18px;">🚨 주요 이슈 미리보기</h3>
        '''
        
        for issue in high_priority_issues:
            preview_html += f'''
            <div style="background-color: white; border-left: 4px solid #dc3545; padding: 15px; margin-bottom: 10px; border-radius: 0 6px 6px 0;">
                <div style="font-weight: 600; color: #333; margin-bottom: 5px;">{issue.get('section', 'N/A')}</div>
                <div style="color: #666; font-size: 14px; line-height: 1.4;">{issue.get('issue', 'N/A')}</div>
                <div style="font-size: 12px; color: #007bff; margin-top: 5px;">💡 {issue.get('proposed_change', 'N/A')[:100]}{'...' if len(issue.get('proposed_change', '')) > 100 else ''}</div>
            </div>
            '''
        
        if len(high_priority_issues) < len([i for i in issues if i.get('priority') == 'high']):
            remaining = len([i for i in issues if i.get('priority') == 'high']) - len(high_priority_issues)
            preview_html += f'''
            <div style="text-align: center; margin-top: 10px;">
                <span style="color: #666; font-size: 14px;">+ {remaining}개의 고우선순위 이슈가 더 있습니다</span>
            </div>
            '''
        
        preview_html += '</div>'
        return preview_html
    
    def create_failure_email(self, user_email: str, task_id: str, 
                           error_message: str) -> MIMEMultipart:
        """실패 알림 이메일 생성"""
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"❌ GMP 컴플라이언스 분석 실패 - {task_id[:8]}"
        msg['From'] = self.from_email
        msg['To'] = user_email
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                
                <div style="background-color: #dc3545; color: white; padding: 30px; text-align: center;">
                    <h1 style="margin: 0; font-size: 24px;">❌ 분석 실패</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">GMP 컴플라이언스 분석 중 오류가 발생했습니다</p>
                </div>
                
                <div style="padding: 30px;">
                    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                        <h3 style="margin: 0 0 10px 0; color: #333;">오류 정보</h3>
                        <p style="margin: 0; color: #666;"><strong>작업 ID:</strong> {task_id}</p>
                        <p style="margin: 5px 0 0 0; color: #666;"><strong>실패 시간:</strong> {datetime.now().strftime('%Y.%m.%d %H:%M')}</p>
                    </div>
                    
                    <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                        <h4 style="margin: 0 0 10px 0; color: #856404;">오류 내용</h4>
                        <p style="margin: 0; color: #856404; font-family: monospace; font-size: 14px;">{error_message}</p>
                    </div>
                    
                    <div style="background-color: #e7f3ff; padding: 20px; border-radius: 8px;">
                        <h4 style="margin: 0 0 10px 0; color: #0066cc;">해결 방법</h4>
                        <ul style="margin: 0; padding-left: 20px; color: #333;">
                            <li>업로드한 파일 형식이 지원되는지 확인해주세요 (PDF, DOC, DOCX)</li>
                            <li>파일이 손상되지 않았는지 확인해주세요</li>
                            <li>잠시 후 다시 시도해주세요</li>
                            <li>문제가 계속되면 관리자에게 문의해주세요</li>
                        </ul>
                    </div>
                </div>
                
                <div style="background-color: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px;">
                    이 이메일은 GMP AUTO COMPLIANCE 시스템에서 자동으로 발송되었습니다.
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        return msg
    
    async def send_completion_notification(self, user_email: str, results: AnalysisResults, 
                                         dashboard_url: str = None) -> bool:
        """분석 완료 알림 발송"""
        try:
            logger.info(f"분석 완료 이메일 발송 시작: {user_email} (Task: {results.task_id})")
            
            msg = self.create_completion_email(user_email, results, dashboard_url)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"분석 완료 이메일 발송 성공: {user_email}")
            return True
            
        except Exception as e:
            logger.error(f"분석 완료 이메일 발송 실패: {user_email}, 오류: {str(e)}")
            return False
    
    async def send_failure_notification(self, user_email: str, task_id: str, 
                                      error_message: str) -> bool:
        """분석 실패 알림 발송"""
        try:
            logger.info(f"분석 실패 이메일 발송 시작: {user_email} (Task: {task_id})")
            
            msg = self.create_failure_email(user_email, task_id, error_message)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"분석 실패 이메일 발송 성공: {user_email}")
            return True
            
        except Exception as e:
            logger.error(f"분석 실패 이메일 발송 실패: {user_email}, 오류: {str(e)}")
            return False
    
    def test_connection(self) -> bool:
        """SMTP 연결 테스트"""
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
            logger.info("SMTP 연결 테스트 성공")
            return True
        except Exception as e:
            logger.error(f"SMTP 연결 테스트 실패: {str(e)}")
            return False

# 사용 예시
async def example_usage():
    """사용 예시"""
    
    # 1. SMTP 설정
    smtp_config = {
        'server': 'smtp.gmail.com',
        'port': 587,
        'username': 'your-email@gmail.com',
        'password': 'your-app-password',  # Gmail 앱 비밀번호
        'from_email': 'your-email@gmail.com'
    }
    
    # 2. 알림 서비스 초기화
    notifier = GMPEmailNotifier(smtp_config)
    
    # 3. 연결 테스트
    if not notifier.test_connection():
        print("❌ SMTP 연결 실패")
        return
    
    # 4. 분석 결과 데이터 (실제로는 RAG 분석 결과)
    analysis_results = AnalysisResults(
        task_id="gmp_20241224_001",
        compliance_issues=[
            {
                "section": "제조관리",
                "issue": "온도 기록 주기가 FDA 가이드라인과 불일치",
                "priority": "high",
                "guideline_ref": "FDA 21 CFR 211.160",
                "proposed_change": "온도 기록을 1시간 간격에서 30분 간격으로 변경하여 FDA 요구사항을 준수해야 합니다."
            },
            {
                "section": "품질관리",
                "issue": "샘플링 방법이 ICH Q7과 상이",
                "priority": "medium",
                "guideline_ref": "ICH Q7 Section 11.1",
                "proposed_change": "현재 순차 샘플링에서 랜덤 샘플링 방식으로 변경 필요"
            }
        ],
        total_sections_analyzed=15,
        compliance_rate=87.5,
        analysis_completed_at=datetime.now()
    )
    
    # 5. 완료 알림 발송
    success = await notifier.send_completion_notification(
        user_email="user@company.com",
        results=analysis_results,
        dashboard_url="http://your-dashboard.com/results/gmp_20241224_001"
    )
    
    if success:
        print("✅ 완료 알림 발송 성공")
    else:
        print("❌ 완료 알림 발송 실패")
    
    # 6. 실패 알림 발송 예시
    # await notifier.send_failure_notification(
    #     user_email="user@company.com",
    #     task_id="gmp_20241224_002", 
    #     error_message="파일 파싱 중 오류 발생: Invalid PDF format"
    # )

if __name__ == "__main__":
    asyncio.run(example_usage())
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email_report(smtp_server: str, smtp_port: int, 
                      username: str, password: str, 
                      sender: str, recipients: list, 
                      subject: str, body: str):
    # 메시지 구성
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    # SMTP 서버 연결 및 발송
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()  # TLS 보안 시작
        server.login(username, password)
        server.sendmail(sender, recipients, msg.as_string())
    print("메일을 성공적으로 보냈습니다.")

    """
    크롤링 파일 하단에 아래 내용 복사붙여넣기. 크롤링 완료 시 자동으로 메일 전송하도록

    if __name__ == "__main__":
    crawl()
    
    send_email_report(
        smtp_server="smtp.gmail.com",
        smtp_port=587,
        username="your_email@gmail.com",
        password="your_password",
                                        password : Gmail 계정의 앱 비밀번호(App Password)
                                        구글 계정에 2단계 인증이 활성화된 상태에서 생성한 16자리 앱 비밀번호를 사용해야 합니다.
                                        일반 비밀번호는 더 이상 SMTP 인증에 사용할 수 없습니다.
        sender="your_email@gmail.com",
        recipients=["recipient@example.com"],
        subject="GMP 사이트 크롤링 완료 보고",
        body="크롤링이 정상적으로 완료되었습니다. 다운로드된 문서 수는 X개입니다."
    )
    
    """
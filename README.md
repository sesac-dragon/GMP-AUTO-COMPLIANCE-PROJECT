# GMP SOP 교육자료 및 퀴즈 자동 생성 모듈

GMP(Good Manufacturing Practice) SOP 문서와 관련 가이드라인을 분석하여 **실무자를 위한 교육자료**와 **평가용 퀴즈**를 자동으로 생성하는 Python 모듈입니다.

## 주요 기능

- **교육자료 자동 생성**: SOP와 가이드라인을 분석하여 상세한 교육 자료 생성
  - 개요, 요약, 핵심 포인트 추출
  - 섹션별 상세 설명 (SOP 근거, 가이드라인 근거, 실무 적용 방법)
  - 체크리스트 및 주의사항 포함
  - 출처 명시 (SOP 섹션 번호, 가이드라인 조항)

- **퀴즈 자동 생성**: 평가용 객관식 문제 생성
  - 난이도별 문제 구성 (easy, medium, hard, mixed)
  - 5지선다 형식
  - 상세한 해설 포함
  - 참조 섹션 명시

- **분할 생성 전략**: GPT-4 토큰 제한을 극복하기 위한 2단계 생성
  - 1단계: 개요 및 핵심 포인트 생성
  - 2단계: 상세 내용 생성

## 설치

### 1. 필수 라이브러리 설치

```bash
pip install -r requirements.txt
```

### 2. OpenAI API 키 설정

`.env` 파일을 프로젝트 루트에 생성하고 API 키를 추가:

```
OPENAI_API_KEY=your-api-key-here
```

또는 환경 변수로 설정:

```bash
# Mac/Linux
export OPENAI_API_KEY='your-api-key'

# Windows
set OPENAI_API_KEY=your-api-key
```

## 사용 방법

### 기본 사용 (CLI)

```bash
python test_real_files.py
```

대화형 프롬프트에 따라:
1. SOP Word 파일 경로 입력
2. 가이드라인 Word 파일 경로 입력
3. 퀴즈 문제 수 선택 (기본값: 10)
4. 난이도 선택 (easy/medium/hard/mixed)
5. 추가 설명 입력 (선택사항)

### Python 코드에서 사용

```python
from gmp_training_generator import GMPTrainingGenerator

# 생성기 초기화
generator = GMPTrainingGenerator()

# 교육자료 및 퀴즈 생성
result = generator.generate_from_files(
    sop_file_path="my_sop.docx",
    guideline_file_path="gmp_guideline.docx",
    num_quiz_questions=10,
    quiz_difficulty="mixed",
    additional_context="추가 설명 (선택사항)"
)

# JSON 파일로 저장
training_file, quiz_file = generator.export_to_separate_json(
    result, 
    "generated_material"
)

print(f"교육자료: {training_file}")
print(f"퀴즈: {quiz_file}")
```

### 진행 상황 콜백 사용 (React 연동용)

```python
def progress_callback(message):
    print(f"진행: {message}")
    # React로 전송하는 로직 추가

result = generator.generate_from_files(
    sop_file_path="my_sop.docx",
    guideline_file_path="gmp_guideline.docx",
    progress_callback=progress_callback
)
```

## 출력 형식

### 교육자료 JSON

```json
{
  "training_material": {
    "title": "교육자료 제목",
    "summary": "3-4문장의 상세한 요약",
    "key_points": ["핵심 포인트 1", "핵심 포인트 2", ...],
    "detailed_content": "마크다운 형식의 상세 내용",
    "references": ["SOP Section 1", "21 CFR 211.122", ...]
  },
  "metadata": {
    "sop_file": "my_sop.docx",
    "guideline_file": "gmp_guideline.docx",
    "generation_timestamp": "2025-09-29 14:56:38",
    "training_content_length": 2372
  }
}
```

### 퀴즈 JSON

```json
{
  "quiz_questions": [
    {
      "question": "문제 내용",
      "options": ["선택지1", "선택지2", "선택지3", "선택지4", "선택지5"],
      "correct_answer": 0,
      "explanation": "정답 해설",
      "reference_section": "SOP Section 1"
    }
  ],
  "metadata": {
    "num_questions": 10,
    "difficulty": "mixed"
  }
}
```

## 교육자료 구조

생성되는 교육자료는 다음과 같은 구조로 작성됩니다:

### 1. 개요
- SOP의 목적, 적용 범위
- 관련 규정 근거 (21 CFR Part 211 등)

### 2. 주요 내용
각 핵심 주제별로:
- **SOP 근거**: 해당 섹션의 요구사항, 담당 부서
- **가이드라인 근거**: 관련 조항 및 배경
- **실무 적용**: 단계별 실행 방법
- **예시 또는 주의사항**: 흔한 실수와 예방법

### 3. 체크리스트
주요 절차별 확인사항

### 4. 주의사항 및 흔한 실수
실무에서 자주 발생하는 오류와 예방 방법

## 퀴즈 난이도

- **easy**: 정의, 기본 개념, 단순 암기
  - 예: "QA 부서의 주요 역할은 무엇입니까?"

- **medium**: 절차 이해, 적용, 판단
  - 예: "라벨 검증 시 확인해야 할 사항은?"

- **hard**: 복합 상황 판단, 우선순위 결정
  - 예: "일탈 발생 시 가장 먼저 취해야 할 조치는?"

- **mixed** (권장): 다양한 난이도 혼합
  - easy 30%, medium 50%, hard 20%

## 기술 사양

- **AI 모델**: OpenAI GPT-4 Turbo
- **입력 형식**: Microsoft Word (.docx)
- **출력 형식**: JSON
- **토큰 제한**: 분할 생성으로 극복
- **생성 시간**: 2-4분 (문서 크기에 따라 다름)

## 파일 구조

```
auto_education/
├── gmp_training_generator.py    # 메인 모듈
├── test_real_files.py            # CLI 테스트 스크립트
├── requirements.txt              # 필수 라이브러리
├── .env                          # API 키 (생성 필요)
├── README.md                     # 문서
├── my_sop.docx                   # SOP 파일 (예시)
├── gmp_guideline.docx            # 가이드라인 파일 (예시)
└── generated_training_material_*.json  # 생성된 결과물
```

## API 사용 비용

GPT-4 Turbo 기준 (2024년):
- 입력: $0.01 / 1K 토큰
- 출력: $0.03 / 1K 토큰

예상 비용:
- 교육자료 생성: 약 $0.10-0.30
- 퀴즈 생성: 약 $0.05-0.15
- **총 비용: 약 $0.15-0.45 / 세트**

## 주의사항

1. **API 키 보안**: `.env` 파일을 Git에 커밋하지 마세요
2. **문서 크기**: 너무 큰 문서(50페이지 이상)는 처리 시간이 길어질 수 있습니다
3. **인터넷 연결**: API 호출을 위해 안정적인 인터넷 연결이 필요합니다
4. **결과 검토**: AI 생성 결과는 반드시 전문가가 검토해야 합니다

## React 대시보드 통합

### FastAPI 백엔드 예시

```python
from fastapi import FastAPI, UploadFile, File
from gmp_training_generator import GMPTrainingGenerator

app = FastAPI()
generator = GMPTrainingGenerator()

@app.post("/generate")
async def generate_materials(
    sop_file: UploadFile = File(...),
    guideline_file: UploadFile = File(...),
    num_questions: int = 10,
    difficulty: str = "mixed"
):
    # 파일 저장
    sop_path = f"temp/{sop_file.filename}"
    guideline_path = f"temp/{guideline_file.filename}"
    
    with open(sop_path, "wb") as f:
        f.write(await sop_file.read())
    with open(guideline_path, "wb") as f:
        f.write(await guideline_file.read())
    
    # 생성
    result = generator.generate_from_files(
        sop_path, 
        guideline_path,
        num_questions,
        difficulty
    )
    
    return generator.to_dict(result)
```

### Flask 백엔드 예시

```python
from flask import Flask, request, jsonify
from gmp_training_generator import GMPTrainingGenerator

app = Flask(__name__)
generator = GMPTrainingGenerator()

@app.route('/generate', methods=['POST'])
def generate_materials():
    sop_file = request.files['sop']
    guideline_file = request.files['guideline']
    
    # 파일 저장 및 생성 로직
    result = generator.generate_from_files(...)
    
    return jsonify(generator.to_dict(result))

if __name__ == '__main__':
    app.run(debug=True)
```

## 트러블슈팅

### API 키 오류
```
ValueError: OPENAI_API_KEY가 설정되지 않았습니다.
```
**해결**: `.env` 파일에 API 키를 추가하거나 환경 변수를 설정하세요.

### 교육자료가 짧게 생성됨
**원인**: GPT가 복잡한 프롬프트를 거부
**해결**: 이미 구현된 분할 생성 전략이 자동으로 해결합니다.

### JSON 파싱 오류
**원인**: GPT가 유효하지 않은 JSON 반환
**해결**: 재시도 로직이 자동으로 작동합니다 (최대 2회).

## 라이선스

이 프로젝트는 내부 사용을 위해 개발되었습니다.

## 버전 히스토리

- **v2.0** (2025-09-29)
  - 분할 생성 전략 구현
  - 출처 명시 강화 (SOP 섹션, 가이드라인 조항)
  - 자연스러운 문장 구성
  - 프롬프트 최적화

- **v1.0** (초기 버전)
  - 기본 교육자료 및 퀴즈 생성 기능

## 개발자

성현준 권한대행에게 문의하세요

## 추가 개선 계획

- [ ] Claude API 통합 옵션
- [ ] 비용 추적 기능
- [ ] 배치 처리 기능
- [ ] 다국어 지원
- [ ] PDF 출력 기능

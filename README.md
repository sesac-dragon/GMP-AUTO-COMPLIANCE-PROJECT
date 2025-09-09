# GMP PDF → Text → Chunk → JSONL (v2 + regsection)

이번 버전은 **조항/섹션 인지형 청킹(regsection)**과 **풍부한 메타데이터**를 추가했습니다.

## 설치
```bash
pip install -r requirements.txt
```

## 빠른 실행
```bash
python extract_and_chunk_pdfs.py --zip data.zip --out chunks.jsonl --backend pypdf --chunk-by regsection --chunk-size 1400 --overlap 120 --jurisdiction-from-path
```

## 주요 기능
- **pypdf 우선 + pdfminer 폴백** (느린 PDF에서 안정적)
- **청킹 모드**: `auto|paragraph|sentence|char|regsection`
- **regsection**: 헤딩/조항 패턴(Annex/Section/§/1.2.3/제n조 등)을 인식해 **조항 경계 보존**  
  - 너무 큰 조항은 **하위 항목((1),(a),1.)** 기준으로 2차 분할
  - 동일 조항 내에서만 overlap 적용 → **경계 오염 방지**
- **메타데이터 강화**  
  - `jurisdiction`(경로로 추정, 옵션), `doc_date`, `doc_version`(본문/파일명에서 추정), `source_url`(선택 입력)  
  - `section_id`, `section_title`, `normative_strength`(MUST/SHOULD/MAY) 자동 라벨

## Source Map(선택)
원본 URL/정식 날짜/버전을 갖고 있으면 JSONL/CSV로 매핑 가능:
- 키: `path` 또는 `filename` 또는 `stem`
- 값: `source_url, doc_date, doc_version`

예) JSONL
```json
{"filename":"Annex_1_2022.pdf","source_url":"https://.../Annex1.pdf","doc_date":"2022-08-25","doc_version":"Rev 1"}
```

실행:
```bash
python extract_and_chunk_pdfs.py --zip data.zip --out chunks.jsonl --source-map source_map.jsonl --jurisdiction-from-path
```

## 출력 스키마(JSONL)
- `id, doc_id, source_path, title`
- `jurisdiction, doc_date, doc_version, source_url`
- `section_id, section_title, normative_strength`
- `page_start, page_end, chunk_index, text`

## 추천 파라미터
- **정책/규정 RAG**: `--chunk-by regsection --chunk-size 1400 --overlap 120`
- **문장 중심 QA**: `--chunk-by sentence --chunk-size 900 --overlap 120`
- **서식 난해/OCR 뒤 섞임**: `--chunk-by char --chunk-size 1000 --overlap 150`

## 주의
- 스캔본(이미지 PDF)은 텍스트가 비어 나옵니다(OCR 필요). 필요 시 Tesseract 연동판 요청 주세요.

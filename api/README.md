# api

FastAPI 마스킹 서버 (담당: 강선우)

- `app/` — 엔드포인트, 입력 검증, 정규식 탐지, NER 추론, 마스킹
- `tests/` — 가짜 데이터로만 테스트
- 422 오류 핸들러는 FastAPI 기본값을 쓰지 않고 **입력 원문을 응답·로그에서 제거**
- 모델 파일은 git에 올리지 않고 docker build 때 S3 `models/pii-ner/<version>/`에서 받아 포함

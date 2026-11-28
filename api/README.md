# api

FastAPI 마스킹 서버 (담당: 강선우)

- `app/main.py` — 엔드포인트, 입력 검증, 오류 형식, 요청 로그, 마스킹
- `app/regex_detect.py` — 정규식 탐지 (RRN·PHONE·EMAIL·ACCOUNT)
- `tests/` — 가짜 데이터로만 테스트
- 422 오류 핸들러는 FastAPI 기본값을 쓰지 않고 **입력 원문을 응답·로그에서 제거**
- 모델 파일은 git에 올리지 않고 docker build 때 S3 `models/pii-ner/<version>/`에서 받아 포함

## 로컬 실행

Python 3.11 이상(코드가 `http.HTTPMethod`를 쓰고, fastapi·starlette도 3.11 이상을 요구한다).

```bash
cd api
pip install -r requirements-dev.txt
pytest -q
uvicorn app.main:app --port 8000 --no-access-log
```

- 서버는 꼭 `uvicorn app.main:app` 명령으로 띄운다(Dockerfile을 만들 때 CMD도 이 형식으로). 파이썬 안에서 `from app.main import app` 뒤 `uvicorn.run(app)`을 부르면 uvicorn 접속 로그가 다시 켜지는데, 이 로그는 주소를 쿼리까지 그대로 찍는다.
- 지금은 `S3_BUCKET`이 비어 있는 **로컬 모드만** 있다. S3·DynamoDB 저장, 409 중복 검사, `/results` 조회는 배포 주에 붙인다(그 전까지 `/results`는 항상 404).

## 명세(docs/api-spec.md)와 다르거나 명세에 없는 동작

- **v0에는 주소(ADDRESS) 탐지가 없다.** 명세 0절과 todo.md는 v0·기준선에 도로명 주소 정규식을 넣기로 돼 있는데 아직 안 만들었다. v0 채점에서 ADDRESS 재현율 0은 이 때문이다.
- `/results/{id}`는 로컬 모드에서도 id가 UUID v4가 아니면 404가 아니라 422 `INVALID_REQUEST_ID`다(명세 3절 "항상 404"와 다름).
- `/mask/file`에서 파일 칸이 빠지는 등 형식이 틀리면 422 `INVALID_REQUEST`다(명세 2절 오류 목록에는 없고 5절 표에는 있음).
- `/mask/file`에 `request_id`를 빈 글자로 보내면 안 보낸 것으로 보고 서버가 새 id를 만든다(JSON `/mask`의 `""`는 422 `INVALID_REQUEST_ID`).
- FastAPI 기본 문서 페이지 `/docs`·`/openapi.json`이 열려 있다. 요청 로그에는 남기지 않는다.
- 404·405 오류 코드는 `NOT_FOUND`·`METHOD_NOT_ALLOWED`다(명세 코드표에 없어서 HTTP 상태 이름을 씀).
- 주소 끝 슬래시(`/mask/`)는 다른 주소로 넘기지 않고 404다.
- `/health` 성공 요청은 요청 로그를 남기지 않는다(ECS 헬스 체크가 로그와 성공 건수 지표를 덮지 않게). `/health`로 온 오류(405 등)는 남긴다.
- 마스킹 규칙 2의 "공백"에는 줄바꿈도 들어간다. 번호 두 개가 줄바꿈으로만 떨어져 있으면 하나로 합친다.
- `/mask/file`은 맨 앞 BOM을 떼고 읽는다. 위치는 뗀 텍스트 기준이다.

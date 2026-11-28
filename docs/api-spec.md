# GARIM API 명세 (v0.2.1)

> 작성: 김승하 · 리뷰: 강선우, 윤경화 · 확정 11/24
> 이 문서가 API·UI·채점 스크립트의 공통 기준입니다. 형식을 바꾸려면 이 문서를 먼저 PR로 고칩니다.

## 0. 공통

| 항목 | 내용 |
| --- | --- |
| Base URL | 로컬 `http://localhost:8000` / 배포 `http://<Fargate 퍼블릭 IP>:8000` |
| 인증 | 없음. 보안 그룹에서 허용한 IP(/32)만 접근 가능 (데모 기간 한계로 명시) |
| 인코딩 | 요청·응답 모두 UTF-8 JSON (`/mask/file` 요청만 multipart) |
| request_id | UUID v4 문자열. 요청에 넣으면 그 값을 쓰고, 없으면 서버가 만듭니다. **오류 응답에도 항상 포함**됩니다 (Logs Insights 검색용). 받은 값이 UUID v4가 아니면(`INVALID_REQUEST_ID`) 받은 값을 돌려주지 않고 **서버가 새로 만든 id**를 넣습니다 |
| 원문 보호 | 입력 원문은 **어떤 응답·로그·저장소에도 남기지 않습니다.** 오류 응답에도 받은 값을 넣지 않습니다 |

### 탐지 항목 (`type`)

| type | 마스킹 표시 | 탐지 방법 |
| --- | --- | --- |
| `NAME` | `[이름]` | NER |
| `ADDRESS` | `[주소]` | NER (v0·기준선은 도로명 정규식) |
| `RRN` | `[주민등록번호]` | 정규식 |
| `PHONE` | `[전화번호]` | 정규식 |
| `EMAIL` | `[이메일]` | 정규식 |
| `ACCOUNT` | `[계좌번호]` | 정규식 + 주변 단어("계좌", "입금" 등) |

각 type에 무엇을 정답으로 보는지는 [7. 채점 기준](#7-채점-기준)에 있습니다.

### 탐지 위치 (`entities`)

```json
{ "type": "NAME", "start": 4, "end": 7, "source": "ner" }
```

- `start`, `end`는 **입력 원문** 기준 글자 위치입니다 (Python `str` 인덱스, `start` 포함 / `end` 미포함).
- 위치는 **유니코드 코드포인트 기준**입니다. JS는 이모지 등을 2칸으로 세므로 `text.slice(start, end)` 대신 `Array.from(text).slice(start, end).join("")`로 자릅니다.
- 위치만 담고 **탐지된 글자 자체는 넣지 않습니다.**
- `source`: `regex` 또는 `ner`
- 평가셋 정답 JSON도 같은 형식(`type`, `start`, `end`)을 씁니다. 채점은 이 둘을 비교합니다.

### 마스킹 규칙

1. 정규식과 NER 결과가 겹치면 **정규식 결과를 우선**합니다. 이때 NER 구간 전체를 버리지 않고, **겹친 부분만 잘라내고 나머지는 원래 type으로 남깁니다** (재현율 우선: 구간을 버리면 그 부분이 그대로 노출됨).
   - 예: NER `ADDRESS 10~30`, 정규식 `PHONE 20~25` → `ADDRESS 10~20`, `PHONE 20~25`, `ADDRESS 25~30`
2. 같은 종류 구간이 겹치거나, 맞닿아 있거나, **사이에 공백만 있으면** 하나로 합칩니다 (`[주소] [주소]` 방지). 합친 구간에 정규식 결과가 하나라도 있으면 `source`는 `regex`입니다.
3. 각 탐지 구간을 표의 마스킹 표시로 바꿉니다.

### model_version

`v0` (정규식만) / `baseline` (공개 NER + 정규식) / `v1` (자체 학습 NER + 정규식). 모델 sha256은 `/health`에서 확인합니다.

### 로컬 모드

환경변수 `S3_BUCKET`이 비어 있으면 S3·DynamoDB 저장을 건너뜁니다 (AWS 없이 v0 실행, 채점 스크립트 로컬 테스트용).

- `/mask`, `/mask/file`은 정상 응답합니다. 저장 기록이 없으므로 중복 검사(409)는 하지 않습니다.
- `/results/{request_id}`는 항상 404 `RESULT_NOT_FOUND`입니다.

---

## 1. POST /mask

텍스트를 마스킹합니다. **채점은 이 엔드포인트로만 합니다** (2번 참고).

**요청** `Content-Type: application/json`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `text` | string | O | 1자 이상 5,000자 이하 |
| `request_id` | string | X | UUID v4. 없으면 서버가 생성 |

```json
{
  "text": "계약자 김민수(010-1234-5678)는 서울특별시 강남구 테헤란로 123에 거주한다."
}
```

**응답 200**

```json
{
  "request_id": "6f1c2a8e-3b4d-4e5f-9a10-7b2c3d4e5f60",
  "status": "SUCCESS",
  "model_version": "v1",
  "masked_text": "계약자 [이름]([전화번호])는 [주소]에 거주한다.",
  "entities": [
    { "type": "NAME",    "start": 4,  "end": 7,  "source": "ner" },
    { "type": "PHONE",   "start": 8,  "end": 21, "source": "regex" },
    { "type": "ADDRESS", "start": 24, "end": 42, "source": "ner" }
  ],
  "entity_counts": { "NAME": 1, "PHONE": 1, "ADDRESS": 1 },
  "char_count": 49,
  "latency_ms": 38,
  "created_at": "2026-12-14T05:12:30Z"
}
```

| 필드 | 설명 |
| --- | --- |
| `masked_text` | 마스킹된 텍스트. S3 `masked/{날짜}/{request_id}.txt`에도 저장 |
| `entities` | 탐지 위치 목록 (위 형식). **항상 포함** (채점, UI 강조 표시에 사용) |
| `entity_counts` | 종류별 탐지 개수. 0개인 종류는 생략 |
| `char_count` | 입력 글자 수 |
| `latency_ms` | 서버 처리 시간 (검증 ~ 마스킹 완료) |

**오류**: 422 (`EMPTY_TEXT`, `TEXT_TOO_LONG`, `INVALID_REQUEST`, `INVALID_REQUEST_ID`), 409, 503, 500

---

## 2. POST /mask/file

.txt 파일을 마스킹합니다. 응답은 `/mask`와 같습니다.

**요청** `Content-Type: multipart/form-data`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `file` | file | O | 확장자 `.txt`, UTF-8, 100KB(102,400바이트) 이하. 디코딩한 텍스트도 `/mask`와 같이 **5,000자 이하** |
| `request_id` | string | X | UUID v4 |

```bash
curl -X POST http://localhost:8000/mask/file -F "file=@contract.txt"
```

- **디코딩 기준**: 서버는 파일을 **`utf-8-sig`로 디코딩**합니다 (맨 앞 BOM이 있으면 제거, 없으면 UTF-8과 같음). 줄바꿈(`\r\n`)은 **바꾸지 않고 그대로** 둡니다. 이 방식으로 읽을 수 없으면 422 `INVALID_ENCODING`입니다.
- `entities` 위치와 5,000자 제한은 위 기준으로 디코딩한 텍스트 기준입니다. UI 등 클라이언트가 파일 결과에 위치를 적용할 때도 **같은 방식(`utf-8-sig`, 줄바꿈 유지)으로 디코딩한 텍스트**에 적용합니다.
- 클라이언트마다 파일을 읽는 방식이 달라질 수 있으므로, **채점에는 이 엔드포인트를 쓰지 않습니다.**

**오류**: 422 (`INVALID_FILE_TYPE`, `FILE_TOO_LARGE`, `INVALID_ENCODING`, `EMPTY_TEXT`, `TEXT_TOO_LONG`, `INVALID_REQUEST_ID`), 409, 503, 500

---

## 3. GET /results/{request_id}

처리 기록(DynamoDB)과 마스킹본(S3)을 다시 조회합니다.

**응답 200**

```json
{
  "request_id": "6f1c2a8e-3b4d-4e5f-9a10-7b2c3d4e5f60",
  "status": "SUCCESS",
  "model_version": "v1",
  "masked_text": "계약자 [이름]([전화번호])는 [주소]에 거주한다.",
  "entity_counts": { "NAME": 1, "PHONE": 1, "ADDRESS": 1 },
  "char_count": 49,
  "latency_ms": 38,
  "created_at": "2026-12-14T05:12:30Z"
}
```

- `entities`(위치)는 저장하지 않으므로 재조회 응답에는 없습니다.
- 마스킹본은 DynamoDB에 저장한 `s3_key`로 찾습니다.
- 30일이 지나 S3 마스킹본이 삭제됐으면 `masked_text`는 `null`입니다.
- 로컬 모드에서는 항상 404입니다.

**오류**: 404 `RESULT_NOT_FOUND`, 422 `INVALID_REQUEST_ID`, 500

### 저장 항목

| 저장소 | 내용 |
| --- | --- |
| DynamoDB `garim-requests` | PK `request_id`, `status`, `char_count`, `entity_counts`, `model_version`, `latency_ms`, `created_at`, `s3_key`. **원문 필드 없음** |
| S3 | `masked/{날짜}/{request_id}.txt` (마스킹본만, 30일 후 삭제) |

- **성공 요청만** 기록합니다. 422 등 오류 요청은 CloudWatch 로그로만 추적합니다 (오류 요청을 기록하면 입력을 고쳐 같은 request_id로 다시 보낼 때 409가 나기 때문).
- 같은 request_id 재기록은 조건부 쓰기로 막습니다 (409 `DUPLICATE_REQUEST_ID`).

---

## 4. GET /health

서버와 모델 상태를 확인합니다. ECS 헬스 체크에도 씁니다.

**응답 200** (모델 적재 완료)

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_version": "v1",
  "model_sha256": "3f9a2c1b7e4d"
}
```

**응답 503** (모델 적재 중): 위와 같은 형식에 `"status": "loading"`, `"model_loaded": false`

- `model_sha256`은 앞 12자리만 반환합니다.
- 모델은 서버를 띄운 뒤 백그라운드로 적재합니다. 적재 중 `/mask` 요청은 503 `MODEL_NOT_READY`입니다.
- `v0`은 모델이 없으므로 `"model_loaded": true`, `"model_sha256": null`입니다.

---

## 5. 오류 응답

모든 오류는 같은 형식입니다. **받은 입력값은 절대 넣지 않습니다.** FastAPI 기본 422 핸들러를 덮어써서 이 형식으로 바꿉니다.

```json
{
  "request_id": "6f1c2a8e-3b4d-4e5f-9a10-7b2c3d4e5f60",
  "status": "FAILED",
  "error": {
    "code": "TEXT_TOO_LONG",
    "message": "텍스트는 5,000자 이하여야 합니다."
  }
}
```

| HTTP | code | 상황 |
| --- | --- | --- |
| 422 | `EMPTY_TEXT` | 빈 값 또는 공백만 있음 |
| 422 | `TEXT_TOO_LONG` | 5,000자 초과 |
| 422 | `INVALID_FILE_TYPE` | `.txt`가 아닌 파일 |
| 422 | `FILE_TOO_LARGE` | 100KB 초과 |
| 422 | `INVALID_ENCODING` | UTF-8로 읽을 수 없음 |
| 422 | `INVALID_REQUEST_ID` | request_id가 UUID v4 형식이 아님. 응답의 `request_id`는 서버가 새로 만든 값 |
| 422 | `INVALID_REQUEST` | 필수 필드 누락, 타입 오류 등 그 밖의 형식 오류 |
| 409 | `DUPLICATE_REQUEST_ID` | 이미 처리된 request_id (DynamoDB 조건부 쓰기 실패) |
| 404 | `RESULT_NOT_FOUND` | 조회한 request_id 기록 없음 (로컬 모드에서는 항상) |
| 503 | `MODEL_NOT_READY` | 모델 적재 전 요청 |
| 500 | `INTERNAL_ERROR` | 처리 중 예외. 메시지에 예외 내용을 넣지 않음 |

---

## 6. 요청 로그 (CloudWatch)

요청마다 JSON 한 줄을 남깁니다. 로그 지표 필터와 Logs Insights가 이 필드 이름을 기준으로 동작합니다.

```json
{
  "timestamp": "2026-12-14T05:12:30Z",
  "request_id": "6f1c2a8e-3b4d-4e5f-9a10-7b2c3d4e5f60",
  "endpoint": "POST /mask",
  "http_status": 200,
  "status": "SUCCESS",
  "error_code": null,
  "model_version": "v1",
  "latency_ms": 38,
  "char_count": 49,
  "entity_counts": { "NAME": 1, "PHONE": 1, "ADDRESS": 1 },
  "exception": null
}
```

- 원문, 마스킹본, 탐지된 글자는 로그에 남기지 않습니다.
- `exception`에는 예외 **클래스 이름만** 남깁니다 (예: `"ClientError"`).
- 지표 필터: `status = "SUCCESS"` → success_count, `status = "FAILED"` → error_count, `latency_ms` → latency_ms

---

## 7. 채점 기준

평가셋 정답과 학습 라벨은 모두 이 기준으로 만듭니다.

### 맞음 판정

- **type이 같고**, 예측 구간(여러 개면 합친 것)이 **정답 구간을 빠짐없이 덮으면** 맞음입니다. 경계가 정답보다 넓어도 맞음으로 봅니다 (예: 정답 "테헤란로 123", 예측 "테헤란로 123에" → 맞음).
- 채점 입력은 `/mask`(JSON `text`)로만 보냅니다.

### 정답 범위

| type | 정답에 포함 | 제외 |
| --- | --- | --- |
| `ADDRESS` | 시·도부터 번지까지. 동·호수·층 포함 | "성북구에 사는"처럼 지역 이름만 있는 경우 |
| `NAME` | 이름만 | "님", "씨", "고객님" 같은 호칭 |
| `RRN` | 앞 6자리 + 뒤 7자리 전체 (사이 하이픈·공백 포함) | 법인등록번호 (아래 참고) |
| `PHONE` | 번호 전체 | 앞뒤 괄호 |
| `EMAIL` | 주소 전체 | 앞뒤 괄호 |
| `ACCOUNT` | 숫자 부분만 | 은행 이름 |

- **정답 대상 아님**: 대표번호(1588 등), 주문번호, 송장번호, 금액, 날짜
- **법인등록번호**: 개인정보가 아니므로 RRN 정답에서 제외합니다. 주민번호와 모양이 같아 정규식에 RRN으로 잡히더라도 **틀린 것으로 치지 않습니다.**

---

## 변경 이력

- **v0.2.1 (11/28)**: `/mask/file` 디코딩 기준 명시 (`utf-8-sig`, 줄바꿈 유지). PR #23 리뷰에서 UI 강조 위치가 어긋날 수 있는 문제 발견
- **v0.2 (11/24 확정)**: PR #2 리뷰 반영. 리뷰 항목 4개 결정(422 미기록, 파일 5,000자 제한, `entities` 항상 포함, 정규식 우선 + 겹친 부분만 잘라냄), 같은 종류 인접 구간 합침, 위치 코드포인트 기준, `INVALID_REQUEST_ID` 시 서버 생성 id, 로컬 모드, DynamoDB `created_at`·`s3_key`, v0 `/health`, 채점 기준(7절) 추가
- **v0.1 (11/23)**: 초안

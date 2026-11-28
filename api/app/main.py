"""GARIM 마스킹 API (명세 docs/api-spec.md v0.2).

원문 보호: 입력 원문은 어떤 응답·로그에도 넣지 않는다. 오류 응답도 받은 값을 돌려주지 않는다.
"""
import json
import logging
import os
import time
import uuid
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from http import HTTPMethod, HTTPStatus

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.regex_detect import detect

MODEL_VERSION = "v0"
MAX_CHARS = int(os.getenv("MAX_CHARS", "5000"))
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", "102400"))
INVALID_REQUEST_MESSAGE = "요청 형식이 올바르지 않습니다."
LABELS = {
    "NAME": "[이름]", "ADDRESS": "[주소]", "RRN": "[주민등록번호]",
    "PHONE": "[전화번호]", "EMAIL": "[이메일]", "ACCOUNT": "[계좌번호]",
}

# 끝 슬래시 자동 이동(/mask/ → 307 → /mask)을 끈다. 켜 두면 요청 1번이 로그 2줄(성공 건수 2배)이 되고,
# 307 Location 헤더가 쿼리를 그대로 되돌린다. 주소를 틀리면 404로 바로 드러나게 한다
app = FastAPI(title="GARIM", redirect_slashes=False)
# uvicorn 접속 로그는 주소를 쿼리까지 그대로 찍는다("GET /mask?text=..."). 실행 옵션을 빠뜨려도 꺼지게 코드에서 끈다
# (`uvicorn app.main:app`으로 띄울 때 기준. 파이썬 안에서 이 모듈을 import한 뒤 uvicorn.run()을 부르면 다시 켜진다)
# 대신 요청마다 아래 log_request가 원문 없는 JSON 한 줄을 남긴다(명세 6절)
logging.getLogger("uvicorn.access").disabled = True
# python-multipart는 깨진 업로드를 받으면 JSON이 아닌 경고 줄을 찍고, 거기에 입력 바이트 값이 따라 나온다
logging.getLogger("python_multipart").setLevel(logging.ERROR)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def is_uuid4(value) -> bool:
    # 소문자·하이픈 표준 형태만 받는다. 대문자 등을 받아 고쳐 쓰면 보낸 id와 응답 id가 달라진다
    if not isinstance(value, str):
        return False
    try:
        u = uuid.UUID(value)
    except ValueError:
        return False
    return u.version == 4 and str(u) == value


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    if not getattr(request.state, "request_id", None):
        request.state.request_id = str(uuid.uuid4())
    request.state.error_code = code
    return JSONResponse(
        status_code=status,
        content={"request_id": request.state.request_id, "status": "FAILED", "error": {"code": code, "message": message}},
    )


def set_request_id(request: Request, value) -> None:
    # 받은 값이 UUID v4가 아니면 받은 값을 돌려주지 않고 서버가 새로 만든 id를 쓴다(명세 0절)
    if value is None:
        request.state.request_id = str(uuid.uuid4())
    elif is_uuid4(value):
        request.state.request_id = value
    else:
        request.state.request_id = str(uuid.uuid4())
        raise ApiError(422, "INVALID_REQUEST_ID", "request_id는 UUID v4 형식이어야 합니다.")


@app.middleware("http")
async def log_request(request: Request, call_next):
    start = time.perf_counter()
    exception = None
    try:
        resp = await call_next(request)
    except Exception as exc:
        # Starlette 기본 500 처리는 응답을 보낸 뒤 예외를 다시 던져서, uvicorn이 예외 메시지(입력이 섞일 수 있음)를
        # 로그에 찍는다. 여기서 삼키고 로그에는 예외 클래스 이름만 남긴다(명세 6절)
        exception = type(exc).__name__
        resp = error_response(request, 500, "INTERNAL_ERROR", "처리 중 오류가 발생했습니다.")
    # API 요청과 모든 오류에는 request_id가 붙는다. 없는 건 헬스 체크 성공(ECS가 30초마다 부름)과
    # /docs·/openapi.json뿐이라 남기지 않는다. 남기면 로그와 성공 건수 지표가 이걸로 덮인다
    if not getattr(request.state, "request_id", None):
        return resp
    # 주소는 실제 경로가 아니라 라우트 모양("POST /mask")으로 남긴다. 실제 경로·메서드 자리에는 아무 글자나 들어올 수 있다
    route = request.scope.get("route")
    method = request.method if request.method in HTTPMethod.__members__ else "OTHER"
    state = request.state
    print(json.dumps({
        "timestamp": utc_now(),
        "request_id": getattr(state, "request_id", None),
        "endpoint": f"{method} {route.path}" if route else None,
        "http_status": resp.status_code,
        "status": "SUCCESS" if resp.status_code < 400 else "FAILED",
        "error_code": getattr(state, "error_code", None),
        "model_version": MODEL_VERSION,
        "latency_ms": getattr(state, "latency_ms", round((time.perf_counter() - start) * 1000)),
        "char_count": getattr(state, "char_count", None),
        "entity_counts": getattr(state, "entity_counts", None),
        "exception": exception,
    }), flush=True)
    return resp


@app.exception_handler(ApiError)
async def on_api_error(request: Request, exc: ApiError):
    return error_response(request, exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def on_validation_error(request: Request, exc: RequestValidationError):
    # FastAPI 기본 422는 받은 값(input)을 그대로 돌려준다 → 오류 종류만 남긴다
    # body는 JSON이면 dict, /mask/file(multipart)이면 FormData. 둘 다 Mapping이라 request_id만 꺼내 본다
    body = exc.body if isinstance(exc.body, Mapping) else {}
    try:
        set_request_id(request, body.get("request_id"))
    except ApiError as e:
        return error_response(request, e.status, e.code, e.message)
    return error_response(request, 422, "INVALID_REQUEST", INVALID_REQUEST_MESSAGE)


@app.exception_handler(StarletteHTTPException)
async def on_http_error(request: Request, exc: StarletteHTTPException):
    # FastAPI가 본문을 못 읽으면(UTF-8 아님 등) 400을 낸다 → 명세의 "그 밖의 형식 오류"
    if exc.status_code == 400:
        return error_response(request, 422, "INVALID_REQUEST", INVALID_REQUEST_MESSAGE)
    # 404·405는 명세 코드표에 없어서 HTTP 상태 이름(NOT_FOUND 등)을 코드로 쓴다
    resp = error_response(request, exc.status_code, HTTPStatus(exc.status_code).name, "지원하지 않는 주소나 메서드입니다.")
    resp.headers.update(exc.headers or {})
    return resp


@app.get("/health")
def health():
    # v0은 모델이 없어서 항상 적재 완료로 본다(명세 4절)
    return {"status": "ok", "model_loaded": True, "model_version": MODEL_VERSION, "model_sha256": None}


def merge_same_type(text: str, entities: list[dict]) -> list[dict]:
    # 명세 마스킹 규칙 2: 같은 종류가 겹치거나 맞닿거나 사이에 공백만 있으면 하나로 합친다([전화번호] [전화번호] 방지)
    merged = []
    for e in sorted(entities, key=lambda e: e["start"]):
        last = merged[-1] if merged else None
        if last and last["type"] == e["type"] and not text[last["end"]:e["start"]].strip():
            last["end"] = max(last["end"], e["end"])
            if e["source"] == "regex":
                last["source"] = "regex"
        else:
            merged.append(dict(e))
    return merged


def apply_masks(text: str, entities: list[dict]) -> str:
    parts, pos = [], 0
    for e in entities:
        parts += [text[pos:e["start"]], LABELS[e["type"]]]
        # 구간이 겹쳐 들어와도(지금은 detect가 합쳐서 없음, NER을 붙이면 생길 수 있음) 이미 가린 글자를 다시 내보내지 않는다
        pos = max(pos, e["end"])
    return "".join(parts) + text[pos:]


def mask_text(request: Request, text: str) -> dict:
    # /mask와 /mask/file이 같이 쓴다. latency_ms는 여기(검증)부터 마스킹 끝까지(명세 1절)
    start = time.perf_counter()
    try:
        # 짝 없는 서로게이트(JS에서 이모지를 반만 자른 경우)는 응답을 만들 때 500이 난다 → 형식 오류로 막는다
        text.encode("utf-8")
    except UnicodeEncodeError:
        raise ApiError(422, "INVALID_REQUEST", INVALID_REQUEST_MESSAGE)
    request.state.char_count = len(text)
    if not text.strip():
        raise ApiError(422, "EMPTY_TEXT", "텍스트가 비어 있습니다.")
    if len(text) > MAX_CHARS:
        raise ApiError(422, "TEXT_TOO_LONG", f"텍스트는 {MAX_CHARS:,}자 이하여야 합니다.")
    entities = merge_same_type(text, detect(text))
    masked = apply_masks(text, entities)
    request.state.entity_counts = dict(Counter(e["type"] for e in entities))
    request.state.latency_ms = round((time.perf_counter() - start) * 1000)
    return {
        "request_id": request.state.request_id,
        "status": "SUCCESS",
        "model_version": MODEL_VERSION,
        "masked_text": masked,
        "entities": entities,
        "entity_counts": request.state.entity_counts,
        "char_count": len(text),
        "latency_ms": request.state.latency_ms,
        "created_at": utc_now(),
    }


class MaskRequest(BaseModel):
    text: str
    request_id: str | None = None


@app.post("/mask")
def mask(req: MaskRequest, request: Request):
    set_request_id(request, req.request_id)
    return mask_text(request, req.text)


@app.post("/mask/file")
async def mask_file(request: Request, file: UploadFile, request_id: str | None = Form(None)):
    set_request_id(request, request_id)
    # 파일 이름은 응답·로그에 넣지 않는다(이름에도 개인정보가 들어갈 수 있다)
    if not (file.filename or "").lower().endswith(".txt"):
        raise ApiError(422, "INVALID_FILE_TYPE", ".txt 파일만 받습니다.")
    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ApiError(422, "FILE_TOO_LARGE", f"파일은 {MAX_FILE_BYTES // 1024}KB 이하여야 합니다.")
    try:
        # 메모장이 맨 앞에 붙이는 BOM은 떼고 읽는다. 위치는 이렇게 읽은 텍스트 기준(명세 2절)
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ApiError(422, "INVALID_ENCODING", "UTF-8 텍스트 파일만 받습니다.")
    return mask_text(request, text)


@app.get("/results/{request_id}")
def results(request_id: str, request: Request):
    set_request_id(request, request_id)
    # S3·DynamoDB 저장은 배포 주에 붙인다. 그 전까지는 명세의 로컬 모드처럼 항상 404
    raise ApiError(404, "RESULT_NOT_FOUND", "처리 기록이 없습니다.")

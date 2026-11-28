import json
import logging
import re
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app, is_uuid4

# 앱 밖으로 예외가 새면 TestClient가 테스트 안에서 다시 던진다(= 실제 서버라면 uvicorn이 로그에 찍는다)
client = TestClient(app)
JSON = {"content-type": "application/json"}
# 응답·로그에 원문이 새는지 볼 때 쓰는 가짜 번호
SECRET = "010-1234-5678"
# 오류 메시지는 정해진 문구만 나간다. 받은 값이 조금이라도 섞이면 여기서 걸린다
MESSAGES = {
    "EMPTY_TEXT": "텍스트가 비어 있습니다.",
    "TEXT_TOO_LONG": "텍스트는 5,000자 이하여야 합니다.",
    "INVALID_REQUEST": "요청 형식이 올바르지 않습니다.",
    "INVALID_REQUEST_ID": "request_id는 UUID v4 형식이어야 합니다.",
    "INTERNAL_ERROR": "처리 중 오류가 발생했습니다.",
    "NOT_FOUND": "지원하지 않는 주소나 메서드입니다.",
    "METHOD_NOT_ALLOWED": "지원하지 않는 주소나 메서드입니다.",
    "INVALID_FILE_TYPE": ".txt 파일만 받습니다.",
    "FILE_TOO_LARGE": "파일은 100KB 이하여야 합니다.",
    "INVALID_ENCODING": "UTF-8 텍스트 파일만 받습니다.",
    "RESULT_NOT_FOUND": "처리 기록이 없습니다.",
}


def assert_error(resp, status, code, sent_id=None):
    assert resp.status_code == status
    body = resp.json()
    assert body == {"request_id": body["request_id"], "status": "FAILED", "error": {"code": code, "message": MESSAGES[code]}}
    assert is_uuid4(body["request_id"])
    if sent_id is not None:
        assert body["request_id"] == sent_id
    assert SECRET not in resp.text
    return body


def test_health_v0():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "model_loaded": True, "model_version": "v0", "model_sha256": None}


def test_request_id_given_or_generated():
    rid = str(uuid.uuid4())
    for payload in ({"text": "안녕", "request_id": rid}, {"text": "안녕"}, {"text": "안녕", "request_id": None}):
        resp = client.post("/mask", json=payload)
        assert resp.status_code == 200
        assert is_uuid4(resp.json()["request_id"])
    assert client.post("/mask", json={"text": "안녕", "request_id": rid}).json()["request_id"] == rid


@pytest.mark.parametrize("bad_id", [
    SECRET, "", "abc", str(uuid.uuid4()).upper(), str(uuid.uuid1()), uuid.uuid4().hex,
    "{" + str(uuid.uuid4()) + "}", "urn:uuid:" + str(uuid.uuid4()), 123, ["x"],
])
def test_invalid_request_id_gets_new_id(bad_id):
    ids = [
        assert_error(client.post("/mask", json={"text": "안녕", "request_id": bad_id}), 422, "INVALID_REQUEST_ID")["request_id"]
        for _ in range(2)
    ]
    # 받은 값을 고쳐서(대문자→소문자 등) 돌려주면 두 번 다 같은 id가 나온다. 새로 만든 id면 매번 다르다
    assert ids[0] != ids[1]
    assert bad_id not in ids


@pytest.mark.parametrize("text", ["", " ", "\n\t", "\u3000"])
def test_empty_text(text):
    assert_error(client.post("/mask", json={"text": text}), 422, "EMPTY_TEXT")


def test_text_length_limit():
    # 글자 수는 코드포인트 기준(이모지 1개 = 1자)
    assert client.post("/mask", json={"text": "가" * 5000}).status_code == 200
    assert client.post("/mask", json={"text": "😀" * 5000}).status_code == 200
    assert_error(client.post("/mask", json={"text": SECRET + "가" * (5001 - len(SECRET))}), 422, "TEXT_TOO_LONG")
    assert_error(client.post("/mask", json={"text": "😀" * 5001}), 422, "TEXT_TOO_LONG")


@pytest.mark.parametrize("payload", [
    {}, {"request_id": str(uuid.uuid4())}, {"text": None}, {"text": 123}, {"text": [SECRET]},
    {"txt": SECRET}, [SECRET], SECRET,
])
def test_invalid_request_hides_input(payload):
    assert_error(client.post("/mask", json=payload), 422, "INVALID_REQUEST")


def test_invalid_request_keeps_valid_id():
    rid = str(uuid.uuid4())
    assert_error(client.post("/mask", json={"request_id": rid, "txt": SECRET}), 422, "INVALID_REQUEST", rid)
    assert_error(client.post("/mask", json={"request_id": rid, "text": " "}), 422, "EMPTY_TEXT", rid)


@pytest.mark.parametrize("raw, headers", [
    ('{"text": "' + SECRET, JSON),
    ('{"text": "' + SECRET + '"}', {}),
    ('{"text": "' + SECRET + '"}', {"content-type": "text/plain"}),
    # 아래 셋은 FastAPI가 본문을 못 읽어 400을 내는 경우(UTF-8 아님, 너무 깊은 중첩)
    (('{"text": "' + SECRET + '\xff"}').encode("latin-1"), JSON),
    (('{"text": "' + SECRET + ' 안녕"}').encode("euc-kr"), JSON),
    (b"[" * 100_000, JSON),
])
def test_broken_body_hides_input(raw, headers):
    assert_error(client.post("/mask", content=raw, headers=headers), 422, "INVALID_REQUEST")


@pytest.mark.parametrize("raw", ['{"text": "\\ud83d"}', '{"text": "' + SECRET + '\\udc00"}'])
def test_lone_surrogate_rejected(raw):
    assert_error(client.post("/mask", content=raw, headers=JSON), 422, "INVALID_REQUEST")
    assert client.post("/mask", content='{"text": "\\ud83d\\ude00"}', headers=JSON).status_code == 200


def test_unknown_route_and_method():
    assert_error(client.get("/" + SECRET), 404, "NOT_FOUND")
    resp = client.get("/mask")
    assert_error(resp, 405, "METHOD_NOT_ALLOWED")
    assert resp.headers["allow"] == "POST"
    assert_error(client.post("/health"), 405, "METHOD_NOT_ALLOWED")


def last_log(capsys):
    out = capsys.readouterr()
    assert SECRET not in out.out + out.err
    return json.loads(out.out.strip().splitlines()[-1])


@pytest.mark.parametrize("target", ["is_uuid4", "detect"])
def test_unexpected_error_hides_input(monkeypatch, capsys, target):
    def boom(*args):
        raise RuntimeError("bad input: " + SECRET)

    monkeypatch.setattr(main, target, boom)
    rid = str(uuid.uuid4())
    body = assert_error(client.post("/mask", json={"text": SECRET, "request_id": rid}), 500, "INTERNAL_ERROR")
    # id 검사 뒤(detect)에서 터지면 보낸 id가 유지된다
    if target == "detect":
        assert body["request_id"] == rid
    log = last_log(capsys)
    assert (log["request_id"], log["http_status"], log["error_code"], log["exception"]) == (
        body["request_id"], 500, "INTERNAL_ERROR", "RuntimeError")


# ---- 청크 2: 마스킹 결과 ----

def mask_ok(text):
    resp = client.post("/mask", json={"text": text})
    assert resp.status_code == 200
    return resp.json()


def test_spec_example_v0():
    # 명세 1절 예시 문장. v0은 이름(NER, v1에서)은 못 가리고 전화·주소(도로명 정규식)를 가린다. 주소 위치는 명세 예시와 같다(24~42)
    text = "계약자 김민수(010-1234-5678)는 서울특별시 강남구 테헤란로 123에 거주한다."
    body = mask_ok(text)
    assert set(body) == {"request_id", "status", "model_version", "masked_text", "entities",
                         "entity_counts", "char_count", "latency_ms", "created_at"}
    assert body["status"] == "SUCCESS" and body["model_version"] == "v0"
    assert body["masked_text"] == "계약자 김민수([전화번호])는 [주소]에 거주한다."
    assert body["entities"] == [{"type": "PHONE", "start": 8, "end": 21, "source": "regex"},
                                {"type": "ADDRESS", "start": 24, "end": 42, "source": "regex"}]
    assert body["entity_counts"] == {"PHONE": 1, "ADDRESS": 1}
    assert body["char_count"] == 49
    assert isinstance(body["latency_ms"], int) and body["latency_ms"] >= 0
    assert_utc_now(body["created_at"])


def assert_utc_now(stamp):
    # "2026-12-14T05:12:30Z" 형식 + 실제로 UTC 현재 시각(로컬 시각이면 9시간 어긋난다)
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", stamp)
    sent = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert abs((datetime.now(timezone.utc) - sent).total_seconds()) < 60


def test_all_regex_types_masked():
    fakes = {"EMAIL": "kim@example.com", "RRN": "900101-1234567", "ACCOUNT": "110-123-456789", "PHONE": SECRET}
    text = f"메일 {fakes['EMAIL']}, 주민번호 {fakes['RRN']}, 신한 계좌 {fakes['ACCOUNT']}, 연락처 {fakes['PHONE']}"
    body = mask_ok(text)
    assert body["masked_text"] == "메일 [이메일], 주민번호 [주민등록번호], 신한 계좌 [계좌번호], 연락처 [전화번호]"
    # 위치로 원문을 잘라 보면 정확히 그 가짜 값이어야 한다. 응답에는 위치만 있고 글자는 없다
    assert {e["type"]: text[e["start"]:e["end"]] for e in body["entities"]} == fakes
    assert all(set(e) == {"type", "start", "end", "source"} for e in body["entities"])
    assert body["entity_counts"] == {"EMAIL": 1, "RRN": 1, "ACCOUNT": 1, "PHONE": 1}
    for value in fakes.values():
        assert value not in body["masked_text"]


def test_no_pii_unchanged():
    body = mask_ok("안녕하세요. 내일 3시에 만나요.")
    assert body["masked_text"] == "안녕하세요. 내일 3시에 만나요."
    assert body["entities"] == [] and body["entity_counts"] == {}


@pytest.mark.parametrize("text, masked, spans", [
    # 같은 종류 사이에 공백만 있으면 하나로 합친다(명세 규칙 2)
    ("010-1111-2222 010-3333-4444", "[전화번호]", [(0, 27)]),
    ("010-1111-2222\n010-3333-4444 끝", "[전화번호] 끝", [(0, 27)]),
    # 공백 말고 다른 글자가 끼면 따로 둔다
    ("010-1111-2222, 010-3333-4444", "[전화번호], [전화번호]", [(0, 13), (15, 28)]),
    # 종류가 다르면 붙어 있어도 따로 둔다
    ("010-1111-2222 kim@example.com", "[전화번호] [이메일]", [(0, 13), (14, 29)]),
])
def test_merge_same_type(text, masked, spans):
    body = mask_ok(text)
    assert body["masked_text"] == masked
    assert [(e["start"], e["end"]) for e in body["entities"]] == spans
    assert sum(body["entity_counts"].values()) == len(spans)


def test_offsets_are_codepoints():
    # 이모지 1개 = 1칸. JS는 2칸으로 세므로 UI는 Array.from으로 잘라야 한다(명세 0절)
    text = "😀😀 " + SECRET
    body = mask_ok(text)
    assert body["entities"][0]["start"] == 3
    assert body["masked_text"] == "😀😀 [전화번호]"
    assert body["char_count"] == len(text) == 16


def test_merge_same_type_rules():
    # v0 /mask로는 못 만드는 입력(NER 섞임·포함 관계·순서 뒤섞임)을 함수에 직접 넣는다
    text = "서울시 강남구 테헤란로 1"
    entities = [
        {"type": "ADDRESS", "start": 8, "end": 12, "source": "regex"},
        {"type": "ADDRESS", "start": 0, "end": 14, "source": "ner"},
    ]
    assert main.merge_same_type(text, entities) == [{"type": "ADDRESS", "start": 0, "end": 14, "source": "regex"}]
    # 입력 목록은 건드리지 않는다
    assert entities[1] == {"type": "ADDRESS", "start": 0, "end": 14, "source": "ner"}


def test_apply_masks_overlap_does_not_leak():
    text = "주소 서울시 " + SECRET + " 테헤란로 1"
    entities = [{"type": "ADDRESS", "start": 3, "end": 26, "source": "ner"},
                {"type": "PHONE", "start": 7, "end": 20, "source": "regex"}]
    # 바깥 구간(주소) 안의 글자가 전화 표시 뒤에 다시 나오면 안 된다
    assert main.apply_masks(text, entities) == "주소 [주소][전화번호]1"


def test_address_masked_and_not_logged(capsys):
    # 주소는 [주소]로 가려지고, 요청 로그에는 종류별 개수만 남는다(명세 6절: 원문 글자 0)
    text = "배송지 서울시 강남구 테헤란로 123, 101동 202호 (연락처 " + SECRET + ")"
    body = mask_ok(text)
    assert body["masked_text"] == "배송지 [주소] (연락처 [전화번호])"
    out = capsys.readouterr().out
    assert '"ADDRESS": 1' in out and "테헤란로" not in out and SECRET not in out


def test_mask_worst_case_latency():
    # 띄어쓰기 없는 5,000자(시·군·구 나누기가 폭발하기 쉬운 꼴)도 요청 한 건이 1초 안에 끝난다
    for unit in ["시", "서울특별시 " * 8 + "1", "구" * 61 + "1", "세종특별자치시\n" * 6 + "가 1"]:
        body = mask_ok((unit * (5000 // len(unit) + 1))[:5000])
        assert body["latency_ms"] < 1000, unit[:6]


def test_request_log_lines(capsys):
    rid = str(uuid.uuid4())
    mask_ok_resp = client.post("/mask", json={"text": "연락처 " + SECRET, "request_id": rid})
    assert mask_ok_resp.status_code == 200
    log = last_log(capsys)
    assert set(log) == {"timestamp", "request_id", "endpoint", "http_status", "status", "error_code",
                        "model_version", "latency_ms", "char_count", "entity_counts", "exception"}
    assert log == {**log, "request_id": rid, "endpoint": "POST /mask", "http_status": 200, "status": "SUCCESS",
                   "error_code": None, "model_version": "v0", "latency_ms": mask_ok_resp.json()["latency_ms"],
                   "char_count": 17, "entity_counts": {"PHONE": 1}, "exception": None}
    assert_utc_now(log["timestamp"])

    assert_error(client.post("/mask", json={"text": SECRET + "가" * 5000}), 422, "TEXT_TOO_LONG")
    log = last_log(capsys)
    assert (log["status"], log["http_status"], log["error_code"], log["char_count"], log["entity_counts"]) == (
        "FAILED", 422, "TEXT_TOO_LONG", 5013, None)

    # 실제 경로가 아니라 라우트 모양만 남긴다. 없는 주소는 endpoint를 비운다
    assert_error(client.get("/" + SECRET + "?q=" + SECRET), 404, "NOT_FOUND")
    assert last_log(capsys)["endpoint"] is None

    # 메서드 자리에 넣은 글자도 남기지 않는다
    assert_error(client.request(SECRET, "/mask"), 405, "METHOD_NOT_ALLOWED")
    assert last_log(capsys)["endpoint"] == "OTHER /mask"

    # 헬스 체크 성공·문서 페이지는 남기지 않는다. 헬스 체크 주소로 온 오류는 남긴다
    for path in ("/health", "/docs", "/openapi.json"):
        assert client.get(path).status_code == 200
    assert capsys.readouterr().out == ""
    assert_error(client.post("/health"), 405, "METHOD_NOT_ALLOWED")
    assert last_log(capsys)["endpoint"] == "POST /health"


def test_uvicorn_access_log_off():
    # 접속 로그는 "GET /mask?text=..."처럼 쿼리까지 찍는다. 이 한 줄이 꺼지면 로그로 원문이 샐 수 있다
    assert logging.getLogger("uvicorn.access").disabled


def test_trailing_slash_not_redirected(capsys):
    # 끝 슬래시를 307로 넘기면 요청 1번이 로그 2줄(성공 건수 2배)이 되고 Location이 쿼리를 되돌린다
    resp = client.post("/mask/?q=" + SECRET, json={"text": "안녕"}, follow_redirects=False)
    assert_error(resp, 404, "NOT_FOUND")
    assert "location" not in resp.headers
    assert len(capsys.readouterr().out.strip().splitlines()) == 1


# ---- 청크 3: /mask/file, /results ----

def post_file(content: bytes, name="memo.txt", data=None):
    return client.post("/mask/file", files={"file": (name, content, "text/plain")}, data=data or {})


def test_mask_file_ok(capsys):
    rid = str(uuid.uuid4())
    text = "상담 기록\r\n연락처 " + SECRET
    resp = post_file(text.encode("utf-8"), name=SECRET + ".txt", data={"request_id": rid})
    assert resp.status_code == 200
    body = resp.json()
    assert body["request_id"] == rid
    assert body["masked_text"] == "상담 기록\r\n연락처 [전화번호]"
    # \r\n은 그대로 두고 센다(명세 2절: 서버가 읽은 텍스트 기준)
    assert body["entities"] == [{"type": "PHONE", "start": 11, "end": 24, "source": "regex"}]
    assert body["char_count"] == len(text)
    assert SECRET not in resp.text
    # 파일 이름에 든 번호도 로그에 안 남는다(last_log가 확인)
    log = last_log(capsys)
    assert (log["endpoint"], log["request_id"], log["char_count"]) == ("POST /mask/file", rid, len(text))


def test_mask_file_strips_bom_and_accepts_upper_ext():
    body = post_file(("\ufeff연락처 " + SECRET).encode("utf-8"), name="MEMO.TXT").json()
    assert body["masked_text"] == "연락처 [전화번호]"
    assert body["entities"][0]["start"] == 4


@pytest.mark.parametrize("content, name, code", [
    (SECRET.encode(), SECRET + ".csv", "INVALID_FILE_TYPE"),
    (SECRET.encode(), "memo.txt.exe", "INVALID_FILE_TYPE"),
    # 파일 이름이 없는 칸은 파일이 아니라 글자 칸으로 들어와서 형식 오류가 된다
    (SECRET.encode(), "", "INVALID_REQUEST"),
    # 100KB 경계: 102,400바이트는 파일 크기는 통과하고 글자 수(5,000자)에서 걸린다
    (b"a" * 102_401, "memo.txt", "FILE_TOO_LARGE"),
    (b"a" * 102_400, "memo.txt", "TEXT_TOO_LONG"),
    (("가" * 5001).encode(), "memo.txt", "TEXT_TOO_LONG"),
    (("연락처 " + SECRET).encode("euc-kr"), "memo.txt", "INVALID_ENCODING"),
    (b"\xff" + SECRET.encode(), "memo.txt", "INVALID_ENCODING"),
    (b"", "memo.txt", "EMPTY_TEXT"),
    ("\ufeff \r\n".encode(), "memo.txt", "EMPTY_TEXT"),
])
def test_mask_file_errors(content, name, code):
    # 어느 단계에서 걸려도 보낸 id는 유지한다
    rid = str(uuid.uuid4())
    assert_error(post_file(content, name=name, data={"request_id": rid}), 422, code, rid)


@pytest.mark.parametrize("content, name, rid, code", [
    # 두 조건을 같이 어기면 앞 단계 오류가 나간다: id → 확장자 → 100KB → UTF-8
    (b"hi", "memo.csv", SECRET, "INVALID_REQUEST_ID"),
    (b"a" * 102_401, "memo.csv", None, "INVALID_FILE_TYPE"),
    (b"\xff" * 102_401, "memo.txt", None, "FILE_TOO_LARGE"),
])
def test_mask_file_check_order(content, name, rid, code):
    assert_error(post_file(content, name=name, data={"request_id": rid} if rid else None), 422, code)


def test_mask_file_request_id():
    rid = str(uuid.uuid4())
    assert_error(post_file(b"hi", data={"request_id": SECRET}), 422, "INVALID_REQUEST_ID")
    # 파일이 빠진 형식 오류여도 보낸 id는 유지한다
    assert_error(client.post("/mask/file", data={"request_id": rid}), 422, "INVALID_REQUEST", rid)


@pytest.mark.parametrize("kwargs", [
    {"json": {"text": SECRET}},
    {"content": b"--x\r\nbroken " + SECRET.encode(), "headers": {"content-type": "multipart/form-data; boundary=x"}},
    {"content": SECRET.encode() + b"\r\n--x--\r\n", "headers": {"content-type": "multipart/form-data; boundary=x"}},
    {"data": {"file": SECRET}},
])
def test_mask_file_bad_body(kwargs, caplog):
    assert_error(client.post("/mask/file", **kwargs), 422, "INVALID_REQUEST")
    # python-multipart 경고(입력 바이트 값이 들어감)가 로그로 나가지 않는다
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_results_local_mode(capsys):
    rid = str(uuid.uuid4())
    assert_error(client.get("/results/" + rid), 404, "RESULT_NOT_FOUND", rid)
    assert last_log(capsys)["endpoint"] == "GET /results/{request_id}"
    body = assert_error(client.get("/results/" + SECRET), 422, "INVALID_REQUEST_ID")
    assert body["request_id"] != SECRET

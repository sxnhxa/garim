"""정규식으로 번호류 개인정보 위치를 찾는다. 반환 형식은 docs/api-spec.md의 entities와 같다."""
import re

# 전각 숫자·여러 대시·특수 공백을 ASCII로 1:1 바꾼다. 글자 수가 그대로라 위치는 원문 기준 그대로다
# (NFKC는 ㈜ -> (주)처럼 길이가 바뀌어서 쓰지 않는다)
_NORMALIZE = str.maketrans(
    "０１２３４５６７８９－‐‑‒–—−＋（）＠． 　",
    "0123456789-------+()@.  ",
)

# 번호 사이 구분자: 하이픈·점(양옆 공백 1칸까지), 공백 1칸, 없음 + 줄바꿈(윈도우 \r\n 포함)
# 탭·두 칸 공백은 안 받는다. 엑셀에서 복사한 표의 숫자 칸들이 번호로 이어 붙기 때문
# 한계: "100000 - 1500000원" 같은 쉼표 없는 금액 범위, 한 줄에 숫자 하나씩 쓴 목록은 번호로 잡힐 수 있다
SEP = r"(?: ?[-.] ?| ?)\r?\n?"

# 주민등록번호·외국인등록번호: 생년월일 6자리 + 구분자 + 뒷자리 첫 숫자 + 6자리
# 뒷자리 첫 숫자: 1·2 = 1900년대생, 3·4 = 2000년대생, 5~8 = 외국인
# 월 00~12, 일 00~31: Faker ko_KR ssn()이 00월·00일을 만들어서 00도 받는다
# 한계: 체크섬은 안 본다(재현율 우선). 날짜처럼 생긴 13자리 주문번호·바코드(880...)·법인등록번호도 잡힌다
RRN = re.compile(rf"(?<!\d)\d{{2}}(?:0\d|1[0-2])(?:[0-2]\d|3[01]){SEP}[1-8]\d{{6}}(?!\d)")

# 전화번호
# 시작: +82 / +82 (0) / +82-0 / (02) / 0
#   여는 괄호는 뒤에 "0 + 숫자 1~3개 + 닫는 괄호"가 있을 때만 구간에 넣는다(\((?=0\d{1,3}\))).
#   그래서 "(02)123-4567"은 괄호까지 잡고, "김민수(010-1234-5678)"은 괄호를 빼고 010부터 잡는다
# 앞자리: 휴대폰 식별번호 10·11·16~19, 서울 2, 지역 x1~x5, 인터넷전화 70, 안심번호 502~508
#   실제 지역번호는 31~33·41~44·51~55·61~64뿐인데 재현율 때문에 끝자리 1~5로 넓게 받는다
# 끝: 바로 뒤에 숫자가 더 붙으면 전화로 안 본다
#   "010-1234-5678-12"처럼 "-숫자"가 이어지는 건 계좌 단어가 있으면 계좌 패턴이 먼저 통째로 가져가고,
#   없으면 전화 부분이라도 가린다(재현율 우선)
PHONE = re.compile(
    rf"(?<![\d+])(?:\+82{SEP}(?:\(0\){SEP}|0)?|\((?=0\d{{1,3}}\))0|0)"
    rf"(?:1[016789]|2|[3-6][1-5]|70|50[2-8])(?:\){SEP}|{SEP})"
    rf"\d{{3,4}}{SEP}\d{{4}}(?!\d)"
)

# 이메일: 한글도 \w에 걸려서 영문·숫자를 직접 적는다. 첫 글자는 영문·숫자, 끝은 영문 2자 이상(.com, .kr)
EMAIL = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
)

# 계좌번호 후보: 숫자 10~14자리. 하이픈으로 끊거나, 공백으로 끊거나, 붙여 쓴 것(둘을 섞진 않는다)
# 하이픈형(붙여 쓴 것 포함)을 먼저 시도해서 "110123456789 12월"의 " 12"를 계좌에 붙이지 않는다
# 한계: 공백으로 끊은 계좌 뒤에 숫자가 오면("110 123 456789 12월") 14자리까지 이어 붙인다.
#       하이픈 친 16자리 카드번호가 계좌 단어 옆에 오면 앞 12~14자리가 계좌로 잡힌다
ACCOUNT = re.compile(r"(?<!\d)(?:\d(?:-?\d){9,13}|\d(?: ?\d){9,13})(?!\d)")

# 계좌 쪽 단어(번호 앞 20자·뒤 10자 안). 다른 뜻으로 거의 안 쓰는 말만. "은행"이 국민은행·우리은행 등을 덮는다
ACCOUNT_WORDS = re.compile(r"계좌|입금|송금|이체|은행|뱅크|농협|신한|새마을|우체국|수협|신협|씨티|SC제일|KB|NH|IBK")
# 평소에도 쓰는 은행 줄임말("우리 집", "하나 더")은 번호 바로 옆에 붙을 때만 계좌 단어로 친다
BANK_SHORT = "국민|우리|하나|기업|산업|부산|대구|경남|광주|전북|제주|카카오|토스"
BANK_SHORT_BEFORE = re.compile(rf"(?:{BANK_SHORT})[ :(]*$")
BANK_SHORT_AFTER = re.compile(rf"^[ (]*(?:{BANK_SHORT})")
# 주민번호·전화 쪽 단어. 계좌 단어보다 이쪽이 번호에 더 가까우면 계좌로 안 본다
OTHER_WORDS = re.compile(r"주민|외국인|생년월일|전화|연락처|폰|팩스|HP|TEL|Tel|FAX|Fax")


def _nearest(words, before, after):
    """번호에서 가장 가까운 단어까지 글자 수. 없으면 None"""
    dists = [len(before) - w.end() for w in words.finditer(before)]
    dists += [w.start() for w in words.finditer(after)]
    return min(dists, default=None)


def _is_account(norm, m):
    """계좌 단어가 있고, 주민번호·전화 단어보다 번호에 더 가까우면 계좌다
    예: "계좌 개설 시 주민번호 900101-1234567" -> '주민'이 더 가까워서 계좌 아님(주민번호로 감)
    한계: "계좌 정보 확인 후 900101-1234567"처럼 다른 단어 없이 계좌 단어만 근처에 있으면 계좌로 본다"""
    before = norm[max(0, m.start() - 20):m.start()]
    after = norm[m.end():m.end() + 10]
    acc = 0 if BANK_SHORT_BEFORE.search(before) or BANK_SHORT_AFTER.search(after) else _nearest(ACCOUNT_WORDS, before, after)
    other = _nearest(OTHER_WORDS, before, after)
    return acc is not None and (other is None or acc < other)


# 앞에 있을수록 우선. 세 번째 칸은 추가 조건(없으면 None)
# 이메일이 맨 앞인 건 "01012345678@example.com"을 전화로 잘라 내지 않으려고
# 계좌가 주민번호·전화보다 앞인 건 "입금 계좌 1002123456789"(날짜처럼 생긴 계좌)·"입금 계좌 010-1234-5678"(평생계좌)을
# 주민번호·전화로 잘못 붙이지 않으려고. 계좌 조건이 안 맞으면 그 숫자는 뒤의 주민번호·전화 패턴이 다시 본다
# 한계: 이미 잡힌 구간과 조금이라도 겹치면 뒤 패턴 결과는 통째로 버린다(정규식끼리는 부분 겹침이 드물다)
PATTERNS = [("EMAIL", EMAIL, None), ("ACCOUNT", ACCOUNT, _is_account), ("RRN", RRN, None), ("PHONE", PHONE, None)]


def detect(text: str) -> list[dict]:
    norm = text.translate(_NORMALIZE)
    found = []
    for typ, pattern, condition in PATTERNS:
        for m in pattern.finditer(norm):
            if condition and not condition(norm, m):
                continue
            if all(m.end() <= f["start"] or m.start() >= f["end"] for f in found):
                found.append({"type": typ, "start": m.start(), "end": m.end(), "source": "regex"})
    return sorted(found, key=lambda f: f["start"])

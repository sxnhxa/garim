# 실행: api 폴더에서 pytest (준비: pip install -r requirements-dev.txt)
from faker import Faker

from app.regex_detect import detect

fake = Faker("ko_KR")
Faker.seed(0)


def spans(text):
    return [(e["type"], text[e["start"]:e["end"]]) for e in detect(text)]


def test_faker_values_found_exactly():
    # Faker 형식은 하이픈형뿐이다(주민번호는 월 00~09·일 00~29·뒷자리 1·2만). 나머지 형태는 test_variants가 맡는다
    for _ in range(300):
        for typ, value in [("RRN", fake.ssn()), ("PHONE", fake.phone_number()), ("EMAIL", fake.email())]:
            text = f"고객 {fake.name()}님의 정보는 {value}입니다."
            assert spans(text) == [(typ, value)], text


def test_variants():
    cases = {
        # 주민번호: 구분자 변형, 2000년대생(3·4), 외국인(5~8), 10~12월·30~31일, 전각
        "9001011234567": "RRN",
        "900101 1234567": "RRN",
        "900101 - 1234567": "RRN",
        "900101-\n1234567": "RRN",
        "900101-\r\n1234567": "RRN",
        "001231-3234567": "RRN",
        "051031-4234567": "RRN",
        "900101-5234567": "RRN",
        "901130-7234567": "RRN",
        "901231-8234567": "RRN",
        "９００１０１－１２３４５６７": "RRN",
        # 전화: 구분자 변형, 국제번호, 괄호 국번, 안심번호, 전각·특수 공백·다른 대시
        "01012345678": "PHONE",
        "0212345678": "PHONE",
        "010 1234 5678": "PHONE",
        "010.1234.5678": "PHONE",
        "010 - 1234 - 5678": "PHONE",
        "010-1234-\n5678": "PHONE",
        "+82 10-1234-5678": "PHONE",
        "+821012345678": "PHONE",
        "+82-010-1234-5678": "PHONE",
        "+82 (0)10-1234-5678": "PHONE",
        "02-123-4567": "PHONE",
        "(02)123-4567": "PHONE",
        "031)234-5678": "PHONE",
        "0505-123-4567": "PHONE",
        "０１０－１２３４－５６７８": "PHONE",
        "010 1234 5678": "PHONE",
        "010　1234　5678": "PHONE",
        "010-1234-\r\n5678": "PHONE",
        "010–1234–5678": "PHONE",
    }
    for value, typ in cases.items():
        text = f"연락처 {value}로 보내 주세요"
        assert spans(text) == [(typ, value)], value


def test_not_detected():
    for text in [
        "수신자부담 080-123-4567로 문의",
        "정보이용료 060-123-4567",
        "991301-1234567",
        "900101-9234567",
        "12301012345678",
        "19001011234567",
        "010-1234-56789",
        "주문번호 1234567890123 배송 완료",
        "송장번호 123456789012",
        "번호\t수량\t금액\n02\t150\t3000",
        "총 02  1234  5678원",
        "단가 3@12.5",
        "lodash@4.17.21",
    ]:
        assert detect(text) == [], text


# 은행별 계좌 자릿수 모양(국민·신한·우리·하나·농협·카카오뱅크·토스뱅크·붙여 쓴 13자리)
ACCOUNT_FORMATS = [
    "######-##-######",
    "###-###-######",
    "####-###-######",
    "###-######-#####",
    "###-####-####-##",
    "####-##-#######",
    "####-####-####",
    "#############",
]


def test_accounts_found():
    # 계좌 단어가 번호 앞에 있을 때, 은행 이름이 뒤에 붙을 때, 정식 은행명일 때
    for _ in range(100):
        for fmt in ACCOUNT_FORMATS:
            value = fake.numerify(fmt)
            for text in [f"입금 계좌 {value}로 보내 주세요", f"{value} (국민) 홍길동", f"신한은행 {value}"]:
                assert spans(text) == [("ACCOUNT", value)], text


def test_account_or_not():
    cases = {
        "입금 계좌: 1002123456789": [("ACCOUNT", "1002123456789")],
        "입금 계좌 010-1234-5678": [("ACCOUNT", "010-1234-5678")],
        "평생계좌 010-1234-5678-12": [("ACCOUNT", "010-1234-5678-12")],
        "번호 010-1234-5678-12 확인": [("PHONE", "010-1234-5678")],
        "입금 계좌 123456789012345": [],
        "입금 계좌 123-45-6789": [],
        "이체 110 123 456789 부탁드립니다": [("ACCOUNT", "110 123 456789")],
        "110-123-456789 12월까지 입금": [("ACCOUNT", "110-123-456789")],
        "110123456789 12월까지 입금": [("ACCOUNT", "110123456789")],
        "농협 352-1234-5678-93": [("ACCOUNT", "352-1234-5678-93")],
        "카카오 3333-01-1234567": [("ACCOUNT", "3333-01-1234567")],
        "계좌 개설 시 주민번호 900101-1234567 필요": [("RRN", "900101-1234567")],
        "입금자 연락처 010-1234-5678": [("PHONE", "010-1234-5678")],
        "하나 더 적으면 900101-1234567": [("RRN", "900101-1234567")],
        "연락처 010-1234-5678, 계좌 110-123-456789": [("PHONE", "010-1234-5678"), ("ACCOUNT", "110-123-456789")],
    }
    for text, expected in cases.items():
        assert spans(text) == expected, text


def test_email_boundaries():
    cases = {
        "메일은minsu.kim@example.com으로 주세요.": "minsu.kim@example.com",
        "확인바랍니다.kim@example.com": "kim@example.com",
        "kim@example.com.": "kim@example.com",
        "kim@example.com-로": "kim@example.com",
        "-kim@example.co.kr": "kim@example.co.kr",
    }
    for text, value in cases.items():
        assert spans(text) == [("EMAIL", value)], text


def test_overlap_keeps_first_pattern():
    text = "01012345678@example.com"
    assert spans(text) == [("EMAIL", text)]


def test_many_in_one_text():
    values = [
        ("RRN", "900101-1234567"),
        ("PHONE", "010-1234-5678"),
        ("PHONE", "02-123-4567"),
        ("EMAIL", "kim@example.com"),
        ("ACCOUNT", "110-123-456789"),
    ]
    text = "주민번호 {}, 휴대폰 {}, 집 {}, 메일 {}, 신한은행 {} 입니다.".format(*(v for _, v in values))
    expected = []
    for typ, v in values:
        start = text.index(v)
        expected.append({"type": typ, "start": start, "end": start + len(v), "source": "regex"})
    assert detect(text) == expected


def test_spec_example_positions():
    text = "계약자 김민수(010-1234-5678)는 서울특별시 강남구 테헤란로 123에 거주한다."
    assert detect(text) == [{"type": "PHONE", "start": 8, "end": 21, "source": "regex"}]

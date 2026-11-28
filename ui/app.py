import html
import os
import re
from urllib.parse import quote

import requests
import streamlit as st
from dotenv import load_dotenv

st.set_page_config(page_title="GARIM", page_icon="🛡️", layout="wide",
                   initial_sidebar_state="collapsed")

load_dotenv()
API_URL = os.environ.get("GARIM_API_URL", "http://localhost:8000")

LABEL = {"NAME": "이름", "ADDRESS": "주소", "RRN": "주민등록번호",
         "PHONE": "전화번호", "EMAIL": "이메일", "ACCOUNT": "계좌번호"}
# 형광펜 색: (배경, 글자) — 밝기는 맞추고 색상만 다르게
COLORS = {
    "NAME": ("#f7e9e9", "#9b3b3b"), "ADDRESS": ("#f6eedf", "#85591a"), "RRN": ("#eeebf8", "#5a479e"),
    "PHONE": ("#e7eff8", "#2e5b8f"), "EMAIL": ("#e6f2eb", "#2f6a48"), "ACCOUNT": ("#f3f0dd", "#6c6224"),
}
COLOR_BY_LABEL = {LABEL[t]: COLORS[t] for t in LABEL}
EXAMPLE = ("계약자 홍길동(010-0000-0000)은 서울특별시 중구 세종대로 110에 거주한다.\n"
           "연락 메일은 hong@example.com 이고,\n"
           "보증금은 국민은행 계좌 123456-78-901234 로 입금한다.")

# 디자인 규칙: 글씨체 Pretendard 하나 / 글자 크기 24·16·14·12 / 간격 8의 배수 / 강조색 하나(네이비)
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
:root { --ink: #111827; --sub: #6b7280; --muted: #9ca3af; --line: #e5e7eb; --bg: #f7f8fa; --accent: #1e3a5f; }

html, body, .stApp, .stApp * { font-family: 'Pretendard', -apple-system, sans-serif !important; }
code, pre, pre * { font-family: 'Pretendard', sans-serif !important; }
[data-testid="stIconMaterial"] { font-family: 'Material Symbols Rounded' !important; }

/* 기본 크롬 숨기기 */
header[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }
.block-container { max-width: 1120px; padding: 0 32px 48px; }

/* 상단바 */
.topbar { display: flex; justify-content: space-between; align-items: center; height: 64px;
          border-bottom: 1px solid var(--line); margin: 0 -32px 40px; padding: 0 32px; background: #fff; }
.logo { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 700; color: var(--ink); letter-spacing: .02em; }
.logo i { width: 16px; height: 16px; background: var(--accent); border-radius: 4px; display: inline-block; }
.status { font-size: 12px; color: var(--sub); display: flex; align-items: center; gap: 8px; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.ver { border: 1px solid var(--line); border-radius: 999px; padding: 2px 8px; color: var(--sub); }

/* 제목 */
.h1 { font-size: 24px; font-weight: 700; color: var(--ink); letter-spacing: -0.02em; margin-bottom: 8px; }
.desc { font-size: 14px; color: var(--sub); margin-bottom: 24px; }

/* 탭 */
.stTabs [data-baseweb="tab-list"] { gap: 24px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { padding: 8px 0 12px; }
.stTabs [data-baseweb="tab"] p { font-size: 14px; font-weight: 500; color: var(--sub); }
.stTabs [aria-selected="true"] p { color: var(--ink); font-weight: 600; }
.stTabs [data-baseweb="tab-highlight"] { background: var(--accent); height: 2px; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 24px; }

/* 패널 (원문 / 결과) */
[class*="st-key-pane"] { background: #fff; border: 1px solid var(--line); border-radius: 12px;
                         padding: 16px 16px 12px; min-height: 360px; gap: 8px; }
.pane-head { display: flex; justify-content: space-between; align-items: center; height: 24px; }
.pane-title { font-size: 12px; font-weight: 600; color: var(--sub); }
.pane-foot { font-size: 12px; color: var(--muted); text-align: right; }
.st-key-btn_example { display: flex; justify-content: flex-end; width: 100% !important; }
.st-key-btn_example .stButton { width: auto !important; margin-left: auto; }
.st-key-btn_example button { font-size: 12px !important; color: var(--accent) !important; padding: 0 !important; min-height: 0 !important; }

/* 입력칸: 패널 안에 녹아들게 테두리 없음 */
.stTextArea [data-baseweb="textarea"], .stTextInput [data-baseweb="input"] { border: none !important; background: transparent; }
.stTextArea [data-baseweb="base-input"], .stTextInput [data-baseweb="base-input"] { background: transparent !important; }
.stTextArea textarea { font-size: 16px; line-height: 1.75; color: var(--ink); padding: 8px 0; }
.stTextArea textarea::placeholder, .stTextInput input::placeholder { color: var(--muted); }
.st-key-rid [data-baseweb="input"] { border: 1px solid var(--line) !important; border-radius: 8px; background: #fff; }
.stTextInput input { font-size: 14px; padding: 12px; }
[data-testid="stFileUploaderDropzone"] { background: var(--bg); border: 1px dashed #d1d5db; border-radius: 8px; }

/* 결과 */
.out { font-size: 16px; line-height: 1.9; color: var(--ink); padding: 8px 0; white-space: normal; }
.empty { height: 260px; display: flex; align-items: center; justify-content: center;
         font-size: 14px; color: var(--muted); text-align: center; line-height: 1.7; }
.chip { padding: 2px 8px; border-radius: 6px; font-weight: 600; font-size: 14px; }
mark { color: var(--ink); padding: 1px 2px; border-radius: 3px 3px 0 0; }
.summary { font-size: 12px; color: var(--sub); margin: 8px 0; }
.summary b { color: var(--ink); font-weight: 600; }

/* 복사 버튼: st.code의 복사 기능을 '결과 복사하기' 버튼처럼 */
[class*="st-key-copybar"] [data-testid="stCode"] { position: relative; border: 1px solid var(--line); border-radius: 8px; height: 40px; overflow: hidden; }
[class*="st-key-copybar"] [data-testid="stCode"] pre { height: 40px; padding: 0 !important; margin: 0; background: transparent !important; }
[class*="st-key-copybar"] code { visibility: hidden; }
[class*="st-key-copybar"] [data-testid="stCode"]::before { content: "결과 복사하기"; position: absolute; left: 0; right: 0; top: 0; line-height: 38px;
    text-align: center; font-size: 14px; font-weight: 600; color: var(--accent); pointer-events: none; z-index: 1; }
[class*="st-key-copybar"] [data-testid="stCode"] > div { position: static !important; opacity: 1 !important; }
[class*="st-key-copybar"] [data-testid="stCodeCopyButton"] { position: absolute; top: 0; left: 0; min-width: 100% !important; min-height: 100% !important; display: flex !important; align-items: center; opacity: 1 !important; transform: none !important;
    visibility: visible !important; background: transparent !important; border: none; justify-content: flex-end; z-index: 2; padding-right: 14px; color: var(--accent); }
[class*="st-key-copybar"] [data-testid="stCodeCopyButton"]:hover { background: var(--bg) !important; }

/* 버튼 */
.stButton button { border-radius: 8px; font-size: 14px; font-weight: 600; }
.stButton button[kind="primary"] { background: var(--accent); border-color: var(--accent); min-height: 48px; }
.stButton button[kind="primary"]:hover { background: #162d4a; border-color: #162d4a; }
.stButton button[kind="primary"]:disabled { background: #e5e7eb; border-color: #e5e7eb; color: var(--muted); }

/* 접수번호 칸, 접이식 칸, 알림 */
[data-testid="stCode"] pre { background: var(--bg) !important; border-radius: 8px; font-size: 12px !important; color: var(--sub); }
[data-testid="stExpander"] details { border: 1px solid var(--line); border-radius: 12px; background: #fff; }
[data-testid="stExpander"] summary p { font-size: 14px; color: var(--sub); }
[data-testid="stAlert"] { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


def chip(label, color):
    bg, fg = color
    return f'<span class="chip" style="background:{bg};color:{fg}">{label}</span>'


def highlight(text, entities):
    out = []
    last = 0
    for e in sorted(entities, key=lambda e: e["start"]):
        s, end = e["start"], e["end"]
        out.append(html.escape(text[last:s]))
        bg, fg = COLORS.get(e["type"], ("#eeeeee", "#555555"))
        out.append(f'<mark style="background:{bg};box-shadow:inset 0 -2px 0 {fg}" title="{LABEL.get(e["type"], e["type"])}">'
                   + html.escape(text[s:end]) + "</mark>")
        last = end
    out.append(html.escape(text[last:]))
    return "".join(out).replace("\n", "<br>")


def masked_html(masked):
    # [전화번호] 같은 표시를 같은 색 칩으로 바꿔서 보여 줌
    def repl(m):
        return chip(m.group(0), COLOR_BY_LABEL[m.group(1)])
    pattern = r"\[(" + "|".join(COLOR_BY_LABEL) + r")\]"
    return re.sub(pattern, repl, html.escape(masked)).replace("\n", "<br>")


def html_block(inner):
    st.markdown(inner, unsafe_allow_html=True)


def summary_text(counts):
    if not counts:
        return "찾은 개인정보 없음"
    parts = " · ".join(f"{LABEL.get(t, t)} {n}" for t, n in counts.items())
    return f"<b>{sum(counts.values())}개</b> 찾음 · {parts}"


def call_api(path, method="post", **kwargs):
    """성공하면 (data, None), 실패하면 (None, 오류 문구)."""
    try:
        res = requests.request(method, f"{API_URL}{path}", timeout=10, **kwargs)
    except requests.exceptions.RequestException:
        return None, "API 서버에 연결할 수 없습니다. 서버가 켜져 있는지 확인하세요."
    try:
        data = res.json()
    except ValueError:
        return None, f"서버 응답을 읽을 수 없습니다. (HTTP {res.status_code})"
    if res.status_code != 200:
        err = data.get("error", {})
        return None, f"{err.get('message', '요청에 실패했습니다.')} ({err.get('code', res.status_code)})"
    return data, None


def result_pane(key, state):
    """오른쪽 결과 패널. state = None | {"error"} | {"text", "data"}"""
    with st.container(key=key):
        html_block('<div class="pane-head"><span class="pane-title">가린 결과</span></div>')
        if state is None:
            html_block('<div class="empty">왼쪽에 문장을 넣고 [가리기]를 누르면<br>개인정보를 가린 결과가 여기에 표시됩니다.</div>')
        elif "error" in state:
            st.error(state["error"])
        else:
            data = state["data"]
            html_block(f'<div class="out" translate="no">{masked_html(data["masked_text"])}</div>')
            html_block(f'<div class="summary">{summary_text(data.get("entity_counts"))}'
                       f' · {data.get("latency_ms", 0)}ms</div>')
            with st.container(key=f"copybar_{key}"):
                st.code(data["masked_text"], language=None)


def details(state):
    if state and "data" in state:
        data = state["data"]
        with st.expander("탐지 위치와 접수번호 보기"):
            html_block(f'<div class="out" translate="no">{highlight(state["text"], data["entities"])}</div>')
            st.caption(f"접수번호 (request_id) · 글자 수 {data.get('char_count', 0):,}자")
            st.code(data["request_id"], language=None)


# ---------- 상단바 ----------
try:
    h = requests.get(f"{API_URL}/health", timeout=2).json()
    color, word = ("#16a34a", "서버 연결됨") if h.get("model_loaded") else ("#d97706", "모델 준비 중")
    ver = f'<span class="ver">{html.escape(str(h.get("model_version")))}</span>'
except (requests.exceptions.RequestException, ValueError):
    color, word, ver = "#dc2626", "서버 연결 안 됨", ""
html_block(f'<div class="topbar"><div class="logo"><i></i>GARIM</div>'
           f'<div class="status"><span class="dot" style="background:{color}"></span>{word}{ver}</div></div>')

html_block('<div class="h1">개인정보 가리기</div>'
           '<div class="desc">LLM에 보내기 전에 문서 속 이름·주소·주민등록번호·전화번호·이메일·계좌번호를 찾아 가립니다.</div>')

tab_text, tab_file, tab_find = st.tabs(["텍스트", "파일 (.txt)", "기록 조회"])

with tab_text:
    left, right = st.columns(2, gap="medium")
    with left:
        with st.container(key="pane_in"):
            c1, c2 = st.columns([1, 1])
            c1.markdown('<div class="pane-title">원문</div>', unsafe_allow_html=True)
            with c2:
                if st.button("예시 문장 넣기", key="btn_example", type="tertiary"):
                    st.session_state["input_text"] = EXAMPLE
            text = st.text_area("원문", height=264, key="input_text", label_visibility="collapsed",
                                placeholder="개인정보가 들어 있는 문장을 붙여넣으세요.")
            html_block(f'<div class="pane-foot">{len(text):,} / 5,000자</div>')
        if st.button("가리기", key="btn_text", type="primary", use_container_width=True):
            data, err = call_api("/mask", json={"text": text})
            st.session_state["r_text"] = {"error": err} if err else {"text": text, "data": data}
    with right:
        result_pane("pane_out", st.session_state.get("r_text"))
    details(st.session_state.get("r_text"))

with tab_file:
    left, right = st.columns(2, gap="medium")
    with left:
        with st.container(key="pane_file"):
            html_block('<div class="pane-head"><span class="pane-title">파일</span></div>')
            up = st.file_uploader("파일", type=["txt"], label_visibility="collapsed")
            html_block('<div class="pane-foot">.txt · UTF-8 · 100KB 이하 · 5,000자 이하</div>')
        if st.button("가리기", key="btn_file", type="primary", disabled=up is None, use_container_width=True):
            raw = up.getvalue()
            data, err = call_api("/mask/file", files={"file": (up.name, raw, "text/plain")})
            st.session_state["r_file"] = ({"error": err} if err
                                          else {"text": raw.decode("utf-8-sig"), "data": data})
    with right:
        result_pane("pane_file_out", st.session_state.get("r_file"))
    details(st.session_state.get("r_file"))

with tab_find:
    html_block('<div class="desc" style="margin-bottom:8px">처리할 때 받은 접수번호(request_id)로 가린 결과를 다시 조회합니다. 원문은 저장하지 않습니다.</div>')
    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
    with c1:
        rid = st.text_input("접수번호", key="rid", label_visibility="collapsed",
                            placeholder="예) 6f1c2a8e-3b4d-4e5f-9a10-7b2c3d4e5f60").strip()
    with c2:
        clicked = st.button("조회", key="btn_find", type="primary", disabled=not rid, use_container_width=True)
    if clicked:
        data, err = call_api(f"/results/{quote(rid, safe='')}", method="get")
        if err:
            st.error(err)
        elif data.get("masked_text") is None:
            st.info("보관 기간(30일)이 지나 마스킹본이 삭제됐습니다.")
        else:
            with st.container(key="pane_find_out"):
                html_block('<div class="pane-head"><span class="pane-title">가린 결과</span></div>')
                html_block(f'<div class="out" translate="no">{masked_html(data["masked_text"])}</div>')
                html_block(f'<div class="summary">{summary_text(data.get("entity_counts"))}'
                           f' · 처리 시각 {html.escape(str(data.get("created_at")))}</div>')

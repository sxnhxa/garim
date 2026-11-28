# ui

Streamlit 화면 (담당: 윤경화). API 명세 v0.2의 `/mask`, `/mask/file`, `/results/{id}`, `/health`를 호출합니다.

## 실행

```bash
pip install -r ui/requirements.txt
cd ui && streamlit run app.py
```

- API 주소는 저장소 루트 `.env`의 `GARIM_API_URL` (없으면 `http://localhost:8000`)
- 테마(`ui/.streamlit/config.toml`)를 읽으려면 `ui` 폴더에서 실행
- 테스트는 가짜 개인정보로만

## 기능

- 텍스트 붙여넣기 / .txt 업로드 → [가리기] → 원문·가린 결과 비교, 결과 복사
- 탐지 위치 강조 (`entities` 위치, 코드포인트 기준)
- 접수번호(request_id) 표시와 재조회 (로컬 모드에서는 항상 "기록 없음")
- 422 등 오류 메시지 표시, 상단바에 `/health` 서버 상태

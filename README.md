# GARIM

LLM에 보내기 전에 개인정보를 가리는 마스킹 API입니다. 클라우드컴퓨팅 기말 팀 프로젝트(팀 에봉이)입니다.

- 번호류(주민등록번호·전화번호·이메일·계좌번호)는 **정규식**으로 찾습니다.
- 이름·주소는 직접 파인튜닝한 **한국어 NER 모델**(klue/roberta-small, NAME·ADDRESS 태그)로 찾습니다.
- FastAPI + Docker → Amazon ECR → **ECS/Fargate**(ap-northeast-2)에 배포합니다.
- **원본 텍스트는 어디에도 저장하지 않습니다.** 마스킹본은 S3, 처리 기록은 DynamoDB에 남깁니다.

```
계약자 김민수(010-1234-5678)는 서울특별시 성북구 …
→ 계약자 [이름]([전화번호])는 [주소] …
```

## 구조

| 경로 | 내용 | 담당 |
| --- | --- | --- |
| [api/](api/) | FastAPI, 정규식, NER 추론, Dockerfile | 강선우 |
| [ui/](ui/) | Streamlit 화면 | 윤경화 |
| [eval/](eval/) | 평가셋 채점 스크립트 (데이터는 S3) | 윤경화 |
| [infra/](infra/) | ECS Task Definition, IAM 정책, 배포·정리 스크립트 | 김승하 |
| [scripts/](scripts/) | release manifest, 배포 전 검증 스크립트 | 김승하 |
| [docs/](docs/) | API 명세, 할당량·배포 증빙 | 전원 |

학습 템플릿·노트북은 평가셋 작성자와 분리하기 위해 별도 레포(`garim-train`)에서 관리합니다.

## 엔드포인트

| 메서드 | 경로 | 역할 |
| --- | --- | --- |
| POST | `/mask`, `/mask/file` | 텍스트 또는 .txt 파일 마스킹 |
| GET | `/results/{request_id}` | 처리 기록과 마스킹본 재조회 |
| GET | `/health` | 서버 상태, 모델 적재 여부, model_version |

## 시작하기

```bash
git clone https://github.com/sxnhxa/garim.git && cd garim
cp .env.example .env            # 값 채우기 (커밋 금지)
pip install pre-commit && pre-commit install
```

협업 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md)를 보세요. **main에 직접 push할 수 없고, PR + 팀원 1명 Approve 후 merge합니다.**

## 라이선스 / 데이터 고지

- 비상업 수업 목적 프로젝트입니다.
- 학습 데이터에 KLUE NER(CC BY-SA 4.0)을 사용합니다.
- 베이스 모델 klue/roberta-small은 모델 카드에 라이선스가 명시되어 있지 않아, 사용 범위를 비상업 수업으로 한정합니다.
- 학습·평가·테스트에 실제 개인정보는 사용하지 않습니다 (Faker ko_KR 가짜 데이터).

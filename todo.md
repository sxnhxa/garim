# GARIM TODO

> 발표 **12/14 (일)**, 5분 시연(정상 1건 + 오류 1건).
> 13주차(11/23~): 모델 v1 학습 + 평가 / 14주차(11/30~): 클라우드 배포 / 15주차(12/7~): 데모 리허설

## 0. 레포가 두 개인 이유

| 레포 | 공개 | 누가 | 내용 |
| --- | --- | --- | --- |
| [sxnhxa/garim](https://github.com/sxnhxa/garim) | public | 전원 | API, UI, 채점 스크립트, 배포 설정, 문서 |
| sxnhxa/garim-train | **private** | 강선우, 김승하 | 학습 문장 템플릿, 학습셋 생성 코드, Colab 노트북 |

평가셋을 만드는 사람(윤경화)이 학습 문장을 보면, 비슷한 문장으로 평가셋을 만들게 되기 쉽습니다. 그러면 모델이 학습 문장을 외웠을 뿐인데 점수가 높게 나옵니다. 그래서 **학습 쪽은 별도 private 레포로 분리**하고, 윤경화는 처음부터 접근 권한을 받지 않습니다.

반대 방향도 지킵니다. 평가셋 문장은 S3 `eval/`에만 두고 git, 카톡, PR에 올리지 않습니다. 강선우에게는 점수만 공유합니다.

---

## 1. 공통: 초대 수락 후 처음 한 번

- [ ] GitHub 초대 메일 수락 (`garim`: 전원 / `garim-train`: 강선우)
- [ ] clone 후 pre-commit 설치. 커밋할 때 키 유출 검사와 노트북 출력 셀 삭제가 자동으로 실행됩니다.
  ```bash
  git clone https://github.com/sxnhxa/garim.git && cd garim
  pip install pre-commit && pre-commit install
  cp .env.example .env
  ```
- [ ] [CONTRIBUTING.md](CONTRIBUTING.md) 읽기. **main에 직접 push 금지**, 브랜치 → PR → 다른 팀원 1명 Approve → Squash merge
- [ ] 첫 작업은 브랜치 → PR → 리뷰 흐름으로 올려 보기 (PR 흐름 연습)

## 2. 가장 먼저 할 일: API 계약 확정 (11/24까지, 전원)

UI(윤경화)와 채점(윤경화)이 API 응답 형식에 의존하므로 **이것부터 확정해야 다른 작업이 막히지 않습니다.**

- [ ] `docs/api-spec.md` 초안 작성 (**김승하**), 리뷰 (**강선우, 윤경화**)
  - `POST /mask`, `POST /mask/file`, `GET /results/{request_id}`, `GET /health`
  - 요청·응답 JSON 필드: `request_id`, `masked_text`, `model_version`, `latency_ms`, 탐지 개수
  - 채점용 탐지 위치: `entities: [{type, start, end}]` (원문 글자 없이 위치만)
  - 오류 응답 형식 (422 / 409 / 503 / 500). **원문을 돌려주지 않음**
- [ ] 정답 위치 JSON 형식 합의: 평가셋 정답과 API `entities`를 같은 형식으로 (글자 오프셋 `start`·`end`, 라벨 `NAME`·`ADDRESS`·`RRN`·`PHONE`·`EMAIL`·`ACCOUNT`)

---

## 3. 강선우: AI·API

**보는 곳**: `garim/api/`, `garim-train/` 전체

### garim: API (`api/`)
- [ ] FastAPI 뼈대: `/health`, `/mask`, `/mask/file`, `/results/{request_id}`
- [ ] 입력 검증: 빈 값, 5,000자 초과, .txt·UTF-8이 아닌 파일, 100KB 초과 → 422
- [ ] **422 핸들러 교체**: FastAPI 기본 422는 받은 값을 그대로 돌려주므로, 오류 유형만 반환하도록 변경
- [ ] 정규식: 주민등록번호, 전화번호, 이메일 (하이픈·공백 없는 형태 포함), 계좌번호 ("계좌", "입금" 같은 주변 단어가 있을 때만)
- [ ] **v0** = 정규식 + 도로명 주소 정규식 (이름 탐지 없음). 12주차 산출물이니 최우선
- [ ] **기준선** = 공개 한국어 NER의 인물(PS) 태그 + 도로명 정규식
- [ ] 테스트: Faker 가짜 데이터로만 (`api/tests/`)
- [ ] `Dockerfile`: CPU 전용 PyTorch, 모델은 build 때 S3에서 받아 포함

### garim-train: 학습
- [ ] KLUE NER 변환: PS → NAME, 나머지 태그 → O
- [ ] Faker(ko_KR) 이름·주소 템플릿 문장 생성 → 학습셋 **train-v1**을 S3 `train/v1/`에 업로드
- [ ] Colab 노트북: klue/roberta-small 토큰 분류 파인튜닝 (B/I-NAME, B/I-ADDRESS, O)
- [ ] 에폭별 손실·검증 F1, 하이퍼파라미터 기록
- [ ] 결과 가중치·토크나이저 + sha256 → S3 `models/pii-ner/v1/`
- [ ] **AWS 키는 Colab Secrets에만**. 키는 김승하에게 따로 받음. 노트북 코드, 출력 셀, 카톡에 남기지 않기
- 학습 마감: **13주차 안**. 늦어지면 기준선으로 먼저 배포합니다 (API 계약은 같고 `model_version`만 바뀜)

**하지 말 것**: 평가셋 문장을 보거나 요청하지 않기. 점수는 윤경화에게 받습니다.

---

## 4. 윤경화: 데이터·UI

**보는 곳**: `garim/eval/`, `garim/ui/`, `docs/api-spec.md`

### 평가셋 (13주차)
- [ ] **평가셋 A**: 가짜 계약서·상담 기록 100건 + 정답 위치 JSON → S3 `eval/v1/`
- [ ] **평가셋 B**: 실제 말투로 손으로 쓴 상담 문장 30건 (오타·띄어쓰기 변형 포함) → S3 `eval-hand/v1/`
- [ ] 이름·주소는 Faker나 직접 지어낸 가짜만 사용. 실제 개인정보는 0건
- [ ] 평가셋 문장은 **git에 올리지 않음** (S3에만). 강선우와 문장을 공유하지 않기

### 채점 (`eval/`)
- [ ] 채점 스크립트: API `/mask` 응답의 `entities`와 정답 JSON 비교
- [ ] 항목별 **재현율(1순위)**·정밀도 계산
- [ ] v0 / 기준선 / v1을 평가셋 A·B 각각 비교한 표 (목표: 정규식 항목 ≥ 0.98, 이름·주소 ≥ 0.85)
- [ ] A·B 점수 차이가 크면 강선우에게 **점수와 틀린 유형만** 전달 (문장 원문 X)

### 저장소 설계 (13주차)
- [ ] DynamoDB `garim-requests` 스키마: PK `request_id`, 상태, 글자 수, 탐지 개수, model_version, latency_ms. **원문 필드 없음**
- [ ] S3 경로: `masked/{날짜}/{request_id}.txt`
- [ ] 설계가 끝나면 김승하에게 전달 (생성과 IAM은 김승하가 담당)

### UI (`ui/`, 14주차)
- [ ] Streamlit: 텍스트 붙여넣기 / .txt 업로드 → [가리기] → 마스킹 전후 비교
- [ ] request_id 표시, request_id로 재조회, 422 오류 메시지 표시
- [ ] API 주소는 `.env`의 `GARIM_API_URL`

**하지 말 것**: `garim-train` 레포를 보거나 강선우에게 학습 템플릿을 묻지 않기.

---

## 5. 김승하: 클라우드·운영

**보는 곳**: `garim/infra/`, `garim/scripts/`, `docs/evidence/`, 두 레포 PR 리뷰

### 바로 (12주차 마무리)
- [ ] **API 명세 `docs/api-spec.md` 초안 작성 → PR로 강선우·윤경화 리뷰** (2번 항목, 11/24까지)
- [ ] SageMaker Endpoint 할당량 조회 → 캡처를 `docs/evidence/`에
- [ ] 교수님께 대체 경로(Colab 학습 + ECS/Fargate 배포) 확인
- [ ] 팀원 초대, 12~16주차 milestone과 이슈 등록

### AWS 기본 자원 (13주차 초, 서울 리전)
- [x] S3 버킷: 퍼블릭 액세스 차단, SSE-S3, `masked/` 30일 수명 주기
- [ ] **학습 전용 IAM 사용자** `garim-train-uploader`: `train/*`, `models/*`에 `s3:PutObject`만 허용 (생성 완료). **키를 강선우에게 안전하게 전달** (git, 카톡 X)
- [ ] 평가셋(`eval/*`, `eval-hand/*`)은 윤경화만: `garim-eval-uploader` 생성 완료. **키를 윤경화에게 전달**
- [x] DynamoDB `garim-requests` 생성 (윤경화 설계 기준, 조건부 쓰기로 같은 request_id 재기록 방지)
- [x] ECR `garim` 리포지토리, CloudWatch 로그 그룹 `/ecs/garim`

### 배포 (14주차)
- [ ] Task Execution Role (이미지 pull, 로그 쓰기) / Task Role (`masked/*` Put·Get, 테이블 Put·Get) 분리 → `infra/`에 정책 JSON
- [ ] ECS 클러스터, Task Definition (1 vCPU·2GB), Service, 보안 그룹 TCP 8000 /32
- [ ] 로그 지표 필터: success_count, error_count, latency_ms
- [ ] 서울 리전 Fargate 단가 확인 → 비용표
- [ ] `scripts/`: release manifest 생성 (train 버전, 모델 sha256, model_version, ECR 태그·digest, Task Definition revision, Git commit) + 검증 스크립트 (PASS인 버전만 배포)

### 발표 후 (12/14)
- [ ] 자원 정리: Service 작업 수 0 → Service 삭제 → Task STOPPED → Task Definition 해제 → ECR 이미지 → S3·DynamoDB·로그 그룹·IAM → 비용 화면 캡처

---

## 6. 의존 관계

```
API 명세 확정 ──┬──► 윤경화: 채점 스크립트, UI
                └──► 강선우: v0 구현
김승하: S3 + 학습용 IAM 키 ──► 강선우: 학습셋·모델 S3 업로드
윤경화: DynamoDB·S3 설계 ──► 김승하: 자원 생성, Task Role
강선우: v1 모델 + Dockerfile ──► 김승하: ECR → Fargate 배포
윤경화: 3버전 점수 ──► v1 배포 여부 결정 (미달 시 기준선 배포)
```

## 7. 매주 같이 하는 것

- [ ] 주 1회 전체 요청 흐름을 함께 실행하고 기록 남기기 (세 명 모두 전체 흐름을 설명할 수 있게)

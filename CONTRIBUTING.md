# 협업 규칙

## 1. main에 직접 push 금지

`main`은 보호 브랜치입니다. 팀원은 **직접 push할 수 없고**, PR merge로만 바꿀 수 있습니다.

레포 관리자(김승하)는 문서 수정 같은 간단한 변경을 직접 올릴 수 있습니다. 코드 변경은 관리자도 똑같이 PR로 올리고 리뷰를 받습니다.

## 2. 작업 흐름

```bash
git switch main && git pull                 # 최신 main 받기
git switch -c feat/api-mask-v0              # 작업 브랜치 생성
# ... 작업 & 커밋 ...
git push -u origin feat/api-mask-v0         # 브랜치 push
gh pr create --fill                         # PR 생성 (또는 GitHub 웹에서)
```

1. 브랜치에서 작업 → PR 올리기
2. **본인이 아닌 팀원 1명 이상이 Approve**
3. Approve 받은 뒤 PR 작성자가 **Squash and merge**
4. merge 후 브랜치는 자동 삭제됨

## 3. 브랜치 이름

| 접두사 | 용도 | 예시 |
| --- | --- | --- |
| `feat/` | 새 기능 | `feat/ner-inference` |
| `fix/` | 버그 수정 | `fix/422-raw-input-leak` |
| `docs/` | 문서 | `docs/api-spec` |
| `infra/` | 배포·IAM·AWS | `infra/ecs-task-def` |
| `chore/` | 설정·잡일 | `chore/pre-commit` |

## 4. 커밋 메시지

`<type>: <요약>` 형식. type은 `feat`, `fix`, `docs`, `infra`, `chore`, `test`, `refactor`.

```
feat: 주민등록번호·전화번호 정규식 추가
fix: 422 응답에서 입력 원문 제거
```

## 5. 리뷰 담당 (CODEOWNERS 자동 지정)

| 경로 | 담당 |
| --- | --- |
| `api/` | 강선우 |
| `ui/`, `eval/` | 윤경화 |
| `infra/`, `scripts/` | 김승하 |

담당자에게 리뷰가 자동 요청되지만, 담당자가 아니어도 **팀원 누구든 Approve하면 merge 가능**합니다.

## 6. 절대 커밋하면 안 되는 것

- AWS 키, `.env`, 자격 증명 파일
- 실제 개인정보가 들어간 텍스트 (테스트도 전부 가짜 데이터)
- 모델 가중치, 학습·평가 데이터 (S3에서 관리)
- 출력 셀이 남은 노트북

처음 clone한 뒤 한 번 실행해 두세요:

```bash
pip install pre-commit && pre-commit install
```

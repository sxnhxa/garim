# infra

AWS 배포 설정 (담당: 김승하)

- ECS Task Definition, IAM 정책(Task Role / Task Execution Role / 학습 전용 사용자)
- 배포 스크립트(ECR push → Fargate Service 업데이트), 자원 정리 스크립트
- 계정 ID·키 같은 값은 적지 않고 환경변수로 받음

## 기본 자원 (13주차)

`scripts/aws-setup.sh`로 만듭니다. 버킷 이름은 `.env`의 `S3_BUCKET`에서 읽고, 이미 있는 자원은 건너뛰므로 여러 번 실행해도 됩니다. 모든 자원에 `Project=garim` 태그가 붙습니다.

| 자원 | 이름 | 설정 |
| --- | --- | --- |
| S3 버킷 | `$S3_BUCKET` | 퍼블릭 액세스 차단, SSE-S3, `masked/` 30일 후 삭제, 중단된 멀티파트 업로드 7일 후 정리 ([s3-lifecycle.json](s3-lifecycle.json)) |
| DynamoDB | `garim-requests` | PK `request_id`(S), 온디맨드. 항목은 [API 명세 3절](../docs/api-spec.md) |
| ECR | `garim` | push 시 취약점 스캔 |
| CloudWatch 로그 그룹 | `/ecs/garim` | 30일 보존 |
| IAM 사용자 | `garim-train-uploader` (강선우) | `train/*`, `models/*`에 `s3:PutObject`만 ([policies/train-uploader.json](policies/train-uploader.json)) |
| IAM 사용자 | `garim-eval-uploader` (윤경화) | `eval/*`, `eval-hand/*` Put·Get·List만 ([policies/eval-uploader.json](policies/eval-uploader.json)) |

- 정책 JSON의 `${S3_BUCKET}`은 스크립트가 실행할 때 채웁니다.
- 액세스 키는 스크립트가 만들지 않습니다. 콘솔에서 직접 발급해 당사자에게 전달합니다 (git, 카톡 X).
- 학습 사용자는 `eval/*`에 접근할 수 없고, 평가 사용자는 `train/*`, `models/*`에 접근할 수 없습니다 (평가셋·학습셋 분리).

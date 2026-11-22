# infra

AWS 배포 설정 (담당: 김승하)

- ECS Task Definition, IAM 정책(Task Role / Task Execution Role / 학습 전용 사용자)
- 배포 스크립트(ECR push → Fargate Service 업데이트), 자원 정리 스크립트
- 계정 ID·키 같은 값은 적지 않고 환경변수로 받음

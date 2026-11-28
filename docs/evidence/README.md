# evidence

SageMaker 학습·Endpoint 할당량 캡처, 배포·로그·비용 증빙 캡처를 보관합니다.

## SageMaker 할당량 (2026-11-24, 서울 리전)

| 파일 | 내용 | 결과 |
| --- | --- | --- |
| [sagemaker-quota-training-2026-11-24.png](sagemaker-quota-training-2026-11-24.png) | Service Quotas `training job usage` | CPU 학습 인스턴스(ml.c·ml.m·ml.t) 적용값 **0** → SageMaker 학습 불가, Colab GPU로 학습 |
| [sagemaker-quota-endpoint-2026-11-24.png](sagemaker-quota-endpoint-2026-11-24.png) | Service Quotas `endpoint usage` | CPU 인스턴스 적용값 **16** → Endpoint 배포는 가능하지만 ECS/Fargate 선택 |

- GPU 학습 인스턴스(ml.g5·g6 등)는 1대씩 할당돼 있으나 시간당 과금이라 무료 Colab GPU를 씁니다.
- ECS/Fargate를 고른 이유: 추론뿐 아니라 입력 검증·마스킹·S3·DynamoDB 저장·로그까지 한 API로 처리하고, 4주차 Docker → ECR → ECS 실습 절차를 그대로 이어 씁니다.

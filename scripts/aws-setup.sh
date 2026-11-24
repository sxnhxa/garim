#!/usr/bin/env bash
# GARIM AWS 기본 자원 생성 (13주차, todo.md 5절 "AWS 기본 자원")
#
#   S3 버킷 / DynamoDB 테이블 / ECR 리포지토리 / CloudWatch 로그 그룹 /
#   학습용·평가셋용 IAM 사용자(인라인 정책) /
#   ECS Task Execution Role·Task Role (14주차 #15, 인라인 정책)
#
# 사용: scripts/aws-setup.sh
#   - .env의 S3_BUCKET, DDB_TABLE, AWS_REGION을 읽습니다 (버킷 이름은 레포에 적지 않음).
#   - 이미 있는 자원은 건너뛰고 설정만 다시 맞추므로 여러 번 실행해도 됩니다.
#   - 액세스 키는 만들지 않습니다. 콘솔에서 직접 발급해 당사자에게 전달합니다.
#   - 모든 자원에 Project=garim 태그를 붙입니다 (발표 후 정리용).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then set -a; . ./.env; set +a; fi
: "${S3_BUCKET:?.env에 S3_BUCKET을 넣으세요}"
REGION="${AWS_REGION:-ap-northeast-2}"
TABLE="${DDB_TABLE:-garim-requests}"
ECR_REPO="${ECR_REPO:-garim}"
LOG_GROUP="${LOG_GROUP:-/ecs/garim}"
LOG_RETENTION_DAYS=30
TRAIN_USER=garim-train-uploader
EVAL_USER=garim-eval-uploader
API_DEV_USER=garim-api-dev
EXEC_ROLE=garim-task-execution-role
TASK_ROLE=garim-task-role
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION" AWS_PAGER=""

say() { printf '\n== %s\n' "$*"; }

say "계정 확인"
aws sts get-caller-identity --query Arn --output text
# 계정 ID는 레포에 적지 않고 실행할 때 조회해 정책에 채웁니다.
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
render() {
  sed -e "s|\${S3_BUCKET}|${S3_BUCKET}|g" \
      -e "s|\${AWS_ACCOUNT_ID}|${AWS_ACCOUNT_ID}|g" \
      -e "s|\${AWS_REGION}|${REGION}|g" "$1"
}

say "S3 버킷: ${S3_BUCKET}"
if aws s3api head-bucket --bucket "$S3_BUCKET" >/dev/null 2>&1; then
  echo "이미 있음"
else
  aws s3api create-bucket --bucket "$S3_BUCKET" \
    --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
  echo "생성"
fi
aws s3api put-public-access-block --bucket "$S3_BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket "$S3_BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-bucket-lifecycle-configuration --bucket "$S3_BUCKET" \
  --lifecycle-configuration file://infra/s3-lifecycle.json
aws s3api put-bucket-tagging --bucket "$S3_BUCKET" \
  --tagging 'TagSet=[{Key=Project,Value=garim}]'
echo "퍼블릭 차단, SSE-S3, masked/ 30일 수명 주기 적용"

say "DynamoDB 테이블: ${TABLE}"
if aws dynamodb describe-table --table-name "$TABLE" >/dev/null 2>&1; then
  echo "이미 있음"
else
  aws dynamodb create-table --table-name "$TABLE" \
    --attribute-definitions AttributeName=request_id,AttributeType=S \
    --key-schema AttributeName=request_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --tags Key=Project,Value=garim >/dev/null
  aws dynamodb wait table-exists --table-name "$TABLE"
  echo "생성 (PK request_id, 온디맨드)"
fi

say "ECR 리포지토리: ${ECR_REPO}"
if aws ecr describe-repositories --repository-names "$ECR_REPO" >/dev/null 2>&1; then
  echo "이미 있음"
else
  aws ecr create-repository --repository-name "$ECR_REPO" \
    --image-scanning-configuration scanOnPush=true \
    --tags Key=Project,Value=garim >/dev/null
  echo "생성 (push 시 취약점 스캔)"
fi

say "CloudWatch 로그 그룹: ${LOG_GROUP}"
existing=$(aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" \
  --query "logGroups[?logGroupName=='${LOG_GROUP}'].logGroupName" --output text)
if [ -n "$existing" ]; then
  echo "이미 있음"
else
  aws logs create-log-group --log-group-name "$LOG_GROUP" --tags Project=garim
  echo "생성"
fi
aws logs put-retention-policy --log-group-name "$LOG_GROUP" \
  --retention-in-days "$LOG_RETENTION_DAYS"
echo "보존 ${LOG_RETENTION_DAYS}일"

ensure_user() {
  local name=$1 policy_file=$2
  say "IAM 사용자: ${name}"
  if aws iam get-user --user-name "$name" >/dev/null 2>&1; then
    echo "이미 있음"
  else
    aws iam create-user --user-name "$name" --tags Key=Project,Value=garim >/dev/null
    echo "생성"
  fi
  aws iam put-user-policy --user-name "$name" --policy-name "${name}-s3" \
    --policy-document "$(render "$policy_file")"
  echo "정책 적용: ${policy_file}"
}
ensure_user "$TRAIN_USER" infra/policies/train-uploader.json
ensure_user "$EVAL_USER" infra/policies/eval-uploader.json
# 로컬에서 API의 S3·DynamoDB 저장을 테스트하는 개발용 사용자. Task Role과 같은 정책을 씁니다.
ensure_user "$API_DEV_USER" infra/policies/task-role.json

ensure_role() {
  local name=$1 policy_file=$2 desc=$3
  say "IAM 역할: ${name}"
  if aws iam get-role --role-name "$name" >/dev/null 2>&1; then
    aws iam update-assume-role-policy --role-name "$name" \
      --policy-document "$(render infra/policies/ecs-tasks-trust.json)"
    echo "이미 있음 (신뢰 정책 갱신)"
  else
    aws iam create-role --role-name "$name" --description "$desc" \
      --assume-role-policy-document "$(render infra/policies/ecs-tasks-trust.json)" \
      --tags Key=Project,Value=garim >/dev/null
    echo "생성"
  fi
  aws iam put-role-policy --role-name "$name" --policy-name "${name}-policy" \
    --policy-document "$(render "$policy_file")"
  echo "정책 적용: ${policy_file}"
}
ensure_role "$EXEC_ROLE" infra/policies/task-execution-role.json \
  "GARIM ECS: pull garim image, write /ecs/garim logs"
ensure_role "$TASK_ROLE" infra/policies/task-role.json \
  "GARIM API: S3 masked/ and DynamoDB garim-requests only"

say "완료"
echo "액세스 키는 콘솔 IAM > 사용자 > 보안 자격 증명에서 직접 발급하세요."
echo "  ${TRAIN_USER} → 강선우 (Colab Secrets에만 저장)"
echo "  ${EVAL_USER} → 윤경화"
echo "  ${API_DEV_USER} → 강선우 (로컬 .env/프로필에만 저장)"

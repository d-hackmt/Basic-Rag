# CI/CD — Full Command Flow (one-time AWS setup)

Run these top to bottom **once**, from a machine with the AWS CLI configured
(`aws configure` / `aws sso login`) as an admin-ish user. After this, deploying
is just `git push`. Concepts and troubleshooting are in
[09_cicd_aws_ecr_ec2.md](09_cicd_aws_ecr_ec2.md) — this file is just the flow.

```bash
# ============================================================
# STEP 0 - Variables (edit GH_REPO to your repo)
# ============================================================
export AWS_REGION=eu-west-2
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export GH_REPO="d-hackmt/hr-rag-deployment"
export ECR_REPO=hr-assistant
export SSM_ENV_PARAM=/hr-assistant/env
echo "Account $AWS_ACCOUNT_ID / region $AWS_REGION / repo $GH_REPO"


# ============================================================
# STEP 1 - ECR repository (where images are pushed)
# ============================================================
aws ecr create-repository --repository-name "$ECR_REPO" --region "$AWS_REGION" \
  --image-scanning-configuration scanOnPush=true


# ============================================================
# STEP 2 - GitHub OIDC provider (once per AWS account)
# "already exists" error here is fine - skip it.
# ============================================================
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" || true


# ============================================================
# STEP 3 - IAM role that GitHub Actions assumes (no stored keys)
# ============================================================
cat > trust.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
      "StringLike":   { "token.actions.githubusercontent.com:sub": "repo:${GH_REPO}:ref:refs/heads/main" }
    }
  }]
}
EOF

aws iam create-role --role-name github-actions-hr-assistant \
  --assume-role-policy-document file://trust.json

cat > perms.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "EcrAuth", "Effect": "Allow", "Action": "ecr:GetAuthorizationToken", "Resource": "*" },
    { "Sid": "EcrPush", "Effect": "Allow",
      "Action": ["ecr:BatchCheckLayerAvailability","ecr:GetDownloadUrlForLayer","ecr:BatchGetImage",
                 "ecr:PutImage","ecr:InitiateLayerUpload","ecr:UploadLayerPart","ecr:CompleteLayerUpload"],
      "Resource": "arn:aws:ecr:${AWS_REGION}:${AWS_ACCOUNT_ID}:repository/${ECR_REPO}" },
    { "Sid": "SsmPutEnv", "Effect": "Allow", "Action": "ssm:PutParameter",
      "Resource": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter${SSM_ENV_PARAM}" },
    { "Sid": "SsmSend", "Effect": "Allow", "Action": "ssm:SendCommand",
      "Resource": ["arn:aws:ssm:${AWS_REGION}::document/AWS-RunShellScript",
                   "arn:aws:ec2:${AWS_REGION}:${AWS_ACCOUNT_ID}:instance/*"] },
    { "Sid": "SsmRead", "Effect": "Allow",
      "Action": ["ssm:GetCommandInvocation","ssm:ListCommands"], "Resource": "*" }
  ]
}
EOF

aws iam put-role-policy --role-name github-actions-hr-assistant \
  --policy-name deploy --policy-document file://perms.json

# >>> copy this ARN into GitHub secret AWS_ROLE_ARN
echo "arn:aws:iam::${AWS_ACCOUNT_ID}:role/github-actions-hr-assistant"


# ============================================================
# STEP 4 - Instance profile (permissions the server has)
# ============================================================
cat > ec2-trust.json <<'EOF'
{ "Version": "2012-10-17",
  "Statement": [{ "Effect": "Allow",
    "Principal": { "Service": "ec2.amazonaws.com" }, "Action": "sts:AssumeRole" }] }
EOF

aws iam create-role --role-name hr-assistant-ec2 \
  --assume-role-policy-document file://ec2-trust.json

aws iam attach-role-policy --role-name hr-assistant-ec2 \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam attach-role-policy --role-name hr-assistant-ec2 \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly

cat > ec2-ssm-read.json <<EOF
{ "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": "ssm:GetParameter",
      "Resource": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter${SSM_ENV_PARAM}" },
    { "Effect": "Allow", "Action": "kms:Decrypt",
      "Resource": "arn:aws:kms:${AWS_REGION}:${AWS_ACCOUNT_ID}:alias/aws/ssm" }
  ] }
EOF
aws iam put-role-policy --role-name hr-assistant-ec2 \
  --policy-name read-env --policy-document file://ec2-ssm-read.json

aws iam create-instance-profile --instance-profile-name hr-assistant-ec2
aws iam add-role-to-instance-profile \
  --instance-profile-name hr-assistant-ec2 --role-name hr-assistant-ec2

sleep 10   # let the instance profile propagate


# ============================================================
# STEP 5 - Security group (firewall: only 8501 in)
# ============================================================
export VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' --output text)

export SG_ID=$(aws ec2 create-security-group \
  --group-name hr-assistant-sg \
  --description "HR assistant - Streamlit 8501" \
  --vpc-id "$VPC_ID" --query GroupId --output text)

aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" --protocol tcp --port 8501 --cidr 0.0.0.0/0
echo "SG: $SG_ID"


# ============================================================
# STEP 6 - Launch the EC2 instance (installs Docker on boot)
# ============================================================
cat > user-data.sh <<'EOF'
#!/bin/bash
set -eux
dnf install -y docker
systemctl enable --now docker
mkdir -p /opt/hr-assistant
EOF

export AMI_ID=$(aws ssm get-parameter \
  --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query 'Parameter.Value' --output text)

export INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t3.micro \
  --iam-instance-profile Name=hr-assistant-ec2 \
  --security-group-ids "$SG_ID" \
  --user-data file://user-data.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=hr-assistant-prod}]' \
  --query 'Instances[0].InstanceId' --output text)

# >>> copy this into GitHub variable EC2_INSTANCE_ID
echo "INSTANCE_ID=$INSTANCE_ID"

echo "waiting for the instance to register with SSM (~2 min)..."
until aws ssm describe-instance-information \
  --query "InstanceInformationList[?InstanceId=='$INSTANCE_ID'].InstanceId" \
  --output text | grep -q "$INSTANCE_ID"; do sleep 10; echo -n .; done
echo " registered."


# ============================================================
# STEP 7 - Seed the runtime .env into Parameter Store (first time)
# The pipeline re-syncs this every run from the APP_ENV_FILE secret.
# .env.docker = strict format (KEY=value, no spaces/quotes).
# ============================================================
aws ssm put-parameter --name "$SSM_ENV_PARAM" --type SecureString \
  --value "$(cat .env.docker)" --overwrite


# ============================================================
# STEP 8 - Put the 3 values into GitHub
#   Settings > Secrets and variables > Actions
#     Secret   AWS_ROLE_ARN     = arn:aws:iam::<acct>:role/github-actions-hr-assistant
#     Secret   APP_ENV_FILE     = <entire contents of .env.docker>
#     Variable EC2_INSTANCE_ID  = <INSTANCE_ID from step 6>
# ============================================================


# ============================================================
# STEP 9 - Deploy
# ============================================================
git add .github/ deploy/ docs/09_cicd_aws_ecr_ec2.md docs/cicd_commands.md
git commit -m "Add CI/CD: GitHub Actions -> ECR -> EC2"
git push origin main
# watch: GitHub repo > Actions tab > "deploy"


# ============================================================
# STEP 10 - Verify
# ============================================================
export PUBLIC_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "App:  http://$PUBLIC_IP:8501"
curl -s -o /dev/null -w "health: %{http_code}\n" "http://$PUBLIC_IP:8501/_stcore/health"


# ============================================================
# Housekeeping
# ============================================================
# shell on the box (no SSH key):   aws ssm start-session --target "$INSTANCE_ID"
# app logs:                        (in that session) docker logs -f hr-assistant
# stop paying (keep instance):     aws ec2 stop-instances  --instance-ids "$INSTANCE_ID"
# delete instance:                 aws ec2 terminate-instances --instance-ids "$INSTANCE_ID"

# clean up local json files from this run
rm -f trust.json perms.json ec2-trust.json ec2-ssm-read.json user-data.sh
```

## Teardown (remove everything this created)

```bash
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"
aws ec2 delete-security-group --group-id "$SG_ID"

aws iam remove-role-from-instance-profile --instance-profile-name hr-assistant-ec2 --role-name hr-assistant-ec2
aws iam delete-instance-profile --instance-profile-name hr-assistant-ec2
aws iam delete-role-policy --role-name hr-assistant-ec2 --policy-name read-env
aws iam detach-role-policy --role-name hr-assistant-ec2 --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam detach-role-policy --role-name hr-assistant-ec2 --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
aws iam delete-role --role-name hr-assistant-ec2

aws iam delete-role-policy --role-name github-actions-hr-assistant --policy-name deploy
aws iam delete-role --role-name github-actions-hr-assistant

aws ssm delete-parameter --name "$SSM_ENV_PARAM"
aws ecr delete-repository --repository-name "$ECR_REPO" --force
# (leave the OIDC provider - other repos may use it)
```

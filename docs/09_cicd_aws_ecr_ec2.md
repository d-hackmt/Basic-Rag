# 09. CI/CD — GitHub Actions → Amazon ECR → EC2

**Branch:** `cicd` (built on top of `docker-compose`)

Goal: every time you `git push` to `main`, GitHub automatically builds the
Docker image, uploads it to AWS, and restarts the app on a server — with no
manual steps and no secrets stored in GitHub.

---

## 1. What is CI/CD, in plain words

- **CI — Continuous Integration:** every push is automatically built and
  checked, so you find out immediately if something is broken, instead of
  weeks later.
- **CD — Continuous Delivery/Deployment:** once the build passes, it's
  automatically shipped to a running server, so "it works on my machine" and
  "it's live" are the same thing.

We already have the *build* recipe (`Dockerfile`) and *run* recipe
(`docker-compose.yml`) from the last two branches. This branch adds the
**automation** that ties them to `git push` and to a real cloud server.

---

## 2. The big picture

```
you: git push origin main
        │
        ▼
┌─────────────────────────── GitHub Actions (ubuntu runner) ───────────────────────────┐
│ 1. checkout code                                                                     │
│ 2. get temporary AWS credentials  ── OIDC ──►  IAM role  (no stored keys!)            │
│ 3. docker build  ──►  docker push  ──────────►  Amazon ECR   (image registry)        │
│ 4. put runtime .env  ───────────────────────►  SSM Parameter Store (encrypted)       │
│ 5. "run this script on the box"  ── SSM ────►  EC2 instance                           │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                                       │
                                                       ▼
                                        ┌──────────── EC2 instance ────────────┐
                                        │ docker login ECR                     │
                                        │ read .env from Parameter Store       │
                                        │ docker pull <new image>              │
                                        │ docker rm -f + docker run  (restart) │
                                        │ curl /_stcore/health   (verify)      │
                                        └──────────────────────────────────────┘
                                                       │
                                                       ▼
                                        http://<EC2 public IP>:8501   ← the live app
```

**Why no SSH?** Opening port 22 to the internet (which is what you'd need,
because GitHub's runners have unpredictable IPs) is a real risk. Instead we
use **AWS Systems Manager (SSM)** — GitHub tells AWS "run this script on that
instance", AWS delivers it through an agent already running on the box. No
inbound ports, no SSH key to leak.

---

## 3. The AWS pieces, one line each

| Piece | What it is | Why we need it |
|---|---|---|
| **ECR** (Elastic Container Registry) | A private Docker Hub inside your AWS account | Somewhere to push the built image so the server can pull it |
| **EC2** | A virtual Linux server | Something to actually *run* the container 24/7 |
| **IAM OIDC provider** | A trust link: "I trust tokens issued by GitHub Actions" | Lets GitHub get AWS credentials without us storing any |
| **IAM role** (`github-actions-hr-assistant`) | A set of permissions GitHub is allowed to borrow, briefly | Push to ECR, write one SSM parameter, send one SSM command |
| **IAM instance profile** (`hr-assistant-ec2`) | Permissions the *server* has | Pull from ECR, read the .env parameter |
| **SSM Parameter Store** | Encrypted key/value store | Carries the runtime `.env` to the box without it ever touching GitHub logs |
| **Security group** | A firewall for the instance | Allow inbound `8501` (the app), nothing else |

---

## 4. Part A — one-time AWS setup

You need the AWS CLI installed and logged in (`aws configure` or `aws sso
login`) as a user allowed to create these resources. Run everything from a
terminal. **A companion copy-paste script is in
[`cicd_commands.md`](cicd_commands.md)** — this section explains what each
block does.

### A0. Set some shell variables (reused below)

```bash
export AWS_REGION=eu-west-2
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export GH_REPO="d-hackmt/hr-rag-deployment"     # <owner>/<repo>
export ECR_REPO=hr-assistant
export SSM_ENV_PARAM=/hr-assistant/env
```

### A1. Create the ECR repository

```bash
aws ecr create-repository \
  --repository-name "$ECR_REPO" \
  --region "$AWS_REGION" \
  --image-scanning-configuration scanOnPush=true
```

This is the private registry the image gets pushed to. `scanOnPush` makes AWS
scan each image for known vulnerabilities.

### A2. Create the GitHub OIDC provider (once per AWS account)

```bash
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com"
```

This tells AWS: "identity tokens signed by GitHub Actions are legitimate."
If it already exists you'll get an error — that's fine, skip it.

### A3. Create the IAM role GitHub Actions will assume

**Trust policy** — *who* may assume it. Only your repo, only on branch `main`:

```bash
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

aws iam create-role \
  --role-name github-actions-hr-assistant \
  --assume-role-policy-document file://trust.json
```

**Permissions policy** — *what* it can do (deliberately narrow):

```bash
cat > perms.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "EcrAuth",   "Effect": "Allow", "Action": "ecr:GetAuthorizationToken", "Resource": "*" },
    { "Sid": "EcrPush",    "Effect": "Allow",
      "Action": ["ecr:BatchCheckLayerAvailability","ecr:GetDownloadUrlForLayer","ecr:BatchGetImage",
                 "ecr:PutImage","ecr:InitiateLayerUpload","ecr:UploadLayerPart","ecr:CompleteLayerUpload"],
      "Resource": "arn:aws:ecr:${AWS_REGION}:${AWS_ACCOUNT_ID}:repository/${ECR_REPO}" },
    { "Sid": "SsmPutEnv",  "Effect": "Allow", "Action": "ssm:PutParameter",
      "Resource": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter${SSM_ENV_PARAM}" },
    { "Sid": "SsmSend",    "Effect": "Allow", "Action": "ssm:SendCommand",
      "Resource": [
        "arn:aws:ssm:${AWS_REGION}::document/AWS-RunShellScript",
        "arn:aws:ec2:${AWS_REGION}:${AWS_ACCOUNT_ID}:instance/*"
      ] },
    { "Sid": "SsmRead",    "Effect": "Allow",
      "Action": ["ssm:GetCommandInvocation","ssm:ListCommands"], "Resource": "*" }
  ]
}
EOF

aws iam put-role-policy \
  --role-name github-actions-hr-assistant \
  --policy-name deploy \
  --policy-document file://perms.json
```

Note the role ARN it prints — you'll paste it into GitHub as `AWS_ROLE_ARN`:
```
arn:aws:iam::<ACCOUNT_ID>:role/github-actions-hr-assistant
```

### A4. Create the instance profile (permissions the server has)

```bash
# a role for the EC2 instance itself
cat > ec2-trust.json <<'EOF'
{ "Version": "2012-10-17",
  "Statement": [{ "Effect": "Allow",
    "Principal": { "Service": "ec2.amazonaws.com" },
    "Action": "sts:AssumeRole" }] }
EOF

aws iam create-role --role-name hr-assistant-ec2 \
  --assume-role-policy-document file://ec2-trust.json

# lets SSM manage the box + lets it pull from ECR
aws iam attach-role-policy --role-name hr-assistant-ec2 \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam attach-role-policy --role-name hr-assistant-ec2 \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly

# lets it read (and decrypt) the one .env parameter
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

# wrap the role in an instance profile (EC2 needs this wrapper)
aws iam create-instance-profile --instance-profile-name hr-assistant-ec2
aws iam add-role-to-instance-profile \
  --instance-profile-name hr-assistant-ec2 --role-name hr-assistant-ec2
```

### A5. Create a security group (the firewall)

```bash
export VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' --output text)

export SG_ID=$(aws ec2 create-security-group \
  --group-name hr-assistant-sg \
  --description "HR assistant - Streamlit 8501" \
  --vpc-id "$VPC_ID" --query GroupId --output text)

# allow the Streamlit port from anywhere (tighten to your IP if you can)
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" --protocol tcp --port 8501 --cidr 0.0.0.0/0
```

No SSH rule on purpose — you get a shell via `aws ssm start-session` instead.

### A6. Launch the EC2 instance

The `user-data` script runs once on first boot and installs Docker. The SSM
agent is already preinstalled on Amazon Linux 2023.

```bash
cat > user-data.sh <<'EOF'
#!/bin/bash
set -eux
dnf install -y docker
systemctl enable --now docker
mkdir -p /opt/hr-assistant
EOF

# latest Amazon Linux 2023 AMI id, straight from AWS
export AMI_ID=$(aws ssm get-parameter \
  --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query 'Parameter.Value' --output text)

aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t3.micro \
  --iam-instance-profile Name=hr-assistant-ec2 \
  --security-group-ids "$SG_ID" \
  --user-data file://user-data.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=hr-assistant-prod}]' \
  --query 'Instances[0].InstanceId' --output text
```

Save the instance id it prints — that's `EC2_INSTANCE_ID` for GitHub. Wait ~2
minutes, then confirm SSM sees it:

```bash
aws ssm describe-instance-information \
  --query "InstanceInformationList[].InstanceId" --output text
```

Get the public URL any time with:

```bash
aws ec2 describe-instances --instance-ids <ID> \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
```

### A7. Put the runtime `.env` into Parameter Store (first time)

The pipeline re-syncs this on every run from a GitHub secret, but seed it once
now so the very first deploy has something to read. Use the strict-format
`.env.docker` (no spaces/quotes):

```bash
aws ssm put-parameter \
  --name "$SSM_ENV_PARAM" \
  --type SecureString \
  --value "$(cat .env.docker)" \
  --overwrite
```

---

## 5. Part B — one-time GitHub setup

Repo → **Settings** → **Secrets and variables** → **Actions**.

**Secrets** (tab: *Secrets*):

| Name | Value |
|---|---|
| `AWS_ROLE_ARN` | `arn:aws:iam::<ACCOUNT_ID>:role/github-actions-hr-assistant` (from A3) |
| `APP_ENV_FILE` | the **entire contents** of `.env.docker`, pasted in as-is |

**Variables** (tab: *Variables*):

| Name | Value |
|---|---|
| `EC2_INSTANCE_ID` | the `i-0abc123...` from A6 |

That's all GitHub stores. No AWS access keys, ever.

---

## 6. Part C — the workflow, explained

File: [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml). It has
one job with six steps.

| Step | What it does | Notes |
|---|---|---|
| **Checkout** | pulls your repo into the runner | standard first step |
| **Configure AWS credentials (OIDC)** | trades a GitHub identity token for temporary AWS keys by assuming `AWS_ROLE_ARN` | `permissions: id-token: write` at the top is what makes this possible |
| **Log in to Amazon ECR** | `docker login` against your private registry | outputs the registry hostname for the next step |
| **Build and push image** | `docker build`, then push two tags: the git SHA (immutable, for rollbacks) and `latest` | the exact image URI is saved to `$GITHUB_ENV` as `IMAGE` |
| **Sync runtime .env to SSM** | writes the `APP_ENV_FILE` secret into Parameter Store as a `SecureString` | so rotating a key = edit the GitHub secret + re-run; the box always reads the current one |
| **Deploy on EC2 via SSM** | fills the `${...}` blanks in `deploy/remote.sh`, sends it to the instance with `ssm send-command`, waits, prints the box's output, fails the job if the remote script failed | `envsubst` only substitutes the 4 named vars; `jq` builds the JSON payload safely |

The remote half is [`deploy/remote.sh`](../deploy/remote.sh): ECR login → read
`.env` from Parameter Store → `docker pull` → `docker rm -f` + `docker run` →
`docker image prune` → `curl /_stcore/health`. `--restart unless-stopped` means
the container also comes back on its own if the instance reboots.

Triggers: every push to `main`, or manually via the **Actions** tab
(`workflow_dispatch`). `concurrency` stops two deploys running at once.

---

## 7. Part D — first deploy and verify

```bash
git add .github/workflows/deploy.yml deploy/remote.sh docs/09_cicd_aws_ecr_ec2.md docs/cicd_commands.md
git commit -m "Add CI/CD: GitHub Actions -> ECR -> EC2"
git push origin main
```

1. GitHub → **Actions** tab → watch the `deploy` run. All six steps should go
   green (~2–4 min).
2. The last step prints the remote script's output — look for
   `Deployed OK: ...:<sha>` and a `ok` from the health check.
3. Open `http://<EC2 public IP>:8501` — the live app.
4. Independent check from your laptop:
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" http://<EC2 public IP>:8501/_stcore/health   # -> 200
   ```

---

## 8. Part E — day-to-day

| Task | How |
|---|---|
| **Ship a change** | `git push origin main` — that's it |
| **Rotate a leaked/expired key** | edit the `APP_ENV_FILE` GitHub secret → re-run the `deploy` workflow (Actions tab → Run workflow). The sync step + `docker run --env-file` pick it up |
| **Roll back** | Actions tab → re-run an older successful `deploy`, **or** SSM a one-liner: `docker run -d ... <ECR-URI>:<old-sha>` |
| **See app logs** | `aws ssm start-session --target <ID>` then `docker logs -f hr-assistant` |
| **Get a shell on the box** | `aws ssm start-session --target <ID>` (no SSH key needed) |
| **Stop paying** | `aws ec2 stop-instances --instance-ids <ID>` (keeps it) or `terminate-instances` (deletes it) |

---

## 9. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| OIDC step: `Not authorized to perform sts:AssumeRoleWithWebIdentity` | `sub` in the trust policy doesn't match. It must be `repo:<owner>/<repo>:ref:refs/heads/main`. Pushing from a different branch won't match by design. |
| ECR push: `denied: ... not authorized` | role's `EcrPush` resource ARN doesn't match the repo, or region mismatch |
| Deploy step hangs then fails at `ssm wait` | instance not registered with SSM — check `describe-instance-information`; needs `AmazonSSMManagedInstanceCore` + outbound internet (default subnet has it) |
| remote stderr: `Unable to locate credentials` | instance profile not attached, or you launched before creating it — `aws ec2 associate-iam-instance-profile` after the fact |
| remote stderr: `AccessDenied` on `ssm get-parameter` | `hr-assistant-ec2` role missing the `read-env` inline policy or the `kms:Decrypt` on `alias/aws/ssm` |
| Health check fails but container runs | app crashed on boot — `docker logs hr-assistant`; usually a bad/missing key in the `.env` (check `QDRANT_URL` ends in `:443`) |
| Site won't load in browser | security group missing the `8501` ingress rule, or you're hitting `https://` (it's plain `http` on `:8501`) |

---

## 10. Files added on this branch

| File | Purpose |
|---|---|
| [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) | The pipeline: build → push to ECR → deploy to EC2 |
| [`deploy/remote.sh`](../deploy/remote.sh) | The script that runs *on* the instance (sent via SSM) |
| [`docs/09_cicd_aws_ecr_ec2.md`](09_cicd_aws_ecr_ec2.md) | This document |
| [`docs/cicd_commands.md`](cicd_commands.md) | Copy-paste command flow for the one-time AWS setup |

---

## 11. Assignment for students

1. **Lock the deploy role to a single instance.** Right now `SsmSend`'s
   resource is `instance/*`. Change it to the real instance ARN and confirm
   the pipeline still works.
2. **Add a test gate.** Insert a step before `Build and push` that runs
   `python -c "import hr_assistant.pipeline"` (or a real `pytest`), so a
   broken import never gets deployed.
3. **Put it behind a real domain + HTTPS.** Run [Caddy](https://caddyserver.com/)
   as a second container (`-p 80:80 -p 443:443`) reverse-proxying to
   `localhost:8501`, point a domain's DNS at the instance, and get an
   automatic Let's Encrypt certificate. Update the security group.
4. **Zero-downtime deploy.** The current `docker rm -f` + `docker run` has a
   ~5–10s gap. Start the new container on a temp name, health-check it, then
   swap — or move to `docker compose` on the box with two replicas.
5. **Move off a single box.** Rewrite the deploy step to update an ECS Fargate
   service instead of SSM-ing one instance (see the ECS path in AWS docs).

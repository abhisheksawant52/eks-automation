# EKS Automation

End-to-end tooling for provisioning and managing **AWS Elastic Kubernetes Service (EKS)** clusters. This repo combines:

- **Terraform** — provisions VPC, subnets, IAM roles, EKS cluster, and managed node group
- **Python CLI** (`eks_manager.py`) — day-two operations (create, delete, scale, list, credentials)
- **GitHub Actions** — CI/CD pipeline with plan-on-PR and apply-on-merge
- **Kubernetes manifests** — sample nginx workload to smoke-test the cluster

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| AWS CLI | 2.x+ | [aws.amazon.com/cli](https://aws.amazon.com/cli/) |
| Terraform | 1.5+ | [developer.hashicorp.com](https://developer.hashicorp.com/terraform/install) |
| Python | 3.11+ | [python.org](https://www.python.org/downloads/) |
| kubectl | 1.29+ | [kubernetes.io](https://kubernetes.io/docs/tasks/tools/) |

An AWS account with permissions to create VPCs, IAM roles, and EKS clusters is required.

---

## Repository Structure

```
eks-automation/
├── .github/workflows/eks-deploy.yml   # CI/CD pipeline
├── kubernetes/deployment.yaml          # Sample nginx app + NLB service + HPA
├── src/
│   ├── eks_manager.py                  # Python CLI tool
│   └── requirements.txt
├── terraform/
│   ├── main.tf                         # VPC + IAM + EKS cluster + node group
│   ├── variables.tf
│   └── outputs.tf
└── README.md
```

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/abhisheksawant52/eks-automation.git
cd eks-automation

# 2. Configure AWS credentials
export AWS_ACCESS_KEY_ID="<your-access-key>"
export AWS_SECRET_ACCESS_KEY="<your-secret-key>"
export AWS_DEFAULT_REGION="us-east-1"

# 3. Provision with Terraform
cd terraform
terraform init
terraform apply -var="cluster_name=my-cluster"

# 4. Update kubeconfig
cd ..
pip install -r src/requirements.txt
python src/eks_manager.py get-credentials --cluster-name my-cluster --region us-east-1

# 5. Deploy sample app
kubectl apply -f kubernetes/deployment.yaml

# 6. Get load balancer DNS
kubectl get svc nginx-service -n sample-app --watch
```

---

## Authentication

Uses the standard AWS credential chain — boto3 tries in this order:

1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. AWS CLI profile (`~/.aws/credentials`)
3. IAM instance/container role

For local development:

```bash
aws configure
# or
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="us-east-1"
```

---

## Terraform Usage

### Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `region` | `us-east-1` | AWS region |
| `cluster_name` | `eks-automation-cluster` | EKS cluster name |
| `kubernetes_version` | `1.29` | Kubernetes version |
| `instance_type` | `t3.medium` | EC2 instance type |
| `desired_size` | `2` | Desired node count |
| `min_size` | `1` | Minimum nodes |
| `max_size` | `10` | Maximum nodes |
| `vpc_cidr` | `10.0.0.0/16` | VPC CIDR |
| `endpoint_public_access` | `true` | Enable public API endpoint |

### Commands

```bash
cd terraform

terraform init
terraform plan -var="cluster_name=my-cluster"
terraform apply -var="cluster_name=my-cluster"

# Get outputs
terraform output cluster_endpoint
terraform output kubeconfig_command

# Destroy
terraform destroy -var="cluster_name=my-cluster"
```

---

## Python CLI Usage

### Installation

```bash
pip install -r src/requirements.txt
export AWS_DEFAULT_REGION="us-east-1"
```

### Commands

#### `create-cluster`
```bash
python src/eks_manager.py create-cluster \
  --cluster-name my-cluster \
  --role-arn arn:aws:iam::123456789:role/eks-role \
  --subnet-ids subnet-abc,subnet-def \
  --security-group-ids sg-xyz
```

#### `list-clusters`
```bash
python src/eks_manager.py list-clusters --region us-east-1
python src/eks_manager.py list-clusters --output json
```

#### `describe-cluster`
```bash
python src/eks_manager.py describe-cluster --cluster-name my-cluster
```

#### `get-credentials`
```bash
python src/eks_manager.py get-credentials --cluster-name my-cluster --region us-east-1
```

#### `create-nodegroup`
```bash
python src/eks_manager.py create-nodegroup \
  --cluster-name my-cluster \
  --node-role-arn arn:aws:iam::123456789:role/node-role \
  --subnet-ids subnet-abc,subnet-def \
  --desired-size 3
```

#### `scale-nodegroup`
```bash
python src/eks_manager.py scale-nodegroup \
  --cluster-name my-cluster \
  --nodegroup-name nodegroup-1 \
  --desired-size 5
```

#### `delete-cluster`
```bash
python src/eks_manager.py delete-cluster --cluster-name my-cluster --yes
```

---

## GitHub Actions Setup

Add these secrets in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_REGION` | Target region (e.g. `us-east-1`) |

### Workflow Behaviour

| Event | Action |
|-------|--------|
| PR to `main` | `terraform plan` — posts output as PR comment |
| Push to `main` | `terraform apply` — requires `production` env approval |
| Manual (destroy) | `terraform destroy` — requires `production` env approval |

---

## Deploying the Sample App

```bash
kubectl apply -f kubernetes/deployment.yaml
kubectl get pods -n sample-app --watch
kubectl get svc nginx-service -n sample-app
curl http://<EXTERNAL-DNS>
```

Expected: HTML page showing "🚀 EKS Cluster is Live!"

---

## Cleanup

```bash
# Remove Kubernetes resources
kubectl delete namespace sample-app

# Destroy infrastructure
cd terraform
terraform destroy -var="cluster_name=my-cluster"
```

---

## Troubleshooting

**`NoCredentialsError`** — Run `aws configure` or export `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.

**Cluster stuck in CREATING** — EKS clusters take 10–15 minutes. Run `eks_manager.py describe-cluster` to check status.

**`kubectl` unauthorized** — Run `get-credentials` again; your token may have expired (EKS tokens last 15 minutes).

**LoadBalancer pending** — Ensure the node group is `ACTIVE` and the NLB controller has the right IAM permissions.

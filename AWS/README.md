# Cloud-Benchmark - AWS

This script is a read-only utility that counts cloud resources in your AWS account. If you run this in your organization account, it will discover resources in all accounts in your organization.

No changes will be made to your account. No data will be sent anywhere and will remain in your cloud shell environment.

## 🔧 How it works
This script can run against an individual AWS account or all child accounts in an AWS Organization. When running the script in CloudShell, it will establish the session using the AWS Identity currently signed in. When running the script in your local environment, it will establish the session based on your AWS CLI configuration. Please see [Local Environment Instructions](../README.md) for more details. If your AWS Identity is in the AWS Organization Management account, the script will use the default role `OrganizationAccountAccessRole` (or custom role if provided) to switch into each child account.  If your AWS Identity is not in an AWS Organization Management account, the script will only process resources in this single account. Upon completion, a CSV report is generated with the findings.

### Reported Resources
Reported Resources will include a count of each of the following resource types per AWS Region:  

| Resource | Description |
| :--- | :--- |
| Terminated VMs | Terminated EC2 Instances |
| Running VMs | Running EC2 Instances |
| Terminated Kubernetes Nodes | Terminated EKS Nodes |
| Running Kubernetes Nodes | Running EKS Nodes |
| Active EKS Fargate Profiles | Active EKS Fargate Profiles for each EKS Cluster. Excludes any existing Falcon Profiles eg. fp-falcon* |
| ECS Service Fargate Tasks | DesiredCount of tasks in Active ECS Services.  Excludes standalone tasks or tasks that are scheduled outside of Services |
  
## ▶️ Usage

### Initialize execution environment

Open AWS Cloud Shell ([overview](https://aws.amazon.com/cloudshell/), [documentation](https://docs.aws.amazon.com/cloudshell/latest/userguide/welcome.html)) using one of the direct links:

| Region | Link |
| :--- | :--- |
| us-east-1 | **[Virginia, United States](https://us-east-1.console.aws.amazon.com/cloudshell/home?region=us-east-1)** |
| us-east-2 | **[Ohio, United States](https://us-east-2.console.aws.amazon.com/cloudshell/home?region=us-east-2)** |
| us-west-2 | **[Oregon, United States](https://us-west-2.console.aws.amazon.com/cloudshell/home?region=us-west-2)** |
| eu-west-1 | **[Ireland](https://eu-west-1.console.aws.amazon.com/cloudshell/home?region=eu-west-1)** |
| ap-northeast-1 | **[Tokyo, Japan](https://ap-northeast-1.console.aws.amazon.com/cloudshell/home?region=ap-northeast-1)** |

### Export Environment Variables

```shell
export AWS_ASSUME_ROLE_NAME="Example-Role-Name"
```

### Execute Script

```shell
curl https://raw.githubusercontent.com/CrowdStrike/cloud-resource-estimator/main/benchmark.sh | bash
```

### Collect the findings

```shell
cat ./cloud-benchmark/*benchmark.csv
```

## ⚙️ Features & Configuration

### Complete Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `AWS_ASSUME_ROLE_NAME` | `OrganizationAccountAccessRole` | IAM role name for cross-account access |
| `AWS_REGIONS` | All regions | Comma-separated list of regions to scan |
| `AWS_THREADS` | `5` | Number of concurrent account threads |
| `AWS_BATCH_SIZE` | `20` | Accounts processed per batch |
| `AWS_BATCH_DELAY` | `30` | Seconds to wait between batches |
| `AWS_API_DELAY` | `0.1` | Seconds to wait between API calls |
| `AWS_MAX_RETRIES` | `5` | Maximum retry attempts for failed operations |
| `AWS_OPERATION_TIMEOUT` | `300` | Timeout for individual operations (seconds) |
| `AWS_RESUME_FILE` | `aws_benchmark_progress.json` | Progress tracking file |
| `AWS_SKIP_ACCOUNTS` | None | Comma-separated list of account IDs to skip |
| `AWS_DRY_RUN` | `false` | Set to `true` to simulate without API calls |

### Configuration Recommendations per Organization Size

#### Standard Processing for Small Organizations (< 50 accounts) 
```shell
# Default settings work well - no configuration needed
curl https://raw.githubusercontent.com/CrowdStrike/cloud-resource-estimator/main/benchmark.sh | bash
```

#### Fast Processing for Smaller Organizations (< 50 accounts)
```shell
export AWS_THREADS=8
export AWS_BATCH_SIZE=50
export AWS_BATCH_DELAY=15
export AWS_API_DELAY=0.05
curl https://raw.githubusercontent.com/CrowdStrike/cloud-resource-estimator/main/benchmark.sh | bash
```

#### Medium Organizations (50-200 accounts)
```shell
export AWS_THREADS=4
export AWS_BATCH_SIZE=15
export AWS_BATCH_DELAY=30
curl https://raw.githubusercontent.com/CrowdStrike/cloud-resource-estimator/main/benchmark.sh | bash
```

#### Large Organizations (200+ accounts)
```shell
export AWS_THREADS=2
export AWS_BATCH_SIZE=10
export AWS_BATCH_DELAY=60
export AWS_API_DELAY=0.2
curl https://raw.githubusercontent.com/CrowdStrike/cloud-resource-estimator/main/benchmark.sh | bash
```

### Resume Interrupted Runs

If the script times out or is interrupted, it automatically saves progress and can be resumed:

```shell
# The script will automatically resume from where it left off
curl https://raw.githubusercontent.com/CrowdStrike/cloud-resource-estimator/main/benchmark.sh | bash
```

The script will display progress and automatically skip completed accounts.

### Other Usage Options

#### Scan specific regions only
```shell
export AWS_REGIONS="us-east-1,us-west-2,eu-west-1"
```

#### Skip Problematic Accounts
```shell
python aws_cspm_benchmark.py \
  --skip-accounts "123456789012,234567890123,345678901234"
```

#### Dry Run to Preview Processing
```shell
python aws_cspm_benchmark.py --dry-run
```

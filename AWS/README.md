# Cloud-Benchmark - AWS

This script is a read-only utility that counts cloud resources in your AWS account. If you run this in your organization account, it will discover resources in all accounts in your organization.

No changes will be made to your account. No data will be sent anywhere and will remain in your cloud shell environment.

## How it works
This script can run against an individual AWS account or all child accounts in an AWS Organization. When running the script in CloudShell, it will establish the session using the AWS Identity currently signed in. When running the script in your local environment, it will establish the session based on your AWS CLI configuration. Please see [Local Environment Instructions](../README.md) for more details. If your AWS Identity is in the AWS Organization Management account, the script will use the default role `OrganizationAccountAccessRole` (or custom role if provided) to switch into each child account.  If your AWS Identity is not in an AWS Organization Management account, the script will only process resources in this single account. Upon completion, a CSV report is generated with the findings.

## Reported Resources
Reported Resources will include a count of each of the following resource types per AWS Region:  

| Resource | Description |
| :--- | :--- |
| Terminated VMs | Terminated EC2 Instances |
| Running VMs | Running EC2 Instances |
| Terminated Kubernetes Nodes | Terminated EKS Nodes |
| Running Kubernetes Nodes | Running EKS Nodes |
| Active EKS Fargate Profiles | Active EKS Fargate Profiles for each EKS Cluster. Excludes any existing Falcon Profiles eg. fp-falcon* |
| ECS Service Fargate Tasks | DesiredCount of tasks in Active ECS Services.  Excludes standalone tasks or tasks that are scheduled outside of Services |
  
## How to use

### Initialize execution environment

Open AWS Cloud Shell ([overview](https://aws.amazon.com/cloudshell/), [documentation](https://docs.aws.amazon.com/cloudshell/latest/userguide/welcome.html)) using one of the direct links:

| Region | Link |
| :--- | :--- |
| us-east-1 | **[Virginia, United States](https://us-east-1.console.aws.amazon.com/cloudshell/home?region=us-east-1)** |
| us-east-2 | **[Ohio, United States](https://us-east-2.console.aws.amazon.com/cloudshell/home?region=us-east-2)** |
| us-west-2 | **[Oregon, United States](https://us-west-2.console.aws.amazon.com/cloudshell/home?region=us-west-2)** |
| eu-west-1 | **[Ireland](https://eu-west-1.console.aws.amazon.com/cloudshell/home?region=eu-west-1)** |
| ap-northeast-1 | **[Tokyo, Japan](https://ap-northeast-1.console.aws.amazon.com/cloudshell/home?region=ap-northeast-1)** |

### Example

```shell
curl https://raw.githubusercontent.com/CrowdStrike/cloud-resource-estimator/main/benchmark.sh | bash
```

### Collect the findings

```shell
cat ./cloud-benchmark/*benchmark.csv
```

### Provide Custom IAM Role Name

```shell
export AWS_ASSUME_ROLE_NAME="custom-role-name"
```

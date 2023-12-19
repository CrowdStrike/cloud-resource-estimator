# Cloud-Benchmark - AWS

This script is a read-only utility that counts cloud resources in your AWS account. If you run this in your organization account, it will discover resources in all accounts in your organization.

No changes will be made to your account. No data will be sent anywhere and will remain in your cloud shell environment.

## How it works
### Single Account
When this script runs in an individual AWS Account (ie. not the Organization Management Account), the script will perform the following steps:

- establish session using AWS Identity in CloudShell 
- check if running in Organization by making requests against the Organization service
- if this call fails, the script will return "Cannot autodiscover adjacent accounts: cannot list accounts within the AWS organization"
- gracefully continue to process the resources in the single AWS Account tied to your Identity
- generate a csv report

### Organization  
When this script runs in an AWS Organization Management account, the script perform the following steps:  

- establish session using AWS Identity in CloudShell 
- check if running in Organization by making requests against the Organization service
- when this call succeeds, generate a list of Account IDs in your Organization
- foreach Account ID, create a session with the default role OrganizationAccountAccessRole or a custom role if provided
- process the resources in each account
- generate a csv report

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

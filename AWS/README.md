# Cloud-Benchmark - AWS

This script is a read-only utility that counts cloud resources in your AWS account. If you run this in your organization account, it will discover resources in all accounts in your organization.

No changes will be made to your account. No data will be sent anywhere and will remain in your cloud shell environment.

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


### Run the script

   ```
   curl https://raw.githubusercontent.com/CrowdStrike/Cloud-Benchmark/main/benchmark.sh | /bin/bash
   ```

(Alternatively, if you happen to be frequent cloud user and have `aws` cli utility installed locally, you can run the below step locally instead of using cloud shell).

### Collect the findings

```
cat ./cloud-benchmark/*benchmark.csv
```

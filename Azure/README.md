# Cloud-Benchmark - Azure

This script is a read-only utility that counts cloud resources in your Azure account.
No changes will be made to your account. No data will be sent anywhere and will remain in your cloud shell environment.

## How to use

### Initialize execution environment

- Log-in with azure. Using the account that has read access to all your azure tenants/subscriptions
- Navigate to [Azure Cloud Shell](https://shell.azure.com) and choose bash option

### Run the script

```shell
curl https://raw.githubusercontent.com/CrowdStrike/cloud-resource-estimator/main/benchmark.sh | bash
```

### Collect the findings

```shell
cat ./cloud-benchmark/*benchmark.csv
```

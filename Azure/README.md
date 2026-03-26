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

## Advanced Usage

### Subscription Filtering

The Azure script supports filtering which subscriptions to scan:

#### Skip Specific Subscriptions

```shell
python3 azure_cspm_benchmark.py --skip-subscriptions "sub-id-1,sub-id-2,sub-id-3"
```

Or using environment variables:

```shell
export AZURE_SKIP_SUBSCRIPTIONS="sub-id-1,sub-id-2,sub-id-3"
python3 azure_cspm_benchmark.py
```

#### Process Only Specific Subscriptions

```shell
python3 azure_cspm_benchmark.py --include-subscriptions "sub-id-1,sub-id-2"
```

Or using environment variables:

```shell
export AZURE_INCLUDE_SUBSCRIPTIONS="sub-id-1,sub-id-2"
python3 azure_cspm_benchmark.py
```

**Note:** `--include-subscriptions` takes precedence over `--skip-subscriptions` if both are specified.

### Command Line Options

| Option | Environment Variable | Description |
|--------|---------------------|-------------|
| `--skip-subscriptions` | `AZURE_SKIP_SUBSCRIPTIONS` | Comma-separated list of subscription IDs to exclude from scanning |
| `--include-subscriptions` | `AZURE_INCLUDE_SUBSCRIPTIONS` | Comma-separated list of subscription IDs to scan (exclusive filter) |

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
cat ./cloud-benchmark/azure-benchmark.csv
```

## Advanced Usage

### Subscription Filtering

The Azure script supports filtering which subscriptions to scan. This is useful for:
- Testing with a subset of subscriptions
- Excluding problematic or restricted subscriptions
- Focusing on specific business units or departments

#### Skip Specific Subscriptions

Exclude specific subscriptions from scanning:

```shell
python3 azure_cspm_benchmark.py --skip-subscriptions "sub-id-1,sub-id-2,sub-id-3"
```

Or using environment variables:

```shell
export AZURE_SKIP_SUBSCRIPTIONS="sub-id-1,sub-id-2,sub-id-3"
python3 azure_cspm_benchmark.py
```

#### Process Only Specific Subscriptions

Scan only specific subscriptions (all others are ignored):

```shell
python3 azure_cspm_benchmark.py --include-subscriptions "sub-id-1,sub-id-2"
```

Or using environment variables:

```shell
export AZURE_INCLUDE_SUBSCRIPTIONS="sub-id-1,sub-id-2"
python3 azure_cspm_benchmark.py
```

**Important:**
- `--include-subscriptions` takes **full precedence**. If set, `--skip-subscriptions` is completely ignored.
- Use **one or the other**, not both.
- Invalid subscription IDs will generate warnings but won't stop execution.
- If filtering results in zero subscriptions, the script will exit with an error.

### Input Validation

The script validates subscription IDs and provides helpful feedback:

- **Invalid IDs**: If you provide subscription IDs that don't exist, you'll see a warning:
  ```
  WARNING: The following subscription IDs in include list were not found: invalid-id-1, invalid-id-2
  ```

- **Empty filters**: If filtering results in no subscriptions to process:
  ```
  ERROR: No subscriptions to process after filtering. Check your filter settings.
  ```
  The script exits with code 1 (failure).

- **Whitespace handling**: Empty values and extra whitespace in comma-separated lists are automatically filtered out:
  ```shell
  # This works fine - empty values are ignored
  export AZURE_INCLUDE_SUBSCRIPTIONS="sub1, , ,sub2"
  ```

### Exit Codes

The script returns standard exit codes for automation:

- **0**: Success - subscriptions were processed and CSV was generated
- **1**: Failure - no subscriptions to process, authentication failed, or Azure API error

### Command Line Options

| Option | Environment Variable | Description |
|--------|---------------------|-------------|
| `--skip-subscriptions` | `AZURE_SKIP_SUBSCRIPTIONS` | Comma-separated list of subscription IDs to exclude from scanning |
| `--include-subscriptions` | `AZURE_INCLUDE_SUBSCRIPTIONS` | Comma-separated list of subscription IDs to scan (exclusive filter, takes full precedence) |

### Usage with benchmark.sh

The wrapper script supports the same environment variables:

```shell
# Skip specific subscriptions
export AZURE_SKIP_SUBSCRIPTIONS="sub-id-1,sub-id-2"
./benchmark.sh azure

# Or include only specific subscriptions
export AZURE_INCLUDE_SUBSCRIPTIONS="sub-id-3,sub-id-4"
./benchmark.sh azure
```

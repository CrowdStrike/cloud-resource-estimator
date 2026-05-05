![CrowdStrike Logo (Light)](https://raw.githubusercontent.com/CrowdStrike/.github/main/assets/cs-logo-light-mode.png#gh-light-mode-only)
![CrowdStrike Logo (Dark)](https://raw.githubusercontent.com/CrowdStrike/.github/main/assets/cs-logo-dark-mode.png#gh-dark-mode-only)

# CrowdStrike Cloud Resource Estimator

This multi-cloud resource auditing utility helps organizations calculate the size of their cloud deployments across AWS, Azure, and Google Cloud Platform. It's designed for **CrowdStrike CWP/Horizon licensing calculations** and cloud security posture management (CSPM) benchmarking.

## Security

- All output (CSV, progress file) is written locally — nothing is sent to CrowdStrike or any external service automatically.
- **Least-privilege recommendation:** This script requires read-only permissions only. Do not run it with root account credentials or `AdministratorAccess`. Use a dedicated IAM role scoped to the actions the script needs (`ec2:Describe*`, `ecs:List*`/`Describe*`, `eks:List*`/`Describe*`, `organizations:ListAccounts`).
- Each release ships a `checksum.txt`. Verify the download before running (see installation steps below).

## What This Tool Does

The Cloud Resource Estimator performs **read-only** scanning of your cloud infrastructure to count:

- Virtual machines and compute instances
- Container services (ECS, AKS, GKE)
- Serverless functions and managed services
- Other billable resources relevant for CSPM licensing

**No changes are made to your cloud environment** - this is strictly an auditing and counting tool.

## Running an audit

The `benchmark.sh` entrypoint script helps you to perform sizing calculations for your cloud resources. It detects the cloud provider (AWS, Azure, or GCP) and downloads the necessary scripts to perform the calculation. You can also pass one or more cloud providers as arguments.

## Configuration

Each cloud provider supports various environment variables for performance tuning and filtering. Below are the key configuration options for each provider (for complete configuration details, see the provider-specific README files):

### AWS Configuration

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

To use, please export variables in your environment prior to running the script:

```shell
export AWS_ASSUME_ROLE_NAME="Example-Role-Name"
```

### Azure Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `AZURE_SKIP_SUBSCRIPTIONS` | None | Comma-separated list of subscription IDs to exclude from scanning |
| `AZURE_INCLUDE_SUBSCRIPTIONS` | None | Comma-separated list of subscription IDs to scan (exclusive filter, takes full precedence) |

**Important**:
- `AZURE_INCLUDE_SUBSCRIPTIONS` takes **full precedence** - if set, `AZURE_SKIP_SUBSCRIPTIONS` is completely ignored
- Use one or the other, not both
- Invalid subscription IDs generate warnings but don't stop execution
- Empty filter results exit with error code 1

Example usage:

```shell
# Skip specific subscriptions
export AZURE_SKIP_SUBSCRIPTIONS="sub-id-1,sub-id-2"

# OR (use one or the other, not both)

# Include only specific subscriptions
export AZURE_INCLUDE_SUBSCRIPTIONS="sub-id-3,sub-id-4"
```

### GCP Configuration

GCP supports performance tuning and filtering options including project filtering (with automatic sys-* project exclusion) and threading options.

For complete configuration details, see the provider-specific README files:

- **AWS**: See [AWS README](AWS/README.md) for detailed configuration options
- **Azure**: See [Azure README](Azure/README.md) for subscription filtering and performance settings
- **GCP**: See [GCP README](GCP/README.md) for project filtering (including sys-* project handling) and threading options

## Usage

```shell
./benchmark.sh [aws|azure|gcp]...
```

Below are two different ways to execute the script.

### In Cloud Shell

To execute the script in your environment using Cloud Shell, follow the appropriate guide based on your cloud provider:

- [AWS](AWS/README.md)
- [Azure](Azure/README.md)
- [GCP](GCP/README.md)

### In your Local Environment

For those who prefer to run the script locally, or would like to run the script against more than one cloud provider at a time, follow the instructions below:

#### Requirements

- Python 3
- pip
- curl
- Appropriate cloud provider CLI ([AWS](https://aws.amazon.com/cli/), [Azure](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli), [GCP](https://cloud.google.com/sdk/docs/install))

#### Steps

1. Download the script and verify its checksum:

    ```shell
    RELEASE_VERSION="v1.0.0"
    curl -sLO "https://github.com/CrowdStrike/cloud-resource-estimator/releases/download/${RELEASE_VERSION}/benchmark.sh"
    curl -sL "https://github.com/CrowdStrike/cloud-resource-estimator/releases/download/${RELEASE_VERSION}/checksum.txt" \
      | grep benchmark.sh | sha256sum -c        # Linux / CloudShell
      # | grep benchmark.sh | shasum -a 256 -c  # macOS
    ```

1. Set execution permissions:

    ```shell
    chmod +x benchmark.sh
    ```

1. Example: Run the script against AWS and Azure:

    ```shell
    ./benchmark.sh aws azure
    ```

---

## Development

Please review our [Developer Guide](DEVELOPMENT.md) for more information on how to contribute to this project.

## License

These scripts are provided to the community, for free, under the Unlicense license. As such, these scripts
carry no formal support, express or implied.

## Questions?

Please review our [Code of Conduct](CODE_OF_CONDUCT.md) and then submit an issue or pull request.
We will address the issue as quickly as possible.

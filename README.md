![CrowdStrike Logo (Light)](https://raw.githubusercontent.com/CrowdStrike/.github/main/assets/cs-logo-light-mode.png#gh-light-mode-only)
![CrowdStrike Logo (Dark)](https://raw.githubusercontent.com/CrowdStrike/.github/main/assets/cs-logo-dark-mode.png#gh-dark-mode-only)

# CrowdStrike Cloud Resource Estimator

This multi-cloud resource auditing utility helps organizations calculate the size of their cloud deployments across AWS, Azure, and Google Cloud Platform. It's designed for **CrowdStrike CWP/Horizon licensing calculations** and cloud security posture management (CSPM) benchmarking.

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

Each cloud provider supports various environment variables for performance tuning and filtering. Below are the key AWS configuration options (for complete configuration details, see the provider-specific README files):

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

### Azure and GCP Configuration

Azure and GCP also support performance tuning and filtering options. For complete configuration details:

- **Azure**: See [Azure README](Azure/README.md) for subscription filtering and performance settings
- **GCP**: See [GCP README](GCP/README.md) for project filtering (including sys-* project handling) and threading options

**Note**: see [AWS Readme](AWS/README.md) for detailed configuration options.

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

1. Download the script:

    ```shell
    curl -O https://raw.githubusercontent.com/CrowdStrike/cloud-resource-estimator/main/benchmark.sh
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

**Alternatively, you can run the script directly from the URL:**

- Run the script against AWS and Azure:

    ```shell
    curl https://raw.githubusercontent.com/CrowdStrike/cloud-resource-estimator/main/benchmark.sh | bash -s -- aws azure
    ```

- Run the script and let it determine the available cloud providers:

    ```shell
    curl https://raw.githubusercontent.com/CrowdStrike/cloud-resource-estimator/main/benchmark.sh | bash
    ```

## Development

Please review our [Developer Guide](DEVELOPMENT.md) for more information on how to contribute to this project.

## License

These scripts are provided to the community, for free, under the Unlicense license. As such, these scripts
carry no formal support, express or implied.

## Questions?

Please review our [Code of Conduct](CODE_OF_CONDUCT.md) and then submit an issue or pull request.
We will address the issue as quickly as possible.

![CrowdStrike Falcon](https://raw.githubusercontent.com/CrowdStrike/falconpy/main/docs/asset/cs-logo.png) [![Twitter URL](https://img.shields.io/twitter/url?label=Follow%20%40CrowdStrike&style=social&url=https%3A%2F%2Ftwitter.com%2FCrowdStrike)](https://twitter.com/CrowdStrike)<br/>

# CrowdStrike CWP / Horizon Benchmark Utilities

These utilities have been developed to assist you in calculating the overall size of a cloud deployment.

## Running an audit

The `benchmark.sh` entrypoint script helps you to perform sizing calculations for your cloud resources. It detects the cloud provider (AWS, Azure, or GCP) and downloads the necessary scripts to perform the calculation. You can also pass one or more cloud providers as arguments.

***Configuration:***

The script recognizes the following environmental variables:

- `AWS_ASSUME_ROLE_NAME`: The name of the AWS role to assume (optional)

To use, please export the variable in your environment prior to running the script:

```shell
export ENV_VARIABLE="Example-Value"
```

***Usage:***

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
- Approprate cloud provider CLI ([AWS](https://aws.amazon.com/cli/), [Azure](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli), [GCP](https://cloud.google.com/sdk/docs/install))

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

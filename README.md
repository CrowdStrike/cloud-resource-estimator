![CrowdStrike Falcon](https://raw.githubusercontent.com/CrowdStrike/falconpy/main/docs/asset/cs-logo.png) [![Twitter URL](https://img.shields.io/twitter/url?label=Follow%20%40CrowdStrike&style=social&url=https%3A%2F%2Ftwitter.com%2FCrowdStrike)](https://twitter.com/CrowdStrike)<br/>

# CrowdStrike Horizon Benchmark Utilities
These utilities have been developed to assist you in calculating the overall size of a cloud deployment.

+ [Running an audit](#running-an-audit)
+ [Notes](#notes)
+ [Cloud Shell documentation](#cloud-shell-documentation)
+ [License and Questions](#license)

## Running an audit
+ Login to your cloud provider and then connect to Cloud Shell.
    - If asked, select `BASH` for your environment.
+ Execute the following command: 
```shell
curl https://raw.githubusercontent.com/CrowdStrike/Cloud-Benchmark/main/benchmark.sh | /bin/bash
```

Results will be calculated and displayed directly to your terminal.

## Notes
- Scripts can be executed directly as shown above, or downloaded and then executed at a later time.
    + Don't forget to set execution permissions on `benchmark.sh` if you decide to download and execute later.
    + Required Python dependencies are listed in the requirements.txt file residing in the directory for that cloud provider.
        - Install these dependencies with the command:
        ```shell
        pip install -r requirements.txt
        ```
- Downloaded audit scripts are developed using Python 3 and BASH.
- Audit scripts are removed after the process completes.
- As part of the audit, necessary dependencies are installed based upon cloud provider.

## Cloud Shell documentation
Cloud Shell is an online development and operations environment accessible anywhere with your browser. AWS, Azure
and GCP all support Cloud Shell environments and provide documentation for using these environments.

### AWS Cloud Shell
[AWS Cloud Shell overview](https://aws.amazon.com/cloudshell/) ||
[AWS Cloud Shell documentation](https://docs.aws.amazon.com/cloudshell/latest/userguide/welcome.html) <BR/>

#### AWS Cloud Shell direct links
| Region | Link |
| :--- | :--- |
| us-east-1 | **[Virginia, United States](https://us-east-1.console.aws.amazon.com/cloudshell/home?region=us-east-1)** |
| us-east-2 | **[Ohio, United States](https://us-east-2.console.aws.amazon.com/cloudshell/home?region=us-east-2)** |
| us-west-2 | **[Oregon, United States](https://us-west-2.console.aws.amazon.com/cloudshell/home?region=us-west-2)** |
| eu-west-1 | **[Ireland](https://eu-west-1.console.aws.amazon.com/cloudshell/home?region=eu-west-1)** |
| ap-northeast-1 | **[Tokyo, Japan](https://ap-northeast-1.console.aws.amazon.com/cloudshell/home?region=ap-northeast-1)** |

### Azure Cloud Shell
[Azure Cloud Shell overview](https://docs.microsoft.com/en-us/azure/cloud-shell/overview) ||
[Azure Cloud Shell Quickstart](https://docs.microsoft.com/en-us/azure/cloud-shell/quickstart) ||
**[Azure Cloud Shell direct link](https://shell.azure.com)**

### Google Cloud Shell
[Google Cloud Shell overview](https://cloud.google.com/shell) ||
[Google Cloud Shell documentation](https://cloud.google.com/shell/docs) || 
**[Google Cloud Shell direct link](https://shell.cloud.google.com/)**

## License
These scripts are provided to the community, for free, under the Unlicense license. As such, these scripts
carry no formal support, express or implied.

## Questions?
Please review our [Code of Conduct](CODE_OF_CONDUCT.md) and then submit an issue or pull request.
We will address the issue as quickly as possible.
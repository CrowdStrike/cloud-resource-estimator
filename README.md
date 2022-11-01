![CrowdStrike Falcon](https://raw.githubusercontent.com/CrowdStrike/falconpy/main/docs/asset/cs-logo.png) [![Twitter URL](https://img.shields.io/twitter/url?label=Follow%20%40CrowdStrike&style=social&url=https%3A%2F%2Ftwitter.com%2FCrowdStrike)](https://twitter.com/CrowdStrike)<br/>

# CrowdStrike CWP / Horizon Benchmark Utilities
These utilities have been developed to assist you in calculating the overall size of a cloud deployment.

## Running an audit

To run the script in your environment, please follow the guide based on the cloud you are using:

 - [AWS](AWS/README.md)
 - [Azure](Azure/README.md)
 - [GCP](GCP/README.md)

This script is a read-only utility that counts cloud resources in your AWS account. Results will be calculated and displayed directly to your terminal.

## Developer notes
- Scripts can be executed directly as shown above, or downloaded and then executed at a later time.
    + Don't forget to set execution permissions on `benchmark.sh` if you decide to download and execute later.
    + Required Python dependencies are listed in the requirements.txt file residing in the directory for that cloud provider.
        - Install these dependencies with the command:
          ```shell
          pip3 install -r requirements.txt
          ```
          *or*
          
          ```shell
          python3 -m pip install -r requirements.txt
          ```
- Downloaded audit scripts are developed using Python 3 and BASH.
- Audit scripts are removed after the process completes.
- As part of the audit, necessary dependencies are installed based upon cloud provider.

## License
These scripts are provided to the community, for free, under the Unlicense license. As such, these scripts
carry no formal support, express or implied.

## Questions?
Please review our [Code of Conduct](CODE_OF_CONDUCT.md) and then submit an issue or pull request.
We will address the issue as quickly as possible.

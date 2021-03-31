![CrowdStrike Falcon](https://raw.githubusercontent.com/CrowdStrike/falconpy/main/docs/asset/cs-logo.png) [![Twitter URL](https://img.shields.io/twitter/url?label=Follow%20%40CrowdStrike&style=social&url=https%3A%2F%2Ftwitter.com%2FCrowdStrike)](https://twitter.com/CrowdStrike)<br/>

# CrowdStrike Horizon Benchmark Utilities
These utilities have been developed to assist you in calculating the overall size of a cloud deployment.

## Running an audit
+ Connect to Cloud Shell within the provider in question
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
- Downloaded audit scripts are developed using Python 3.
- Audit scripts are removed after the process completes.
- As part of the audit, necessary dependencies are installed based upon cloud provider.

## License
These scripts are provided to the community, for free, under the Unlicense license. As such, these scripts
carry no formal support, express or implied.

## Questions?
Please review our [Code of Conduct](CODE_OF_CONDUCT.md) and then submit an issue or pull request.
We will address the issue as quickly as possible.
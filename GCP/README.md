# Cloud-Benchmark - GCP

This script is a read-only utility that counts cloud resources in your GCP account. It will autodiscover all GCP projects.

No changes will be made to your account. No data will be sent anywhere and will remain in your cloud shell environment.

## How to use

### Initialize execution environment

[![Open GCP Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://shell.cloud.google.com/cloudshell/editor?cloudshell_git_repo=https%3A%2F%2Fgithub.com%2FCrowdStrike%2FCloud-Benchmark)

### Run the script

   ```
   ./benchmark.sh
   ```

(Alternatively, if you happen to be frequent cloud user and have `gcloud` utility installed locally, you can run the below step locally instead of using cloud shell). In that case, you can use short cut: `curl https://raw.githubusercontent.com/CrowdStrike/Cloud-Benchmark/main/benchmark.sh | /bin/bash`

### Collect the findings

```
cat ./cloud-benchmark/*benchmark.csv
```

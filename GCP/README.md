# Cloud-Benchmark - GCP

This script is a read-only utility that counts cloud resources in your GCP account. It will autodiscover all GCP projects.

No changes will be made to your account. No data will be sent anywhere and will remain in your cloud shell environment.

## How to use

### Initialize execution environment

[![Open GCP Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://shell.cloud.google.com/cloudshell/editor?cloudshell_git_repo=https%3A%2F%2Fgithub.com%2FCrowdStrike%2Fcloud-resource-estimator)

### Run the script

```shell
./benchmark.sh
```

## Project Filtering

The GCP script automatically excludes Google system projects (`sys-*`) by default for better performance. These system projects typically don't contain billable resources relevant for CSPM benchmarking.

### Filtering Environment Variables

**System Projects:**

```bash
# Include Google system projects (default: false)
export GCP_INCLUDE_SYSTEM_PROJECTS=true
./benchmark.sh gcp
```

**Pattern-Based Filtering:**

```bash
# Only scan projects matching these patterns (allowlist)
export GCP_INCLUDE_PATTERNS="prod-*,production-*"
./benchmark.sh gcp

# Skip projects matching these patterns (denylist)
export GCP_EXCLUDE_PATTERNS="dev-*,test-*,*-sandbox,tmp-*"
./benchmark.sh gcp

# Combine multiple filters
export GCP_EXCLUDE_PATTERNS="dev-*,test-*"
export GCP_INCLUDE_SYSTEM_PROJECTS=false
./benchmark.sh gcp
```

### Common Filtering Examples

**Production Only:**

```bash
export GCP_INCLUDE_PATTERNS="prod-*,production-*,*-prod"
```

**Skip Development/Test:**

```bash
export GCP_EXCLUDE_PATTERNS="dev-*,test-*,staging-*,*-dev,*-test,*-stage"
```

**Skip Personal/Temporary Projects:**

```bash
export GCP_EXCLUDE_PATTERNS="tmp-*,temp-*,*-tmp,poc-*,experiment-*"
```

### Collect the findings

```shell
cat ./cloud-benchmark/*benchmark.csv
```

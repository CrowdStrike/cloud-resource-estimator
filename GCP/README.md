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

## Performance Configuration

The GCP script supports parallel processing and configurable performance settings for faster execution:

### Performance Environment Variables

**Threading & Batching:**

```bash
# Number of concurrent project processors (default: 3, recommended: 3-5)
export GCP_THREADS=3

# Projects per batch (default: 20)
export GCP_BATCH_SIZE=20

# Delay between batches in seconds (default: 10)
export GCP_BATCH_DELAY=10

# Delay between API calls in seconds (default: 0.05)
export GCP_API_DELAY=0.05
```

### Performance Examples

**Fast Processing (for smaller organizations):**

```bash
export GCP_THREADS=5
export GCP_API_DELAY=0.01
export GCP_BATCH_DELAY=5
./benchmark.sh gcp
```

**Rate-Limited Processing (for large organizations):**

```bash
export GCP_THREADS=3
export GCP_API_DELAY=0.1
export GCP_BATCH_DELAY=15
./benchmark.sh gcp
```

**Maximum Performance (use with caution):**

```bash
export GCP_THREADS=5
export GCP_API_DELAY=0
export GCP_BATCH_DELAY=0
./benchmark.sh gcp
```

> [!WARNING]
> Setting `GCP_API_DELAY=0` and `GCP_BATCH_DELAY=0` may trigger Google Cloud's rate limiting mechanisms, especially in organizations with many projects. If you encounter rate limit errors, increase these values. Start with conservative settings and adjust based on your organization's API quota limits.

### Rate Limiting Considerations

Google Cloud APIs have quotas and rate limits that vary by service and organization. When scanning large numbers of projects:

- **Start Conservative**: Use default settings first (`GCP_THREADS=3`, `GCP_API_DELAY=0.05`)
- **Monitor for Errors**: Watch for "quota exceeded" or "rate limit exceeded" errors in the output
- **Adjust Gradually**: If you encounter rate limits, increase `GCP_API_DELAY` and `GCP_BATCH_DELAY` values
- **Organization Size Matters**: Larger organizations should use more conservative settings

**Recommended Settings by Organization Size:**

- **Small** (< 50 projects): Default settings work well
- **Medium** (50-200 projects): `GCP_THREADS=3`, `GCP_API_DELAY=0.1`
- **Large** (200+ projects): `GCP_THREADS=3`, `GCP_API_DELAY=0.15`, `GCP_BATCH_DELAY=15`

### Collect the findings

```shell
cat ./cloud-benchmark/*benchmark.csv
```

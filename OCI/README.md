# OCI Cloud Resource Estimator

This guide explains how to run the OCI CSPM benchmark script to count billable resources in your Oracle Cloud Infrastructure tenancy.

## What it counts

| Resource | OCI Service |
|---|---|
| Running VMs | OCI Compute — `RUNNING` instances |
| Stopped VMs | OCI Compute — `STOPPED` instances |
| OKE Clusters | Container Engine for Kubernetes — active clusters |
| OKE Managed Nodes | OKE managed node pool sizes |
| OKE Virtual Nodes | OKE virtual (serverless) node pool sizes |
| Container Instances | OCI Container Instances — active containers |
| Functions | OCI Functions — active functions across all applications |
| Autonomous Databases | Oracle Autonomous Database — all workload types |
| MySQL DB Systems | MySQL HeatWave Database Service |
| Object Storage Buckets | OCI Object Storage — per compartment |

## Prerequisites

- Python 3
- pip
- [OCI CLI](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm) — `oci` command must be in PATH

### Install the OCI CLI

```shell
bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"
```

### Configure credentials

```shell
oci setup config
```

This creates `~/.oci/config` and generates an API key pair. Upload the public key to your OCI user's API keys in the Console.

Verify authentication:

```shell
oci iam region list
```

## IAM Policy (least-privilege)

Create an IAM group (e.g. `CrowdStrikeEstimatorGroup`) and attach the following policy at the tenancy level:

```
Allow group CrowdStrikeEstimatorGroup to inspect compartments in tenancy
Allow group CrowdStrikeEstimatorGroup to inspect instances in tenancy
Allow group CrowdStrikeEstimatorGroup to inspect cluster-family in tenancy
Allow group CrowdStrikeEstimatorGroup to inspect container-instances in tenancy
Allow group CrowdStrikeEstimatorGroup to inspect fn-app in tenancy
Allow group CrowdStrikeEstimatorGroup to inspect fn-function in tenancy
Allow group CrowdStrikeEstimatorGroup to inspect autonomous-databases in tenancy
Allow group CrowdStrikeEstimatorGroup to inspect mysql-instances in tenancy
Allow group CrowdStrikeEstimatorGroup to inspect buckets in tenancy
Allow group CrowdStrikeEstimatorGroup to read region-subscriptions in tenancy
```

### Using Instance Principal (running on OCI Compute)

Create a Dynamic Group matching your scanner instance:

```
All {instance.compartment.id = 'ocid1.compartment.oc1..<scanner-compartment>'}
```

Then apply the same `inspect` / `read` policies to that Dynamic Group instead of a user group.

## Running in OCI Cloud Shell

OCI Cloud Shell has the OCI CLI pre-installed and is automatically authenticated via Instance Principal.

```shell
RELEASE_VERSION="v1.0.0"
curl -sLO "https://github.com/CrowdStrike/cloud-resource-estimator/releases/download/${RELEASE_VERSION}/benchmark.sh"
curl -sL "https://github.com/CrowdStrike/cloud-resource-estimator/releases/download/${RELEASE_VERSION}/checksum.txt" \
  | grep benchmark.sh | sha256sum -c
chmod +x benchmark.sh
./benchmark.sh oci
```

## Running locally

```shell
./benchmark.sh oci
```

Or scan multiple providers at once:

```shell
./benchmark.sh aws oci
```

## Configuration

All options can be set via environment variables before running the script.

| Variable | Default | Description |
|---|---|---|
| `OCI_PROFILE` | `DEFAULT` | OCI config file profile name |
| `OCI_TENANCY_OCID` | from config | Override tenancy OCID |
| `OCI_REGIONS` | all subscribed | Comma-separated regions to scan |
| `OCI_SKIP_COMPARTMENTS` | none | Comma-separated compartment OCIDs to exclude |
| `OCI_INCLUDE_COMPARTMENTS` | all | Comma-separated compartment OCIDs to scan exclusively |
| `OCI_THREADS` | `5` | Parallel scan workers |
| `OCI_API_DELAY` | `0.05` | Seconds between API calls |
| `OCI_MAX_RETRIES` | `5` | Retry attempts per failed operation |
| `OCI_RESUME_FILE` | `oci_benchmark_progress.json` | Progress tracking file for resume support |
| `OCI_DRY_RUN` | `false` | Set to `true` to simulate without API calls |

**Important:** `OCI_INCLUDE_COMPARTMENTS` takes full precedence — if set, `OCI_SKIP_COMPARTMENTS` is ignored.

### Resuming an interrupted scan

If the scan is interrupted (Ctrl+C or SIGTERM), partial results are written to the CSV and progress is saved to `OCI_RESUME_FILE`. Re-running the same command resumes from where it left off — already-completed `(compartment, region)` pairs are skipped automatically.

The progress file is deleted automatically on a fully successful run. To force a fresh scan, delete it manually or set `OCI_RESUME_FILE` to a new path.

### Example: scan only specific compartments

```shell
export OCI_INCLUDE_COMPARTMENTS="ocid1.compartment.oc1..aaaa...,ocid1.compartment.oc1..bbbb..."
./benchmark.sh oci
```

### Example: scan specific regions only

```shell
export OCI_REGIONS="us-ashburn-1,us-phoenix-1"
./benchmark.sh oci
```

### Example: large tenancies (many compartments and regions)

```shell
export OCI_THREADS=10
export OCI_API_DELAY=0.1
./benchmark.sh oci
```

## Output

The script writes a timestamped CSV file:

```
./cloud-benchmark/oci-benchmark-YYYYMMDD_HHMMSS.csv
```

Results are also printed to the terminal as a grid table.

To view the output:

```shell
cat ./cloud-benchmark/oci-benchmark-*.csv
```

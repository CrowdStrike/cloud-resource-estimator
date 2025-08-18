#!/bin/bash
# Universal cloud provider provisioning calculator
# Based on the cloud provider, downloads the necessary scripts
# to perform a sizing calculation.

base_url=https://raw.githubusercontent.com/CrowdStrike/Cloud-Benchmark/main

# Usage message
usage() {
    echo """
    Usage: $0 [OPTIONS] [aws|azure|gcp]...

    The script recognizes the following environment variables:

    AWS:
        - AWS_ASSUME_ROLE_NAME: The name of the AWS role to assume (optional)
        - AWS_REGIONS: The name of the AWS Region to target or a comma-delimited list of AWS Regions to target (optional)
        - AWS_THREADS: Number of worker threads for parallel processing (default: 5)
        - AWS_BATCH_SIZE: Number of accounts to process per batch (default: 20)
        - AWS_BATCH_DELAY: Delay in seconds between batches (default: 30)
        - AWS_API_DELAY: Delay in seconds between API calls (default: 0.1)
        - AWS_MAX_RETRIES: Maximum retry attempts for failed operations (default: 5)
        - AWS_OPERATION_TIMEOUT: Timeout in seconds for individual operations (default: 300)
        - AWS_RESUME_FILE: File to store/resume progress (default: aws_benchmark_progress.json)
        - AWS_SKIP_ACCOUNTS: Comma-separated list of account IDs to skip
        - AWS_DRY_RUN: Set to 'true' to show what would be processed without making API calls
        
        Example for large organizations (200+ accounts):
        export AWS_THREADS=3
        export AWS_BATCH_SIZE=12
        export AWS_BATCH_DELAY=45
        export AWS_API_DELAY=0.15
        """
}

# Check if the system has Python3 and pip installed
check_python3() {
    if ! type python3 >/dev/null 2>&1; then
        echo "Python3 not found. Please install Python3 and try again."
        exit 1
    fi
    if ! type pip3 >/dev/null 2>&1; then
        echo "Pip not found. Please install pip and try again."
        exit 1
    fi
}

# Ensures the provided cloud provider arg is valid
is_valid_cloud() {
    local cloud="$1"
    local lower_cloud
    lower_cloud=$(echo "$cloud" | tr '[:upper:]' '[:lower:]')

    case "$lower_cloud" in
    aws)
        echo "AWS"
        return 0
        ;;
    azure)
        echo "Azure"
        return 0
        ;;
    gcp)
        echo "GCP"
        return 0
        ;;
    *)
        return 1
        ;;
    esac
}

# Calls the python script for the specified cloud provider with the
# appropriate arguments
call_benchmark_script() {
    local cloud="$1"
    local file="$2"
    local args=()

    case "$cloud" in
    AWS)
        [[ -n $AWS_ASSUME_ROLE_NAME ]] && args+=("-r" "$AWS_ASSUME_ROLE_NAME")
        [[ -n $AWS_REGIONS ]] && args+=("-R" "$AWS_REGIONS")
        [[ -n $AWS_THREADS ]] && args+=("--threads" "$AWS_THREADS")
        [[ -n $AWS_BATCH_SIZE ]] && args+=("--batch-size" "$AWS_BATCH_SIZE")
        [[ -n $AWS_BATCH_DELAY ]] && args+=("--batch-delay" "$AWS_BATCH_DELAY")
        [[ -n $AWS_API_DELAY ]] && args+=("--api-delay" "$AWS_API_DELAY")
        [[ -n $AWS_MAX_RETRIES ]] && args+=("--max-retries" "$AWS_MAX_RETRIES")
        [[ -n $AWS_OPERATION_TIMEOUT ]] && args+=("--operation-timeout" "$AWS_OPERATION_TIMEOUT")
        [[ -n $AWS_RESUME_FILE ]] && args+=("--resume-file" "$AWS_RESUME_FILE")
        [[ -n $AWS_SKIP_ACCOUNTS ]] && args+=("--skip-accounts" "$AWS_SKIP_ACCOUNTS")
        [[ -n $AWS_DRY_RUN ]] && [[ $AWS_DRY_RUN == "true" ]] && args+=("--dry-run")
        ;;
    Azure)
        ;;
    GCP)
        ;;
    *)
        echo "Invalid cloud provider specified: $cloud"
        usage
        exit 1
        ;;
    esac

    python3 "${file}" "${args[@]}"
}

audit() {
    CLOUD="$1"
    echo "Working in cloud: ${CLOUD}"
    cloud=$(echo "$CLOUD" | tr '[:upper:]' '[:lower:]')

    case "$CLOUD" in
    AWS)
        # Use local AWS script if available
        if [ -f "../AWS/aws_cspm_benchmark.py" ]; then
            echo "Using local AWS CSPM benchmark script..."
            file="../AWS/aws_cspm_benchmark.py"
            
            # Install requirements from local AWS directory
            if [ -f "../AWS/requirements.txt" ]; then
                python3 -m pip install --disable-pip-version-check -qq -r "../AWS/requirements.txt"
            else
                echo "AWS requirements.txt not found locally, downloading from remote"
                curl -s -o requirements.txt "${base_url}/${CLOUD}/requirements.txt"
                python3 -m pip install --disable-pip-version-check -qq -r requirements.txt
            fi
        else
            echo "Local AWS script not found, downloading from remote"
            curl -s -o requirements.txt "${base_url}/${CLOUD}/requirements.txt"
            echo "Installing python dependencies for communicating with ${CLOUD} into (~/cloud-benchmark)"
            python3 -m pip install --disable-pip-version-check -qq -r requirements.txt
            file="${cloud}_cspm_benchmark.py"
            curl -s -o "${file}" "${base_url}/${CLOUD}/${file}"
        fi
        ;;
    Azure|GCP)
        # Use remote scripts for Azure and GCP (unchanged behavior)
        curl -s -o requirements.txt "${base_url}/${CLOUD}/requirements.txt"
        echo "Installing python dependencies for communicating with ${CLOUD} into (~/cloud-benchmark)"
        python3 -m pip install --disable-pip-version-check -qq -r requirements.txt
        file="${cloud}_cspm_benchmark.py"
        curl -s -o "${file}" "${base_url}/${CLOUD}/${file}"
        ;;
    *)
        echo "Unsupported cloud provider: $CLOUD"
        exit 1
        ;;
    esac

    call_benchmark_script "$CLOUD" "${file}"
}

check_python3

python3 -m venv ./cloud-benchmark
pushd ./cloud-benchmark >/dev/null || exit
# shellcheck source=/dev/null
source ./bin/activate

# MAIN ROUTINE
found_provider=false

# If arguments are provided, audit the specified providers
for arg in "$@"; do
    result=$(is_valid_cloud "$arg")
    # shellcheck disable=SC2181
    if [ $? -eq 0 ]; then
        audit "$result"
        found_provider=true
    else
        echo "Invalid cloud provider specified: $arg"
        # Exit only if found_provider is false. This means that if the user
        # specifies a valid cloud provider, but also an invalid one, we will
        # still run the audit for the valid provider.
        if [ "$found_provider" = false ]; then
            usage
            popd >/dev/null && exit 1
        fi
    fi
done

# If no arguments provided, auto-detect the available cloud providers
if [ $# -eq 0 ]; then
    echo "Determining cloud provider..."
    if type aws >/dev/null 2>&1; then
        audit "AWS"
        found_provider=true
    fi
    if type az >/dev/null 2>&1; then
        audit "Azure"
        found_provider=true
    fi

    if type gcloud >/dev/null 2>&1; then
        audit "GCP"
        found_provider=true
    fi
fi

if [ "$found_provider" = false ]; then
    echo "No supported cloud provider found."
    usage
    popd >/dev/null && exit 1
fi

popd >/dev/null || exit
deactivate

echo "Type following command to export cloud counts:"
echo "cat ./cloud-benchmark/*benchmark.csv"

# END
#
#       -''--.
#       _`>   `\.-'<
#    _.'     _     '._
#  .'   _.='   '=._   '.
#  >_   / /_\ /_\ \   _<    - jgs
#    / (  \o/\\o/  ) \
#    >._\ .-,_)-. /_.<
#       /__/ \__\
#          '---'     E=mc^2
#
#

#!/bin/bash
# Universal cloud provider provisioning calculator
# Identifies the current cloud provider, then downloads the necessary scripts
# to perform a sizing calculation.
#

base_url=https://raw.githubusercontent.com/CrowdStrike/Cloud-Benchmark/main

# Usage message
usage() {
    echo """
    Usage: $0 [AWS|Azure|GCP]...

    More than one cloud provider can be specified.
    If no cloud provider is specified, the script will attempt to detect the provider."""
}

# Check if the system has Python3 and pip installed
check_python3() {
    if ! type python3 >/dev/null 2>&1; then
        echo "Python3 not found. Please install Python3 and try again."
        exit 1
    fi
    if ! type pip >/dev/null 2>&1; then
        echo "Pip not found. Please install pip and try again."
        exit 1
    fi
}

is_valid_cloud() {
    local cloud="$1"
    local lower_cloud=$(echo "$cloud" | tr '[:upper:]' '[:lower:]')

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

audit() {
    CLOUD="$1"
    echo "Working in cloud: ${CLOUD}"
    cloud=$(echo "$CLOUD" | tr '[:upper:]' '[:lower:]')

    # curl -s -o requirements.txt "${base_url}/${CLOUD}/requirements.txt"
    cp "../${CLOUD}/requirements.txt" .
    echo "Installing python dependencies for communicating with ${CLOUD} into (~/cloud-benchmark)"

    python3 -m pip install --disable-pip-version-check -qq -r requirements.txt
    file="${cloud}_cspm_benchmark.py"
    # curl -s -o "${file}" "${base_url}/${CLOUD}/${file}"
    cp "../${CLOUD}/${file}" .
    python3 "${file}"
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

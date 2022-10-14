#!/bin/bash
# Universal cloud provider provisioning calculator
# Identifies the current cloud provider, then downloads the necessary scripts
# to perform a sizing calculation.
#
# Creation date: 03.25.21, Joshua Hiller @ CrowdStrike
#

base_url=https://raw.githubusercontent.com/CrowdStrike/Cloud-Benchmark/main

audit(){
    CLOUD="$1"
    echo "This is ${CLOUD}"
    cloud=$(echo "$CLOUD" | tr '[:upper:]' '[:lower:]')

    curl -s -o requirements.txt "${base_url}/${CLOUD}/requirements.txt"
    echo "Installing python dependencies for communicating with ${CLOUD} into (~/cloud-benchmark)"

    python3 -m pip install --disable-pip-version-check -qq -r requirements.txt
    file="${cloud}_cspm_benchmark.py"
    curl -s -o "${file}" "${base_url}/${CLOUD}/${file}"
    python3 "${file}"
}

python3 -m venv ./cloud-benchmark
pushd ./cloud-benchmark || exit
# shellcheck source=/dev/null
source ./bin/activate

# MAIN ROUTINE
echo "Determining cloud provider"
if type aws >/dev/null 2>&1; then
    audit "AWS"
fi
if type az >/dev/null 2>&1; then
    audit Azure
fi

if type gcloud >/dev/null 2>&1; then
    audit GCP
fi

popd || exit
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

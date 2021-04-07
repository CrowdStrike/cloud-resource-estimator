#!/bin/bash
# Universal cloud provider provisioning calculator
# Identifies the current cloud provider, then downloads the necessary scripts
# to perform a sizing calculation.
# 
# Creation date: 03.25.21, Joshua Hiller @ CrowdStrike
#

audit_AWS(){
  # AWS audit
  curl -o aws_count.py https://raw.githubusercontent.com/CrowdStrike/Cloud-Benchmark/main/AWS/aws_cspm_benchmark.py
  pip3 install --user tabulate
  python3 aws_count.py
  rm aws_count.py
}

audit_Azure(){
  # Azure audit
  curl -o azure_count.py https://raw.githubusercontent.com/CrowdStrike/Cloud-Benchmark/main/Azure/azure_cspm_benchmark.py
  python3 -m pip install azure-mgmt-resource azure-identity  # azure-mgmt-subscription
  python3 azure_count.py
  rm azure_count.py
}

audit_GCP(){
  # GCP audit
  curl https://raw.githubusercontent.com/CrowdStrike/Cloud-Benchmark/main/GCP/gcp-cspm-benchmark.sh | /bin/bash
}

# MAIN ROUTINE
echo "Determining cloud provider"
if type aws >/dev/null 2>&1; then
  echo "This is AWS"
  audit_AWS
fi

if type az >/dev/null 2>&1; then
  echo "This is Azure"
  audit_Azure
fi

if type gcloud >/dev/null 2>&1; then
  echo "This is GCP"
  audit_GCP
fi

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

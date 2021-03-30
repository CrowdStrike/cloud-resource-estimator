#!/bin/bash
# Universal cloud provider provisioning calculator
# Identifies the current cloud provider, then downloads the necessary scripts
# to perform a sizing calculation.
# 
# Creation date: 03.25.21, Joshua Hiller @ CrowdStrike
#

audit_AWS(){
  # AWS audit
  curl -o aws_count.py https://raw.githubusercontent.com/CrowdStrike/Cloud-Benchmark/main/AWS/aws-cspm-benchmark.py
  pip3 install --user tabulate
  python3 aws_count.py
  rm aws_count.py
}

audit_Azure(){
  # Azure audit
  curl -o azure_count.py https://raw.githubusercontent.com/CrowdStrike/Cloud-Benchmark/main/Azure/azure-cspm-benchmark.py
  python3 -m pip install azure-mgmt-resource azure-identity
  python3 azure_count.py
  rm azure_count.py
}

audit_GCP(){
  # GCP audit
  echo "Not yet implemented"
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
#                      .--------------.
#                 .---'  o        .    `---.
#              .-'    .    O  .         .   `-.
#           .-'     @@@@@@       .             `-.
#         .'@@   @@@@@@@@@@@       @@@@@@@   .    `.
#       .'@@@  @@@@@@@@@@@@@@     @@@@@@@@@         `.
#      /@@@  o @@@@@@@@@@@@@@     @@@@@@@@@     O     \
#     /        @@@@@@@@@@@@@@  @   @@@@@@@@@ @@     .  \
#    /@  o      @@@@@@@@@@@   .  @@  @@@@@@@@@@@     @@ \
#   /@@@      .   @@@@@@ o       @  @@@@@@@@@@@@@ o @@@@ \
#  /@@@@@                  @ .      @@@@@@@@@@@@@@  @@@@@ \
#  |@@@@@    O    `.-./  .        .  @@@@@@@@@@@@@   @@@  |
# / @@@@@        --`-'       o        @@@@@@@@@@@ @@@    . \
# |@ @@@@ .  @  @    `    @            @@      . @@@@@@    |
# |   @@                         o    @@   .     @@@@@@    |
# |  .     @   @ @       o              @@   o   @@@@@@.   |
# \     @    @       @       .-.       @@@@       @@@      /
#  |  @    @  @              `-'     . @@@@     .    .    |
#  \ .  o       @  @@@@  .              @@  .           . /
#   \      @@@    @@@@@@       .                   o     /
#    \    @@@@@   @@\@@    /        O          .        /
#     \ o  @@@       \ \  /  __        .   .     .--.  /
#      \      .     . \.-.---                   `--'  /
#       `.             `-'      .                   .'
#         `.    o     / | `           O     .     .'
#           `-.      /  |        o             .-'
#              `-.          .         .     .-'
#                 `---.        .       .---'
#                      `--------------'

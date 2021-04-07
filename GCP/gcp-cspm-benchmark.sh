#!/bin/bash
# gcp-cspm-benchmark.sh

# Assists with provisioning calculations by retrieving a count
# of all billable resources attached to a GCP subscription.

# Creation date: 03.27.21, Joshua Hiller @ CrowdStrike

projects=($(gcloud projects list --format json | jq  -r '.[].projectId'))
for i in "${projects[@]}"
do
    echo "|== Project $i"
    total_count=0
    # GCP instances
    chk=$(gcloud compute instances list --project $i -q >/dev/null 2>&1)
    compute_api=$?
    if [[ "$compute_api" == 0 ]]
    then
      count=$(gcloud compute instances list --project $i -q --format json 2> /dev/null | jq '.[].name'  | wc -l)
      count_hdr=$count
    else
      count=0
      count_hdr="API disabled"
    fi
    echo "    Total compute instances: $count_hdr"
    total_count=$(( $total_count + $count ))
    if [[ "$compute_api" == 0 ]]
    then
      # Load balancer forwarding rules
      count=$(gcloud compute forwarding-rules list --project $i -q --format json 2> /dev/null | jq '.[].id' | wc -l)
      count_hdr=$count
    else
      count=0
      count_hdr="API disabled"
    fi
    echo "    Total load balancer forwarding rules: $count_hdr"
    total_count=$(( $total_count + $count ))
    if [[ "$compute_api" == 0 ]]
    then
      nat_count=0
      routers=($(gcloud compute routers list --project $i -q --format json 2> /dev/null | jq  -r '.[] | "\(.name);\(.region)"'))
      for j in "${routers[@]}"
      do
          name=$(cut -d ';' -f 1 <<< "$j")
          region=${j##*/}
          count=$(gcloud compute routers nats list --project $i -q --region $region --router $name --format json 2> /dev/null | jq -r '.[].name' | wc -l)
          nat_count=$(( $nat_count + $count ))
      done
      nat_count_hdr=$nat_count
    else
      nat_count=0
      nat_count_hdr="API disabled"
    fi
    echo "    Total Cloud NAT: $nat_count_hdr"
    total_count=$(( $total_count + $nat_count ))
    chk=$(gcloud sql instances list --project $i -q >/dev/null 2>&1)
    sql_api=$?
    if [[ "$sql_api" == 0 ]]
    then
      # Cloud SQL
      count=$(gcloud sql instances list --project $i -q --format json 2> /dev/null | jq '.[].name'  | wc -l)
      count_hdr=$count
    else
      count=0
      count_hdr="API disabled"
    fi
    echo "    Total Cloud SQL instances: $count_hdr"
    total_count=$(( $total_count + $count ))
    chk=$(gcloud spanner instances list --project $i -q >/dev/null 2>&1)
    spanner_api=$?
    if [[ "$spanner_api" == 0 ]]
    then
      # Cloud Spanner
      count=$(gcloud spanner instances list --project $i -q --format json 2> /dev/null | jq '.[].name'  | wc -l)
      count_hdr=$count
    else
      count=0
      count_hdr="API disabled"
    fi
    echo "    Total Cloud Spanner instances: $count_hdr"
    total_count=$(( $total_count + $count ))
    echo -e "\n    Total resource count: $total_count \n\n"
done
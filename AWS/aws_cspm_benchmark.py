"""
aws-cspm-benchmark.py

Assists with provisioning calculations by retrieving a count of
all billable resources attached to an AWS account.

Author: Joshua Hiller @ CrowdStrike
Creation date: 03.23.21
"""
import csv
from functools import cached_property
import boto3
from tabulate import tabulate


def process(reg: str, svc: list) -> dict:
    """ Query a particular AWS service and return the
        resulting output back as a JSON dictionary (sorta).
    """
    # TODO: Implement paging for large resultsets       pylint: disable=W0511
    _ = boto3.client(svc[0], region_name=reg)
    delim = "=" if svc[3] else ""
    ec2_filter = ""
    if svc[3] == "describe_instances":
        ec2_filter = "Filters=[{'Name': 'instance-state-name', 'Values': ['terminated']}]"
    return eval(f"_.{svc[2]}({svc[3]}{delim}{svc[4]}{ec2_filter})")  # nosec   pylint: disable=W0123


aws_account = {}
aws_account["totals"] = {}
checks = [
    ["ec2", "Reservations", "describe_instances", "MaxResults", "1000", "ec2"],
    ["ecs", "clusterArns", "list_clusters", "", "", "ecs"],
    ["eks", "clusters", "list_clusters", "", "", "eks"]
]
data = []
headers = {
            "region": "Region",
            "ec2": "EC2",
            "ecs": "ECS - Clusters",
            "eks": "EKS - Clusters"
}
totals = {
            "region": "TOTAL",
            "ec2": 0,
            "ecs": 0,
            "eks": 0
}


class AWSHandle:
    @property
    def regions(self):
        return self.ec2.describe_regions()['Regions']

    @cached_property
    def ec2(self):
        return boto3.client("ec2")


aws = AWSHandle()

GRAND_TOTAL_RESOURCES = 0
for region in aws.regions:
    RegionName = region["RegionName"]

    # Setup the branch
    print(f"Processing {RegionName}")
    aws_account[RegionName] = {}
    aws_account["totals"][RegionName] = {}
    # Create the row for our output table
    row = {}
    row["region"] = RegionName
    for service in checks:
        # Process each service, adding the results to the aws_account object
        aws_account[RegionName][service[5]] = process(RegionName, service)
        # Calculate the number of elements found and throw it in the totals branch
        aws_account["totals"][RegionName][service[5]] = len(aws_account[RegionName][service[5]][service[1]])

        totals[service[5]] += aws_account["totals"][RegionName][service[5]]

        # Update the row with this service's totals
        row.update(aws_account["totals"][RegionName])
    # Add the row to our display table
    data.append(row)
# Add in our grand totals to the display table
data.append(totals)
# Create GRAND_TOTAL_RESOURCE count for quoting
for key, val in totals.items():
    if val != 'TOTAL':
        GRAND_TOTAL_RESOURCES += val

# Output our results
print(tabulate(data, headers=headers, tablefmt="grid"))
# Output GRAND_TOTAL_RESOURCE
print(f"\nTotal billable resources discovered across all regions: {GRAND_TOTAL_RESOURCES}\n\n")

with open('benchmark.csv', 'w', newline='', encoding='utf-8') as csv_file:
    csv_writer = csv.DictWriter(csv_file, fieldnames=headers.keys())
    csv_writer.writeheader()
    csv_writer.writerows(data)

print("\nCSV file stored in: ./benchmark.csv\n\n")


#     .wwwwwwww.
#   .w"  "WW"  "w.
#  ."   /\  /\   ".
# |\     o  o     /|
#  \|  ___\/___  |/
#  / \ \_v__v_/ / \
# / | \________/ | \
# >  \   WWWW   /  <
# \   \   ""   /   /
#  \   \      /   /
#  The Count says...
#
#  That's ONE server, TWO servers  ... AH AH AH!

"""
aws-cspm-benchmark.py

Assists with provisioning calculations by retrieving a count of
all billable resources attached to an AWS account.

Author: Joshua Hiller @ CrowdStrike
Creation date: 03.23.21
"""
import csv
import boto3                    # pylint: disable=E0401
from tabulate import tabulate   # pylint: disable=E0401


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
filtered = []
# filtered = ["us-west-2"]
include = ["all"]
# include = ["eu-west-2", "us-east-2", "us-west-1", "ap-southeast-2"]
checks = [
    ["ec2", "Reservations", "describe_instances", "MaxResults", "1000", "ec2"],
    ["rds", "DBInstances", "describe_db_instances", "MaxRecords", "100", "rds"],
    ["redshift", "Clusters", "describe_clusters", "MaxRecords", "100", "redshift"],
    ["elbv2", "LoadBalancers", "describe_load_balancers", "PageSize", "400", "lb"],
    ["ec2", "NatGateways", "describe_nat_gateways", "MaxResults", "1000", "natg"],
    ["ecs", "clusterArns", "list_clusters", "", "", "ecs"],
    ["eks", "clusters", "list_clusters", "", "", "eks"]
]
data = []
headers = {
            "region": "Region",
            "ec2": "EC2",
            "rds": "RDS",
            "redshift": "Redshift",
            "lb": "ALB/ELB",
            "natg": "NAT",
            "ecs": "ECS - Clusters",
            "eks": "EKS - Clusters"
}
totals = {
            "region": "TOTAL",
            "ec2": 0,
            "rds": 0,
            "redshift": 0,
            "lb": 0,
            "natg": 0,
            "ecs": 0,
            "eks": 0
}
GRAND_TOTAL_RESOURCES = 0
ec2 = boto3.client("ec2")
response = ec2.describe_regions()
for region in response["Regions"]:
    RegionName = region["RegionName"]
    if RegionName not in filtered:
        if RegionName in include or "all" in include:
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
                if service[5] not in ["iam"]:
                    # Increment the number of elements found for the service in our grand total
                    totals[service[5]] += aws_account["totals"][RegionName][service[5]]
                else:
                    # IAM roles are not region-specific, so just overwrite the previous value (it'll be the same)
                    totals[service[5]] = aws_account["totals"][RegionName][service[5]]
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

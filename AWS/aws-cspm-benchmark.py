"""
aws-cspm-benchmark.py

Assists with provisioning calculations by retrieving a count of
all billable resources attached to an AWS account.

Author: Joshua Hiller
Creation date: 03.23.21
"""
import boto3
import ast
from tabulate import tabulate


def process(region: str, service: list) -> dict:
    """ Query a particular AWS service and return the
        resulting output back as a JSON dictionary (sorta).
    """
    # TODO: Implement paging for large resultsets
    _ = boto3.client(service[0], region_name=region)
    delim = "=" if service[3] else ""
    return ast.literal_eval(f"_.{service[2]}({service[3]}{delim}{service[4]})")


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
    ["ecs", "clusters", "describe_clusters", "", "", "ecs"],
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

# Output our results
print(tabulate(data, headers=headers, tablefmt="grid"))

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

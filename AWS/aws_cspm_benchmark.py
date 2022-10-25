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
    return eval(f"_.{svc[2]}({svc[3]}{delim}{svc[4]}{ec2_filter})")  # nosec   pylint: disable=W0123


aws_account = {}
aws_account["totals"] = {}
checks = [
    ["ecs", "clusterArns", "list_clusters", "", "", "ecs"],
]
data = []
headers = {
            "region": "Region",
            "ecs": "ECS - Clusters",
            "vms_terminated": "Terminated VMs",
            "vms_running": "Running VMs",
            'kubenodes_terminated': "Terminated Kubernetes Nodes",
            'kubenodes_running': "Running Kubernetes Nodes"
}
totals = {
            "region": "TOTAL",
            "ecs": 0,
            "vms_terminated": 0,
            "vms_running": 0,
            'kubenodes_terminated': 0,
            'kubenodes_running': 0
}


class AWSHandle:
    EKS_TAGS = ['eks:cluster-name', 'alpha.eksctl.io/nodegroup-type', 'aws:eks:cluster-name', 'eks:nodegroup-name']

    @property
    def regions(self):
        return self.ec2.describe_regions()['Regions']

    def ec2_instances(self, aws_region):
        client = boto3.client('ec2', aws_region)

        response = client.describe_instances(MaxResults=1000)
        instances = response['Reservations']
        next_token = response['NextToken'] if 'NextToken' in response else None

        while next_token:
            response = client.describe_instances(MaxResults=1000, NextToken=next_token)
            instances += response['Reservations']
            next_token = response['NextToken'] if 'NextToken' in response else None

        return instances

    @cached_property
    def ec2(self):
        return boto3.client("ec2")

    @classmethod
    def is_vm_kubenode(cls, instance):
        return any(True for tag in instance.get('Tags', []) if tag['Key'] in cls.EKS_TAGS)

    @classmethod
    def is_vm_running(cls, vm):
        return vm['State']['Name'] != 'stopped'


aws = AWSHandle()

for region in aws.regions:
    RegionName = region["RegionName"]

    # Setup the branch
    print(f"Processing {RegionName}")
    aws_account[RegionName] = {}
    aws_account["totals"][RegionName] = {}
    # Create the row for our output table
    row = {'region': RegionName, 'vms_terminated': 0, 'vms_running': 0,
           'kubenodes_terminated': 0, 'kubenodes_running': 0}
    for service in checks:
        # Process each service, adding the results to the aws_account object
        aws_account[RegionName][service[5]] = process(RegionName, service)
        # Calculate the number of elements found and throw it in the totals branch
        aws_account["totals"][RegionName][service[5]] = len(aws_account[RegionName][service[5]][service[1]])

        totals[service[5]] += aws_account["totals"][RegionName][service[5]]

        # Update the row with this service's totals
        row.update(aws_account["totals"][RegionName])

    # Count ec2 instances
    for reservation in aws.ec2_instances(RegionName):
        for instance in reservation['Instances']:
            typ = 'kubenode' if AWSHandle.is_vm_kubenode(instance) else 'vm'
            state = 'running' if AWSHandle.is_vm_running(instance) else 'terminated'
            key = f"{typ}s_{state}"
            row[key] += 1

    for k in ['vms_terminated', 'vms_running', 'kubenodes_terminated', 'kubenodes_running']:
        totals[k] += row[k]

    # Add the row to our display table
    data.append(row)
# Add in our grand totals to the display table
data.append(totals)

# Output our results
print(tabulate(data, headers=headers, tablefmt="grid"))

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

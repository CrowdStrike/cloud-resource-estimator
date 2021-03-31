"""
azure-cspm-benchmark.py

Assists with provisioning calculations by retrieving a count
of all billable resources attached to an Azure subscription.

Author: Joshua Hiller @ CrowdStrike
Creation date: 03.23.21
"""

import json
import subprocess
# Import the needed Azure credential and management objects from the Azure SDK.
from azure.identity import AzureCliCredential
from azure.mgmt.resource import ResourceManagementClient
#from azure.mgmt.subscription import SubscriptionClient

# Dictionary of billable resource types and their generic name
billable = {
    "Microsoft.Compute/virtualMachines": "Virtual Machines",
    "Microsoft.Network/applicationGateways": "Load Balancers",
    "Microsoft.Network/loadBalancers": "Load Balancers",
    "Microsoft.Sql/servers/databases": "SQL Server and databases",
    "Microsoft.Sql/servers": "SQL Server and databases",
}

# Acquire a credential object using CLI-based authentication.
credential = AzureCliCredential()

# Retrieve subscription ID from environment variable.
subscription_id = json.loads(subprocess.getoutput("az account show --query id"))
# subscription_id = SubscriptionClient(credential)

# Obtain the management object for resources.
resource_client = ResourceManagementClient(credential, subscription_id)

# Retrieve the list of resource groups
group_list = resource_client.resource_groups.list()

# Show the groups in formatted output
main_column_width = 40

# Output the column headers
print("\nResource Group".ljust(main_column_width) + " Location")

# Grand total of all resources discovered
grand_total_resources = 0

# Loop through every resource group identified
for group in list(group_list):
    # Running total of all resources found within the resource group
    total_resources = 0
    # Results dictionary
    results = {}
    # Output the resource group name and location
    print("-" * (main_column_width * 2))
    print(f"{group.name:<{main_column_width}}{group.location}")
    print("-" * (main_column_width * 2))

    # Retrieve the list of resources in the group.
    resource_list = resource_client.resources.list_by_resource_group(group.name)

    # Loop through the resources discovered and display the totals
    # for each billable resource type.
    for resource in list(resource_list):
        if resource.type in billable:
            total_resources += 1
            grand_total_resources += 1
            if billable[resource.type] in results:
                results[billable[resource.type]] += 1
            else:
                results[billable[resource.type]] = 1

    # Print the resource totals for all resources in this group
    for resource_type, total in sorted(results.items()):
        print("{} : {}".format(resource_type, total))

    # Print the totals for this resource group
    print("\nTotal billable resources: {} \n\n".format(total_resources))

# Print the grand totals for all resources discovered
print("\nTotal billable resources discovered across all resource groups: {}\n\n".format(grand_total_resources))

#             ,ggg,                   gg                   ,ggg,
#            d8P""8b                ,d88b,                d8""Y8b
#            Y8b,__,,aadd88888bbaaa,888888,aaadd88888bbaa,,__,d8P
#             "88888888888888888888I888888I88888888888888888888"
#             /|\`""YY8888888PP""""`888888'""""YY8888888PP""'/|\
#            / | \                  `WWWW'                  / | \
#           /  |  \                 ,dMMb,                 /  |  \
#          /   |   \                I8888I                /   |   \
#         /    |    \               `Y88P'               /    |    \
#        /     |     \               `YP'               /     |     \
#       /      |      \               88               /      |      \
#      /       |       \             i88i             /       |       \
#     /        |        \            8888            /        |        \
# "Y88888888888888888888888P"       i8888i       "Y88888888888888888888888P"
#   `""Y888888888888888P""'        ,888888,        `""Y888888888888888P""'
#                                  I888888I
#                                  Y888888P
#                                  `Y8888P'
#                                   `WWWW'
#                                    dMMb
#                                 _,ad8888ba,_
#                     __,,aaaadd888888888888888bbaaaa,,__
#                   d8888888888888888888888888888888888888b

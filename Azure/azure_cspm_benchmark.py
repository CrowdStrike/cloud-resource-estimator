"""
azure-cspm-benchmark.py

Assists with provisioning calculations by retrieving a count
of all billable resources attached to an Azure subscription.

Supports subscription filtering capabilities:
- --skip-subscriptions: Exclude specific subscription IDs
- --include-subscriptions: Process only specific subscription IDs
- Environment variable support: AZURE_SKIP_SUBSCRIPTIONS, AZURE_INCLUDE_SUBSCRIPTIONS
"""

import csv
import logging
import argparse
import os

from functools import cached_property, lru_cache
from azure.identity import AzureCliCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.subscriptions import SubscriptionClient
from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
import msrestazure.tools
from tabulate import tabulate

headers = {
    'tenant_id': 'Azure Tenant ID',
    'subscription_id': 'Azure Subscription ID',
    'aks_nodes': 'Kubernetes Nodes',
    'vms': 'Virtual Machines',
    'aci_containers': 'Container Instances'
}


class AzureHandle:
    def __init__(self):
        # Acquire a credential object using CLI-based authentication.
        self.creds = AzureCliCredential()

    @cached_property
    def subscriptions(self):
        return list(self.subscription_client.subscriptions.list())

    @property
    def tenants(self):
        return list(self.subscription_client.tenants.list())

    def aci_resources(self, subscription_id):
        client = self.resource_client(subscription_id)
        return client.resources.list(filter="resourceType eq 'microsoft.containerinstance/containergroups'")

    def aks_resources(self, subscription_id):
        client = self.resource_client(subscription_id)
        return client.resources.list(filter="resourceType eq 'microsoft.containerservice/managedclusters'")

    def vmss_resources(self, subscription_id):
        client = self.resource_client(subscription_id)
        return client.resources.list(filter="resourceType eq 'Microsoft.Compute/virtualMachineScaleSets'")

    def vms_resources(self, subscription_id):
        client = self.resource_client(subscription_id)
        return client.resources.list(filter="resourceType eq 'Microsoft.Compute/virtualMachines'")

    def managed_clusters(self, subscription_id):
        return self.container_client(subscription_id).managed_clusters.list()

    def rhos_clusters(self, subscription_id):
        return self.container_client(subscription_id).open_shift_managed_clusters.list()

    def container_vmss(self, aks_resource):
        parsed_id = msrestazure.tools.parse_resource_id(aks_resource.id)
        client = self.container_client(parsed_id['subscription'])
        return client.agent_pools.list(resource_group_name=parsed_id['resource_group'],
                                       resource_name=parsed_id['resource_name'])

    def container_aci(self, aci_resource):
        parsed_id = msrestazure.tools.parse_resource_id(aci_resource.id)
        client = self.container_instance_client(parsed_id['subscription'])
        return client.container_groups.get(resource_group_name=parsed_id['resource_group'],
                                           container_group_name=parsed_id['resource_name']).containers

    def vms_inside_vmss(self, vmss_resource):
        parsed_id = msrestazure.tools.parse_resource_id(vmss_resource.id)
        client = ComputeManagementClient(self.creds, parsed_id['subscription'])
        return client.virtual_machine_scale_set_vms.list(resource_group_name=parsed_id['resource_group'],
                                                         virtual_machine_scale_set_name=vmss_resource.name)

    @lru_cache
    def container_client(self, subscription_id):
        return ContainerServiceClient(self.creds, subscription_id)

    @lru_cache
    def container_instance_client(self, subscription_id):
        return ContainerInstanceManagementClient(self.creds, subscription_id)

    @lru_cache
    def resource_client(self, subscription_id):
        return ResourceManagementClient(self.creds, subscription_id)

    @cached_property
    def subscription_client(self):
        return SubscriptionClient(self.creds)

    def filter_subscriptions(self, subscriptions, skip_list=None, include_list=None):
        """
        Filter subscriptions based on skip/include lists.

        Args:
            subscriptions: List of subscription objects
            skip_list: Comma-separated string of subscription IDs to exclude
            include_list: Comma-separated string of subscription IDs to include

        Returns:
            Filtered list of subscriptions

        Note: If both skip_list and include_list are provided, include_list takes precedence.
        """
        filtered = subscriptions

        # Include list takes precedence over skip list
        if include_list:
            # Filter out empty strings from input
            include_set = {s.strip() for s in include_list.split(",") if s.strip()}

            # Validate that provided IDs exist
            available_ids = {s.subscription_id for s in subscriptions}
            invalid_ids = include_set - available_ids
            if invalid_ids:
                log.warning("The following subscription IDs in include list were not found: %s",
                           ', '.join(sorted(invalid_ids)))

            filtered = [s for s in filtered if s.subscription_id in include_set]
            log.info("Include filter applied: processing %d of %d subscriptions",
                     len(filtered), len(subscriptions))
        elif skip_list:
            # Filter out empty strings from input
            skip_set = {s.strip() for s in skip_list.split(",") if s.strip()}
            filtered = [s for s in filtered if s.subscription_id not in skip_set]
            log.info("Skip filter applied: processing %d of %d subscriptions (skipped %d)",
                     len(filtered), len(subscriptions), len(subscriptions) - len(filtered))

        return filtered


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Azure subscription resource analyzer with filtering capabilities',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process only a specific subscription
  python3 azure_cspm_benchmark.py --include-subscriptions "abc-123-def"

  # Skip problematic subscriptions
  python3 azure_cspm_benchmark.py --skip-subscriptions "sub-1,sub-2"

  # Use environment variables
  export AZURE_INCLUDE_SUBSCRIPTIONS="abc-123-def"
  python3 azure_cspm_benchmark.py

Environment Variables:
  AZURE_SKIP_SUBSCRIPTIONS      Comma-separated list of subscription IDs to skip
  AZURE_INCLUDE_SUBSCRIPTIONS   Comma-separated list of subscription IDs to include

Note: --include-subscriptions takes precedence over --skip-subscriptions
        """
    )

    parser.add_argument(
        '--skip-subscriptions',
        help='Comma-separated list of subscription IDs to skip. '
             'Can also be set via AZURE_SKIP_SUBSCRIPTIONS environment variable.'
    )

    parser.add_argument(
        '--include-subscriptions',
        help='Comma-separated list of subscription IDs to include (exclusive filter). '
             'Can also be set via AZURE_INCLUDE_SUBSCRIPTIONS environment variable. '
             'Takes precedence over --skip-subscriptions.'
    )

    args = parser.parse_args()

    # Environment variables as fallback
    if not args.skip_subscriptions:
        args.skip_subscriptions = os.environ.get('AZURE_SKIP_SUBSCRIPTIONS')

    if not args.include_subscriptions:
        args.include_subscriptions = os.environ.get('AZURE_INCLUDE_SUBSCRIPTIONS')

    return args


LOG_LEVEL = logging.INFO
log = logging.getLogger('azure')
log.setLevel(LOG_LEVEL)
ch = logging.StreamHandler()
ch.setLevel(LOG_LEVEL)
formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', '%Y-%m-%d %H:%M:%S')
ch.setFormatter(formatter)
log.addHandler(ch)

for mod in ['azure.identity._internal.decorators', 'azure.core.pipeline.policies.http_logging_policy']:
    logging.getLogger(mod).setLevel(logging.WARNING)


def main():
    """Main execution function."""
    args = parse_args()

    data = []
    totals = {'tenant_id': 'totals', 'subscription_id': 'totals', 'aks_nodes': 0, 'vms': 0, 'aci_containers': 0}
    az = AzureHandle()

    # Get all subscriptions with error handling
    try:
        all_subscriptions = az.subscriptions
    except Exception as e:
        log.error("Failed to retrieve Azure subscriptions: %s", str(e))
        log.error("Please ensure you are authenticated with 'az login' and have proper permissions")
        return 1

    log.info("Discovered %d subscription(s) within %d tenant(s)",
             len(all_subscriptions), len(az.tenants))

    # Apply filtering
    subscriptions = az.filter_subscriptions(
        all_subscriptions,
        skip_list=args.skip_subscriptions,
        include_list=args.include_subscriptions
    )

    # Log filtering details
    if args.include_subscriptions:
        log.info("INCLUDE filter active: %s", args.include_subscriptions)
        skipped = [s for s in all_subscriptions if s not in subscriptions]
        if skipped:
            log.info("Skipping %d subscription(s): %s",
                     len(skipped),
                     ', '.join([f"{s.display_name} ({s.subscription_id})" for s in skipped]))
    elif args.skip_subscriptions:
        log.info("SKIP filter active: %s", args.skip_subscriptions)
        skipped = [s for s in all_subscriptions if s not in subscriptions]
        if skipped:
            log.info("Skipping %d subscription(s): %s",
                     len(skipped),
                     ', '.join([f"{s.display_name} ({s.subscription_id})" for s in skipped]))

    if not subscriptions:
        log.error("No subscriptions to process after filtering. Check your filter settings.")
        return 1

    log.info("Processing %d subscription(s):", len(subscriptions))
    for sub in subscriptions:
        log.info("  - %s (id=%s)", sub.display_name, sub.subscription_id)

    # Process each subscription
    for subscription in subscriptions:
        row = {'tenant_id': subscription.tenant_id, 'subscription_id': subscription.subscription_id,
               'aks_nodes': 0, 'vms': 0, 'aci_containers': 0}
        log.info("Processing Azure subscription: %s (id=%s)", subscription.display_name, subscription.subscription_id)

        # (1) Process AKS
        for aks in az.aks_resources(subscription.subscription_id):
            for node_pool in az.container_vmss(aks):
                log.info("Identified node pool: '%s' within AKS: '%s' with %d node(s)",
                         node_pool.name, aks.name, node_pool.count)
                row['aks_nodes'] += node_pool.count

        # (2) Process VMSS
        for vmss in az.vmss_resources(subscription.subscription_id):
            if vmss.tags is not None and 'aks-managed-createOperationID' in vmss.tags:
                # AKS resources already accounted for above
                continue

            vm_count = sum(1 for vm in az.vms_inside_vmss(vmss))
            log.info("Identified %d vm resource(s) inside Scale Set: '%s'", vm_count, vmss.name)
            row['vms'] += vm_count

        # (3) Process ACI
        for aci in az.aci_resources(subscription.subscription_id):
            container_count = sum(1 for container in az.container_aci(aci))
            log.info("Identified %d container resource(s) inside Container Group: '%s'", container_count, aci.name)
            row['aci_containers'] += container_count

        # (4) Process VMs
        vm_count = sum((1 for vm in az.vms_resources(subscription.subscription_id)))
        log.info('Identified %d vm resource(s) outside of Scale Sets', vm_count)
        row['vms'] += vm_count
        data.append(row)

        totals['vms'] += row['vms']
        totals['aks_nodes'] += row['aks_nodes']
        totals['aci_containers'] += row['aci_containers']

    data.append(totals)

    # Output our results
    print(tabulate(data, headers=headers, tablefmt="grid"))

    with open('azure-benchmark.csv', 'w', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=headers.keys())
        csv_writer.writeheader()
        csv_writer.writerows(data)

    log.info("CSV summary has been exported to ./azure-benchmark.csv file")
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())

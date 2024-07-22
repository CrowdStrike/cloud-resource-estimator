"""
azure-cspm-benchmark.py

Assists with provisioning calculations by retrieving a count
of all billable resources attached to an Azure subscription.
"""

import csv
import logging

from functools import cached_property, lru_cache
from azure.identity import AzureCliCredential
from azure.mgmt.resource import ResourceManagementClient, SubscriptionClient
from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
import msrestazure.tools


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


LOG_LEVEL = logging.INFO
LOG_LEVEL = logging.DEBUG
log = logging.getLogger('azure')
log.setLevel(LOG_LEVEL)
ch = logging.StreamHandler()
ch.setLevel(LOG_LEVEL)
formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', '%Y-%m-%d %H:%M:%S')
ch.setFormatter(formatter)
log.addHandler(ch)

for mod in ['azure.identity._internal.decorators', 'azure.core.pipeline.policies.http_logging_policy']:
    logging.getLogger(mod).setLevel(logging.WARNING)


data = []
totals = {'tenant_id': 'totals', 'subscription_id': 'totals', 'aks_nodes': 0, 'vms': 0, 'aci_containers': 0}
az = AzureHandle()

log.info("You have access to %d subscription(s) within %s tenant(s)", len(az.subscriptions), len(az.tenants))
for subscription in az.subscriptions:
    row = {'tenant_id': subscription.tenant_id, 'subscription_id': subscription.subscription_id,
           'aks_nodes': 0, 'vms': 0, 'aci_containers': 0}
    log.info("Exploring Azure subscription: %s (id=%s)", subscription.display_name, subscription.subscription_id)

    vmss_list = list(az.vmss_resources(subscription.subscription_id))

    # (1) Process AKS
    for aks in az.aks_resources(subscription.subscription_id):
        for node_pool in az.container_vmss(aks):
            log.debug("Identified node pool: '%s' within AKS: '%s' with %d node(s)",
                      node_pool.name, aks.name, node_pool.count)
            row['aks_nodes'] += node_pool.count

    # (2) Process VMSS
    for vmss in az.vmss_resources(subscription.subscription_id):
        if vmss.tags is not None and 'aks-managed-createOperationID' in vmss.tags:
            # AKS resources already accounted for above
            continue

        vm_count = sum(1 for vm in az.vms_inside_vmss(vmss))
        log.debug("Identified %d vm resource(s) inside Scale Set: '%s'", vm_count, vmss.name)
        row['vms'] += vm_count

    # # (3) Process ACI
    for aci in az.aci_resources(subscription.subscription_id):
        container_count = sum(1 for container in az.container_aci(aci))
        log.debug("Identified %d container resource(s) inside Container Group: '%s'", container_count, aci.name)
        row['aci_containers'] += container_count

    # (4) Process VMs
    vm_count = sum((1 for vm in az.vms_resources(subscription.subscription_id)))
    log.debug('Identified %d vm resource(s) outside of Scale Sets', vm_count)
    row['vms'] += vm_count
    data.append(row)

    totals['vms'] += row['vms']
    totals['aks_nodes'] += row['aks_nodes']
    totals['aci_containers'] += row['aci_containers']

data.append(totals)

headers = ['tenant_id', 'subscription_id', 'aks_nodes', 'vms', 'aci_containers']
with open('az-benchmark.csv', 'w', newline='', encoding='utf-8') as csv_file:
    csv_writer = csv.DictWriter(csv_file, fieldnames=headers)
    csv_writer.writeheader()
    csv_writer.writerows(data)

log.info("CSV summary has been exported to ./az-benchmark.csv file")

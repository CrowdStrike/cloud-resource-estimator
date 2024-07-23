"""
gcp-cspm-benchmark.py

Assists with provisioning calculations by retrieving a count
of all billable resources attached to a GCP project.
"""

import csv
import logging
import os
from tabulate import tabulate
from functools import cached_property
from typing import List, Dict, Any
import google.api_core.exceptions
from google.cloud.resourcemanager import ProjectsClient
from google.cloud.resourcemanager_v3.types import Project
from google.cloud import compute
from googleapiclient import discovery
from googleapiclient.errors import HttpError

# Suppress gRPC and absl logs
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Configuration for logging
LOG_LEVEL = logging.DEBUG
log = logging.getLogger('gcp')
log.setLevel(LOG_LEVEL)
ch = logging.StreamHandler()
ch.setLevel(LOG_LEVEL)
formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', '%Y-%m-%d %H:%M:%S')
ch.setFormatter(formatter)
log.addHandler(ch)


class GCP:
    def projects(self) -> List[Project]:
        return ProjectsClient().search_projects()

    def list_instances(self, project_id: str):
        request = compute.AggregatedListInstancesRequest(max_results=50, project=project_id)
        return self.instances_client.aggregated_list(request=request)

    def clusters(self, project_id: str) -> List[Dict[str, Any]]:
        service = discovery.build('container', 'v1')
        endpoint = service.projects().zones().clusters()
        request = endpoint.list(projectId=project_id, zone='-')
        response = request.execute()
        return response.get('clusters', [])

    def list_cloud_run_services(self, project_id: str) -> List[Dict[str, Any]]:
        service = discovery.build('run', 'v1')
        parent = f"projects/{project_id}/locations/-"
        request = service.projects().locations().services().list(parent=parent)
        response = request.execute()
        return response.get('items', [])

    @cached_property
    def instances_client(self) -> compute.InstancesClient:
        return compute.InstancesClient()

    @classmethod
    def is_vm_kubenode(cls, instance: compute.Instance) -> bool:
        return any(k.key == 'kubeconfig' for k in instance.metadata.items)

    @classmethod
    def is_vm_running(cls, instance: compute.Instance) -> bool:
        return instance.status != 'TERMINATED'

    @classmethod
    def is_cluster_autopilot(cls, cluster: Dict[str, Any]) -> bool:
        return cluster.get('autopilot', {}).get('enabled', False)


def process_gcp_project(project: Project) -> Dict[str, Any]:
    if project.state == Project.State.DELETE_REQUESTED:
        log.debug("Skipping GCP project %s (project pending deletion)", project.display_name)
        return {}

    result = {'project_id': project.project_id,
              'kubenodes_running': 0, 'kubenodes_terminated': 0,
              'vms_running': 0, 'vms_terminated': 0,
              'autopilot_clusters': 0, 'cloud_run_services': 0}
    log.info("Processing GCP project: %s", project.display_name)

    fail_safe(count_instances, project, result)
    fail_safe(count_autopilot_clusters, project, result)
    fail_safe(count_cloud_run_services, project, result)

    return result


def fail_safe(count_func, *args) -> None:
    try:
        count_func(*args)
    except google.api_core.exceptions.Forbidden as exc:
        log.warning("Cannot explore project: %s: %s", project.display_name, exc)
        if 'Compute Engine API has not been used' in str(exc):
            service_disabled_calls.append((project.project_id, 'compute.googleapis.com'))
    except google.api_core.exceptions.GoogleAPIError as exc:
        log.warning("Google API error for project: %s: %s", project.display_name, exc)
    except HttpError as exc:
        if exc.status_code == 403 and 'SERVICE_DISABLED' in str(exc):
            log.warning("The required API is not enabled for the project: %s: %s",
                        project.display_name, exc.reason)
            service_name = get_service_disabled_name(exc)
            if service_name:
                service_disabled_calls.append((project.project_id, service_name))
    except Exception as exc:
        log.error("Unexpected error for project: %s: %s", project.display_name, exc)


def get_service_disabled_name(exc: HttpError) -> str:
    for detail in exc.error_details:
        if detail.get('@type') == 'type.googleapis.com/google.rpc.ErrorInfo':
            return detail['metadata']['service']
    return None


def generate_gcloud_commands(service_disabled_calls: List[str]) -> List[str]:
    commands = []
    for project_id, service_name in service_disabled_calls:
        commands.append(f"gcloud services enable {service_name} --project {project_id}")
    return commands


def count_autopilot_clusters(project: Project, result: Dict[str, int]):
    for cluster in gcp.clusters(project.project_id):
        if GCP.is_cluster_autopilot(cluster):
            result['autopilot_clusters'] += 1


def count_instances(project: Project, result: Dict[str, int]):
    for _zone, response in gcp.list_instances(project.project_id):
        if response.instances:
            for instance in response.instances:
                typ = 'kubenode' if GCP.is_vm_kubenode(instance) else 'vm'
                state = 'running' if GCP.is_vm_running(instance) else 'terminated'
                key = f"{typ}s_{state}"
                result[key] += 1


def count_cloud_run_services(project: Project, result: Dict[str, int]):
    services = gcp.list_cloud_run_services(project.project_id)
    result['cloud_run_services'] = len(services)


data = []
headers = {
    'project_id': 'Project ID',
    'kubenodes_running': 'Kube Nodes Running',
    'kubenodes_terminated': 'Kube Nodes Terminated',
    'vms_running': 'VMs Running',
    'vms_terminated': 'VMs Terminated',
    'autopilot_clusters': 'Autopilot Clusters',
    'cloud_run_services': 'Cloud Run Services'
}
totals = {'project_id': 'totals',
          'kubenodes_running': 0, 'kubenodes_terminated': 0,
          'vms_running': 0, 'vms_terminated': 0,
          'autopilot_clusters': 0, 'cloud_run_services': 0}
service_disabled_calls = []

gcp = GCP()

projects = gcp.projects()
if not projects:
    log.error("No GCP projects found")
    exit()

for project in gcp.projects():
    row = process_gcp_project(project)
    if row:
        data.append(row)
        for k in totals:
            if k != 'project_id':
                totals[k] += row[k]

data.append(totals)

# Output our results
print(tabulate(data, headers=headers, tablefmt="grid"))

with open('gcp-benchmark.csv', 'w', newline='', encoding='utf-8') as csv_file:
    csv_writer = csv.DictWriter(csv_file, fieldnames=headers.keys())
    csv_writer.writeheader()
    csv_writer.writerows(data)

log.info("CSV summary has been exported to ./gcp-benchmark.csv file")

if service_disabled_calls:
    log.warning("There were some projects with disabled services that may lead to inaccurate results.")
    log.warning("A list of gcloud commands to enable the services has been exported to ./disabled-services.txt")
    with open('disabled-services.txt', 'w', encoding='utf-8') as f:
        gcloud_commands = generate_gcloud_commands(service_disabled_calls)
        for cmd in gcloud_commands:
            f.write(cmd + '\n')

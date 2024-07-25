"""
gcp-cspm-benchmark.py

Assists with provisioning calculations by retrieving a count
of all billable resources attached to a GCP project.
"""

import csv
import logging
import os
from functools import cached_property
from typing import List, Dict, Any
from tabulate import tabulate
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
        endpoint = service.projects().zones().clusters()  # pylint: disable=no-member
        request = endpoint.list(projectId=project_id, zone='-')
        response = request.execute()
        return response.get('clusters', [])

    def list_cloud_run_services(self, project_id: str) -> List[Dict[str, Any]]:
        service = discovery.build('run', 'v1')
        parent = f"projects/{project_id}/locations/-"
        request = service.projects().locations().services().list(parent=parent)  # pylint: disable=no-member
        response = request.execute()
        return response.get('items', [])

    def list_cloud_run_jobs(self, project_id: str) -> List[Dict[str, Any]]:
        service = discovery.build('run', 'v1')
        parent = f'namespaces/{project_id}'
        request = service.namespaces().jobs().list(parent=parent)  # pylint: disable=no-member
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

    @classmethod
    def get_autopilot_active_nodes(cls, cluster: Dict[str, Any]) -> int:
        return cluster.get('currentNodeCount', 0)


def process_gcp_project(gcp_project: Project) -> Dict[str, Any]:
    if gcp_project.state == Project.State.DELETE_REQUESTED:
        log.info("Skipping GCP project %s (project pending deletion)", gcp_project.display_name)
        return {}

    result = {
        'project_id': gcp_project.project_id,
        'kubenodes_running': 0, 'kubenodes_terminated': 0,
        'vms_running': 0, 'vms_terminated': 0,
        'autopilot_clusters': 0, 'autopilot_nodes': 0,
        'cloud_run_services': 0, 'cloud_run_jobs': 0
    }

    log.info("Processing GCP project: %s", gcp_project.display_name)

    fail_safe(count_instances, gcp_project, result)
    fail_safe(count_autopilot_clusters, gcp_project, result)
    fail_safe(count_cloud_run_services, gcp_project, result)
    fail_safe(count_cloud_run_jobs, gcp_project, result)

    return result


def fail_safe(count_func, *args) -> None:
    try:
        count_func(*args)
    except google.api_core.exceptions.Forbidden as exc:
        if 'Compute Engine API has not been used' in str(exc):
            log_warning('compute.googleapis.com', project.display_name)
            add_message(project.project_id, exc.errors[0]['message'])
        else:
            log.error("Unexpected error for project: %s: %s", project.display_name, exc)
    except HttpError as exc:
        if exc.status_code == 403 and 'SERVICE_DISABLED' in str(exc):
            log_warning(get_service_disabled_name(exc), project.display_name)
            add_message(project.project_id, exc.reason)
        else:
            log.error("Unexpected error for project: %s: %s", project.display_name, exc)
    except Exception as exc:  # pylint: disable=broad-except
        log.error("Unexpected error for project: %s: %s", project.display_name, exc)


def log_warning(api: str, project_name: str) -> None:
    api_names = {
        'compute.googleapis.com': 'Compute Engine',
        'container.googleapis.com': 'Kubernetes Engine',
        'run.googleapis.com': 'Cloud Run',
    }
    message = f"Unable to process {api_names[api]} API for project: {project_name}."
    log.warning(message)


def add_message(project_id: str, message: str) -> None:
    if project_id not in service_disabled_calls:
        service_disabled_calls[project_id] = []
    service_disabled_calls[project_id].append(message)


def get_service_disabled_name(exc: HttpError) -> str:
    for detail in exc.error_details:
        if detail.get('@type') == 'type.googleapis.com/google.rpc.ErrorInfo':
            return detail['metadata']['service']
    return None


def count_autopilot_clusters(gcp_project: Project, result: Dict[str, int]):
    for cluster in gcp.clusters(gcp_project.project_id):
        if GCP.is_cluster_autopilot(cluster):
            result['autopilot_clusters'] += 1
            result['autopilot_nodes'] += GCP.get_autopilot_active_nodes(cluster)


def count_instances(gcp_project: Project, result: Dict[str, int]):
    for _zone, response in gcp.list_instances(gcp_project.project_id):
        if response.instances:
            for instance in response.instances:
                typ = 'kubenode' if GCP.is_vm_kubenode(instance) else 'vm'
                state = 'running' if GCP.is_vm_running(instance) else 'terminated'
                key = f"{typ}s_{state}"
                result[key] += 1


def count_cloud_run_services(gcp_project: Project, result: Dict[str, int]):
    services = gcp.list_cloud_run_services(gcp_project.project_id)
    result['cloud_run_services'] = len(services)


def count_cloud_run_jobs(gcp_project: Project, result: Dict[str, int]):
    jobs = gcp.list_cloud_run_jobs(gcp_project.project_id)
    result['cloud_run_jobs'] = len(jobs)


data = []
service_disabled_calls = {}
headers = {
    'project_id': 'Project ID',
    'kubenodes_running': 'K8s Nodes (Running)',
    'kubenodes_terminated': 'K8s Nodes (Terminated)',
    'vms_running': 'VMs (Running)',
    'vms_terminated': 'VMs (Terminated)',
    'autopilot_clusters': 'Autopilot Clusters',
    'autopilot_nodes': 'Autopilot Nodes (Running)',
    'cloud_run_services': 'Cloud Run Services',
    'cloud_run_jobs': 'Cloud Run Jobs'
}
totals = {
    'project_id': 'totals',
    'kubenodes_running': 0, 'kubenodes_terminated': 0,
    'vms_running': 0, 'vms_terminated': 0,
    'autopilot_clusters': 0, 'autopilot_nodes': 0,
    'cloud_run_services': 0, 'cloud_run_jobs': 0
}

gcp = GCP()

projects = gcp.projects()
if not projects:
    log.error("No GCP projects found")
    exit(1)  # pylint: disable=consider-using-sys-exit

for project in gcp.projects():
    row = process_gcp_project(project)
    if row:
        data.append(row)
        for k in totals:
            if k != 'project_id':
                totals[k] += row[k]

data.append(totals)

# Output our results
print(tabulate(data, headers=headers, tablefmt="grid", maxheadercolwidths=[10, 15, 15, 10, 15, 15, 15, 15, 12]))

with open('gcp-benchmark.csv', 'w', newline='', encoding='utf-8') as csv_file:
    csv_writer = csv.DictWriter(csv_file, fieldnames=headers.keys())
    csv_writer.writeheader()
    csv_writer.writerows(data)

log.info("CSV file saved to: ./gcp-benchmark.csv")

if service_disabled_calls:
    MSG = (
        "Some API service calls were disabled, preventing data processing. "
        "These calls might be intentionally disabled in your environment. "
        "More details have been saved to: ./api-exceptions.txt"
    )
    log.warning(MSG)

    with open('api-exceptions.txt', 'w', encoding='utf-8') as f:
        for project, messages in service_disabled_calls.items():
            f.write(f"Project ID: {project}\n")
            for msg in set(messages):
                f.write(f"- {msg}\n")
            f.write('\n')

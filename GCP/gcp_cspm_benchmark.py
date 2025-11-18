"""
gcp-cspm-benchmark.py

Assists with provisioning calculations by retrieving a count
of all billable resources attached to a GCP project.
"""

import csv
import fnmatch
import logging
import os
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from threading import Lock, local
from typing import List, Dict, Any
from tabulate import tabulate
import google.api_core.exceptions
from google.cloud.resourcemanager import ProjectsClient
from google.cloud.resourcemanager_v3.types import Project
from google.cloud import compute
from googleapiclient import discovery
from googleapiclient.errors import HttpError
import requests.exceptions
import urllib3.exceptions

# Suppress gRPC and absl logs
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# Configuration for logging
LOG_LEVEL = logging.DEBUG
log = logging.getLogger("gcp")
log.setLevel(LOG_LEVEL)
ch = logging.StreamHandler()
ch.setLevel(LOG_LEVEL)
formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s", "%Y-%m-%d %H:%M:%S")
ch.setFormatter(formatter)
log.addHandler(ch)

# Performance configuration
API_DELAY = float(os.environ.get('GCP_API_DELAY', '0.05'))
THREADS = int(os.environ.get('GCP_THREADS', '3'))
BATCH_SIZE = int(os.environ.get('GCP_BATCH_SIZE', '20'))
BATCH_DELAY = float(os.environ.get('GCP_BATCH_DELAY', '10'))

# Thread-safe locks for shared data
data_lock = Lock()
totals_lock = Lock()
service_calls_lock = Lock()

# Thread-local storage for GCP clients
thread_local_data = local()


def get_thread_local_gcp():
    """Get or create thread-local GCP client instance."""
    if not hasattr(thread_local_data, 'gcp'):
        thread_local_data.gcp = GCP()
    return thread_local_data.gcp


def api_delay():
    """Add configurable delay between API calls for rate limiting."""
    if API_DELAY > 0:
        time.sleep(API_DELAY)


class GCP:
    def __init__(self):
        """Initialize GCP client with thread-local instances."""
        self._instances_client = None
        self._container_client = None
        self._run_client = None

    def projects(self) -> List[Project]:
        return ProjectsClient().search_projects()

    def list_instances(self, project_id: str):
        api_delay()
        request = compute.AggregatedListInstancesRequest(max_results=50, project=project_id)
        return self.instances_client.aggregated_list(request=request)

    def clusters(self, project_id: str) -> List[Dict[str, Any]]:
        api_delay()
        endpoint = self.container_client.projects().zones().clusters()  # pylint: disable=no-member
        request = endpoint.list(projectId=project_id, zone="-")
        response = request.execute()
        return response.get("clusters", [])

    @lru_cache(maxsize=128)
    def get_cached_clusters(self, project_id: str) -> List[Dict[str, Any]]:
        """Cache cluster data to prevent duplicate API calls per project."""
        return self.clusters(project_id)

    def list_cloud_run_services(self, project_id: str) -> List[Dict[str, Any]]:
        api_delay()
        parent = f"projects/{project_id}/locations/-"
        request = self.run_client.projects().locations().services().list(parent=parent)  # pylint: disable=no-member
        response = request.execute()
        return response.get("items", [])

    def list_cloud_run_jobs(self, project_id: str) -> List[Dict[str, Any]]:
        api_delay()
        parent = f"namespaces/{project_id}"
        request = self.run_client.namespaces().jobs().list(parent=parent)  # pylint: disable=no-member
        response = request.execute()
        return response.get("items", [])

    @property
    def instances_client(self) -> compute.InstancesClient:
        """Thread-safe instances client creation."""
        if self._instances_client is None:
            self._instances_client = compute.InstancesClient()
        return self._instances_client

    @property
    def container_client(self):
        """Thread-safe Container API client creation."""
        if self._container_client is None:
            self._container_client = discovery.build("container", "v1")
        return self._container_client

    @property
    def run_client(self):
        """Thread-safe Cloud Run API client creation."""
        if self._run_client is None:
            self._run_client = discovery.build("run", "v1")
        return self._run_client

    @classmethod
    def is_vm_kubenode(cls, instance: compute.Instance) -> bool:
        if any(k.key == "kubeconfig" for k in instance.metadata.items):
            return True

        if instance.labels:
            gke_indicators = ["goog-gke-node", "gke-cluster", "k8s-", "kubernetes"]
            for key, _ in instance.labels.items():
                if any(indicator in key.lower() for indicator in gke_indicators):
                    return True

        if instance.name and "gke-" in instance.name:
            return True

        return False

    @classmethod
    def is_vm_running(cls, instance: compute.Instance) -> bool:
        return instance.status != "TERMINATED"

    @classmethod
    def is_cluster_autopilot(cls, cluster: Dict[str, Any]) -> bool:
        return cluster.get("autopilot", {}).get("enabled", False)

    @classmethod
    def get_autopilot_active_nodes(cls, cluster: Dict[str, Any]) -> int:
        return cluster.get("currentNodeCount", 0)


def process_gcp_project(gcp_project: Project) -> Dict[str, Any]:
    if gcp_project.state == Project.State.DELETE_REQUESTED:
        log.info("Skipping GCP project %s (project pending deletion)", gcp_project.display_name)
        return {}

    result = {
        "project_id": gcp_project.project_id,
        "kubenodes_running": 0,
        "kubenodes_terminated": 0,
        "vms_running": 0,
        "vms_terminated": 0,
        "autopilot_clusters": 0,
        "autopilot_nodes": 0,
        "cloud_run_services": 0,
        "cloud_run_jobs": 0,
    }

    log.info("Processing GCP project: %s", gcp_project.display_name)

    fail_safe(count_instances, gcp_project, result, gcp_project)
    fail_safe(count_autopilot_clusters, gcp_project, result, gcp_project)
    fail_safe(count_cloud_run_resources, gcp_project, result, gcp_project)
    fail_safe(validate_and_adjust_kube_counts, gcp_project, result, gcp_project)

    return result


def fail_safe(count_func, *args) -> None:
    # Extract project from args for error handling
    project = args[-1] if args else None
    # Remove project from args passed to count_func (it's already in the first args)
    func_args = args[:-1] if len(args) > 1 else args

    try:
        count_func(*func_args)
    except google.api_core.exceptions.Forbidden as exc:
        if "Compute Engine API has not been used" in str(exc) and project:
            log_warning("compute.googleapis.com", project.display_name)
            # Safely extract error message
            error_message = str(exc)
            if hasattr(exc, 'errors') and exc.errors and len(exc.errors) > 0:
                error_message = exc.errors[0].get("message", str(exc))
            add_message(project.project_id, error_message)
        else:
            log.error("Unexpected error for project: %s: %s",
                     project.display_name if project else "Unknown", exc)
    except HttpError as exc:
        if exc.status_code == 403 and ("SERVICE_DISABLED" in str(exc) or "BILLING_DISABLED" in str(exc)) and project:
            service_name = get_service_disabled_name(exc)
            error_type = "BILLING_DISABLED" if "BILLING_DISABLED" in str(exc) else "SERVICE_DISABLED"
            log_warning(service_name, project.display_name, error_type)
            add_message(project.project_id, getattr(exc, 'reason', str(exc)))
        else:
            log.error("Unexpected error for project: %s: %s",
                     project.display_name if project else "Unknown", exc)
    except (ssl.SSLError, requests.exceptions.SSLError) as exc:
        log.warning("SSL connection issue for project: %s (retryable network error): %s",
                   project.display_name if project else "Unknown", exc)
        add_message(project.project_id if project else "Unknown", f"SSL connection issue: {exc}")
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        urllib3.exceptions.ProtocolError,
        ConnectionError,
        OSError
    ) as exc:
        log.warning("Network connection issue for project: %s (retryable network error): %s",
                   project.display_name if project else "Unknown", exc)
        add_message(project.project_id if project else "Unknown", f"Network connection issue: {exc}")
    except Exception as exc:  # pylint: disable=broad-except
        log.error("Unexpected error for project: %s: %s",
                 project.display_name if project else "Unknown", exc)


def log_warning(api: str, project_name: str, error_type: str = "SERVICE_DISABLED") -> None:
    api_names = {
        "compute.googleapis.com": "Compute Engine",
        "container.googleapis.com": "Kubernetes Engine",
        "run.googleapis.com": "Cloud Run (Services & Jobs)",
    }

    if error_type == "BILLING_DISABLED":
        message = f"Billing not enabled for {api_names[api]} API on project: {project_name}. Enable billing to access this API."
    else:
        message = f"Unable to process {api_names[api]} API for project: {project_name}."

    log.warning(message)


def add_message(project_id: str, message: str) -> None:
    with service_calls_lock:
        if project_id not in service_disabled_calls:
            service_disabled_calls[project_id] = []
        service_disabled_calls[project_id].append(message)


def get_service_disabled_name(exc: HttpError) -> str:
    """
    Extract the service name from HttpError details safely.

    Returns:
        str: Service name if found, or 'unknown' if not extractable
    """
    try:
        for detail in exc.error_details:
            if detail.get("@type") == "type.googleapis.com/google.rpc.ErrorInfo":
                metadata = detail.get("metadata", {})
                service = metadata.get("service")
                if service:
                    return service
    except (KeyError, AttributeError, TypeError):
        pass
    return "unknown"


def validate_and_adjust_kube_counts(gcp_project: Project, result: Dict[str, Any]) -> None:
    """Compare instance-detected kube nodes with GKE API reported nodes and adjust if needed."""
    try:
        # Check if we already know the Container API is unavailable (thread-safe read)
        with service_calls_lock:
            api_errors = service_disabled_calls.get(gcp_project.project_id, [])

        if api_errors:
            # Check for container API issues (service disabled, billing disabled, or any container-related error)
            container_unavailable = any(
                "container" in err.lower() or
                ("billing" in err.lower() and "container" in err.lower()) or
                "service_disabled" in err.lower()
                for err in api_errors
            )
            if container_unavailable:
                message = (
                    f"Skipping validation for project {gcp_project.project_id} due to container API access issues"
                )
                log.debug(message)
                return

        gcp = get_thread_local_gcp()
        standard_node_count = 0
        for cluster in gcp.get_cached_clusters(gcp_project.project_id):
            if not GCP.is_cluster_autopilot(cluster):
                standard_node_count += cluster.get("currentNodeCount", 0)

        detected_nodes = result["kubenodes_running"]

        if standard_node_count > detected_nodes:

            discrepancy = standard_node_count - detected_nodes
            message = (
                f"Project {gcp_project.project_id}: GKE API reports {standard_node_count} nodes, "
                f"but only {detected_nodes} were detected via instance metadata. "
                f"Adjusting count to {standard_node_count} (added {discrepancy} nodes)"
            )
            log.warning(message)

            result["kubenodes_running"] = standard_node_count

    except Exception:  # pylint: disable=broad-except
        # Don't log this as an error since we likely already logged the underlying API issue
        message = f"Skipping node count validation for project {gcp_project.project_id} due to API access issues"
        log.debug(message)


def count_autopilot_clusters(gcp_project: Project, result: Dict[str, int]):
    gcp = get_thread_local_gcp()
    for cluster in gcp.get_cached_clusters(gcp_project.project_id):
        if GCP.is_cluster_autopilot(cluster):
            result["autopilot_clusters"] += 1
            result["autopilot_nodes"] += GCP.get_autopilot_active_nodes(cluster)


def count_instances(gcp_project: Project, result: Dict[str, int]):
    gcp = get_thread_local_gcp()
    for _, response in gcp.list_instances(gcp_project.project_id):
        if response.instances:
            for instance in response.instances:
                typ = "kubenode" if GCP.is_vm_kubenode(instance) else "vm"
                state = "running" if GCP.is_vm_running(instance) else "terminated"
                key = f"{typ}s_{state}"
                result[key] += 1


def count_cloud_run_services(gcp_project: Project, result: Dict[str, int]):
    gcp = get_thread_local_gcp()
    services = gcp.list_cloud_run_services(gcp_project.project_id)
    result["cloud_run_services"] = len(services)


def count_cloud_run_jobs(gcp_project: Project, result: Dict[str, int]):
    gcp = get_thread_local_gcp()
    jobs = gcp.list_cloud_run_jobs(gcp_project.project_id)
    result["cloud_run_jobs"] = len(jobs)


def count_cloud_run_resources(gcp_project: Project, result: Dict[str, int]):
    """
    Count both Cloud Run services and jobs in a single operation.

    This combined function eliminates duplicate API calls and error messages
    since both services and jobs use the same underlying Cloud Run API.
    If the API is disabled, both counts will be set to 0.
    """
    try:
        gcp = get_thread_local_gcp()
        # Try services first
        services = gcp.list_cloud_run_services(gcp_project.project_id)
        result["cloud_run_services"] = len(services)

        # Only try jobs if services succeeded (same API, so if one works, both should)
        jobs = gcp.list_cloud_run_jobs(gcp_project.project_id)
        result["cloud_run_jobs"] = len(jobs)

    except Exception:
        # If Cloud Run API is disabled, both services and jobs are unavailable
        result["cloud_run_services"] = 0
        result["cloud_run_jobs"] = 0
        raise  # Re-raise for fail_safe() error handling and logging


def should_skip_project(project: Project) -> bool:
    """
    Determine if a project should be skipped during scanning based on filtering rules.

    Filtering rules (in order of precedence):
    1. System projects (sys-*) are skipped by default unless GCP_INCLUDE_SYSTEM_PROJECTS=true
    2. Include patterns (allowlist) - if set, only matching projects are processed
    3. Exclude patterns (denylist) - matching projects are skipped

    Returns True if the project should be skipped.
    """
    project_id = project.project_id

    # 1. System projects (default skip unless explicitly included)
    include_system = os.environ.get('GCP_INCLUDE_SYSTEM_PROJECTS', 'false').lower() == 'true'
    if project_id.startswith('sys-') and not include_system:
        log.info("Skipping system project: %s", project_id)
        return True

    # 2. Include patterns (allowlist - if set, only these patterns are processed)
    include_patterns = os.environ.get('GCP_INCLUDE_PATTERNS', '')
    if include_patterns:
        patterns = [p.strip() for p in include_patterns.split(',') if p.strip()]
        if not matches_any_pattern(project_id, patterns):
            log.info("Project %s doesn't match include patterns, skipping", project_id)
            return True

    # 3. Exclude patterns (denylist)
    exclude_patterns = os.environ.get('GCP_EXCLUDE_PATTERNS', '')
    if exclude_patterns:
        patterns = [p.strip() for p in exclude_patterns.split(',') if p.strip()]
        if matches_any_pattern(project_id, patterns):
            log.info("Project %s matches exclude pattern, skipping", project_id)
            return True

    return False


def matches_any_pattern(project_id: str, patterns: List[str]) -> bool:
    """
    Check if project_id matches any of the provided patterns using glob-style matching.

    Performs case-insensitive matching to handle environment variable patterns correctly.

    Args:
        project_id: The GCP project ID to check
        patterns: List of glob patterns (e.g., ['dev-*', 'test-*', '*-sandbox'])

    Returns:
        True if project_id matches any pattern, False otherwise
    """
    project_id_lower = project_id.lower()
    return any(fnmatch.fnmatch(project_id_lower, pattern.lower()) for pattern in patterns)


def process_project_batch(projects_batch: List[Project], batch_num: int, total_batches: int) -> Dict[str, Any]:
    """
    Process a batch of projects with thread-safe data collection.

    Returns:
        Dictionary with batch statistics: processed_count, skipped_count, rows
    """
    batch_stats = {
        'processed_count': 0,
        'skipped_count': 0,
        'rows': []
    }

    log.info("Processing batch %d/%d (%d projects)", batch_num, total_batches, len(projects_batch))

    # Process projects in this batch using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        # Submit all projects in this batch for processing (pre-filtered, so no skip check needed)
        future_to_project = {}
        for project in projects_batch:
            future = executor.submit(process_gcp_project, project)
            future_to_project[future] = project

        # Collect results as they complete
        for future in as_completed(future_to_project):
            project = future_to_project[future]
            try:
                row = future.result()
                if row:  # Non-empty result (successful processing)
                    batch_stats['rows'].append(row)
                    batch_stats['processed_count'] += 1
                else:  # Empty result (e.g., project in DELETE_REQUESTED state)
                    batch_stats['skipped_count'] += 1
            except Exception as exc:
                log.error("Error processing project %s: %s", project.display_name, exc)
                # Processing errors are tracked separately - don't count as skipped
                # The project was attempted but failed

    return batch_stats


def update_totals_threadsafe(rows: List[Dict], stats: Dict[str, int]) -> None:
    """Thread-safe update of global data and totals."""
    with data_lock:
        data.extend(rows)

    with totals_lock:
        for row in rows:
            for k in totals:
                if k != "project_id":
                    totals[k] += row[k]


data = []
service_disabled_calls = {}
headers = {
    "project_id": "Project ID",
    "kubenodes_running": "K8s Nodes (Running)",
    "kubenodes_terminated": "K8s Nodes (Terminated)",
    "vms_running": "VMs (Running)",
    "vms_terminated": "VMs (Terminated)",
    "autopilot_clusters": "Autopilot Clusters",
    "autopilot_nodes": "Autopilot Nodes (Running)",
    "cloud_run_services": "Cloud Run Services",
    "cloud_run_jobs": "Cloud Run Jobs",
}
totals = {
    "project_id": "totals",
    "kubenodes_running": 0,
    "kubenodes_terminated": 0,
    "vms_running": 0,
    "vms_terminated": 0,
    "autopilot_clusters": 0,
    "autopilot_nodes": 0,
    "cloud_run_services": 0,
    "cloud_run_jobs": 0,
}

main_gcp = GCP()

projects = list(main_gcp.projects())
if not projects:
    log.error("No GCP projects found")
    exit(1)  # pylint: disable=consider-using-sys-exit

# Track filtering statistics for summary
total_projects = 0
skipped_projects = 0
processed_projects = 0

log.info("Starting GCP project scan with parallel processing enabled")
log.info("Environment variables:")
log.info("  GCP_INCLUDE_SYSTEM_PROJECTS: %s", os.environ.get('GCP_INCLUDE_SYSTEM_PROJECTS', 'false'))
log.info("  GCP_INCLUDE_PATTERNS: %s", os.environ.get('GCP_INCLUDE_PATTERNS', '(not set)'))
log.info("  GCP_EXCLUDE_PATTERNS: %s", os.environ.get('GCP_EXCLUDE_PATTERNS', '(not set)'))
log.info("  GCP_THREADS: %d", THREADS)
log.info("  GCP_BATCH_SIZE: %d", BATCH_SIZE)
log.info("  GCP_API_DELAY: %.3fs", API_DELAY)

# Apply filtering to projects before batching for efficiency
filtered_projects = []
total_discovered_projects = len(projects)

log.info("Applying project filters...")
for project in projects:
    if should_skip_project(project):
        continue
    filtered_projects.append(project)

log.info("Project filtering complete:")
log.info("  Total projects discovered: %d", total_discovered_projects)
log.info("  Projects matching filters: %d", len(filtered_projects))
log.info("  Projects to be skipped: %d", total_discovered_projects - len(filtered_projects))

if not filtered_projects:
    log.error("No projects match the current filtering criteria")
    log.error("Consider adjusting your filter settings:")
    log.error("  GCP_INCLUDE_PATTERNS: %s", os.environ.get('GCP_INCLUDE_PATTERNS', '(not set)'))
    log.error("  GCP_EXCLUDE_PATTERNS: %s", os.environ.get('GCP_EXCLUDE_PATTERNS', '(not set)'))
    log.error("  GCP_INCLUDE_SYSTEM_PROJECTS: %s", os.environ.get('GCP_INCLUDE_SYSTEM_PROJECTS', 'false'))
    exit(1)  # pylint: disable=consider-using-sys-exit

# Process filtered projects in batches with parallel execution
total_projects = len(filtered_projects)
processed_projects = 0
post_filter_skipped = 0  # Projects skipped after filtering (e.g., DELETE_REQUESTED)

# Split filtered projects into batches
batches = [filtered_projects[i:i + BATCH_SIZE] for i in range(0, len(filtered_projects), BATCH_SIZE)]
total_batches = len(batches)

log.info("Processing %d projects in %d batches", total_projects, total_batches)

for batch_num, batch in enumerate(batches, 1):
    # Process this batch
    batch_stats = process_project_batch(batch, batch_num, total_batches)

    # Update global statistics and data
    update_totals_threadsafe(batch_stats['rows'], batch_stats)
    processed_projects += batch_stats['processed_count']
    post_filter_skipped += batch_stats['skipped_count']

    # Log batch completion
    log.info("Batch %d/%d complete: %d processed, %d skipped",
             batch_num, total_batches,
             batch_stats['processed_count'],
             batch_stats['skipped_count'])

    # Add delay between batches (except for the last batch)
    if batch_num < total_batches and BATCH_DELAY > 0:
        log.debug("Waiting %.1fs before next batch...", BATCH_DELAY)
        time.sleep(BATCH_DELAY)

# Log final processing summary
skipped_by_filters = total_discovered_projects - total_projects
processing_errors = max(0, total_projects - processed_projects - post_filter_skipped)

log.info("Processing summary:")
log.info("  Total projects discovered: %d", total_discovered_projects)
log.info("  Projects matching filters: %d", total_projects)
log.info("  Projects skipped by filters: %d", skipped_by_filters)
log.info("  Projects successfully processed: %d", processed_projects)
log.info("  Projects skipped during processing: %d", post_filter_skipped)
log.info("  Projects with processing errors: %d", processing_errors)

data.append(totals)

# Output our results
print(tabulate(data, headers=headers, tablefmt="grid", maxheadercolwidths=[10, 15, 15, 10, 15, 15, 15, 15, 12]))

with open("gcp-benchmark.csv", "w", newline="", encoding="utf-8") as csv_file:
    csv_writer = csv.DictWriter(csv_file, fieldnames=headers.keys())
    csv_writer.writeheader()
    csv_writer.writerows(data)

log.info("CSV file saved to: ./gcp-benchmark.csv")

if service_disabled_calls:
    MSG = (
        "Some API service calls were disabled in certain projects, preventing data processing. "
        "These APIs might be intentionally disabled in your environment. "
        "Details have been captured and saved to: ./gcp-exceptions.txt for your review."
    )
    log.warning(MSG)

    with open("gcp-exceptions.txt", "w", encoding="utf-8") as f:
        for project, messages in service_disabled_calls.items():
            f.write(f"Project ID: {project}\n")
            for msg in set(messages):
                f.write(f"- {msg}\n")
            f.write("\n")

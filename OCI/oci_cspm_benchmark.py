# pylint: disable=C0301,C0302,E0401,W1203,W0718
# flake8: noqa: E501
"""
oci_cspm_benchmark.py

Assists with provisioning calculations by retrieving a count of
all billable resources attached to an OCI tenancy.
"""

import argparse
import csv
import concurrent.futures
import threading
import time
import json
import os
import random
import signal
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union, Tuple

import oci
import oci.config
import oci.exceptions
import oci.pagination
import oci.auth.signers
import oci.identity
import oci.core
import oci.container_engine
import oci.container_instances
import oci.functions
import oci.database
import oci.mysql
import oci.object_storage
from tabulate import tabulate


# Global data structures
data: List[Dict[str, Any]] = []
headers = {
    "tenancy_id": "OCI Tenancy ID",
    "compartment_id": "Compartment OCID",
    "compartment_name": "Compartment Name",
    "region": "Region",
    "vms_running": "Running VMs",
    "vms_stopped": "Stopped VMs",
    "oke_clusters": "OKE Clusters",
    "oke_nodes": "OKE Managed Nodes",
    "oke_virtual_nodes": "OKE Virtual Nodes",
    "container_instances": "Container Instances",
    "functions": "Functions",
    "autonomous_dbs": "Autonomous Databases",
    "mysql_dbs": "MySQL DB Systems",
    "buckets": "Object Storage Buckets",
}
totals: Dict[str, Union[str, int]] = {
    "tenancy_id": "totals",
    "compartment_id": "totals",
    "compartment_name": "totals",
    "region": "totals",
    "vms_running": 0,
    "vms_stopped": 0,
    "oke_clusters": 0,
    "oke_nodes": 0,
    "oke_virtual_nodes": 0,
    "container_instances": 0,
    "functions": 0,
    "autonomous_dbs": 0,
    "mysql_dbs": 0,
    "buckets": 0,
}

# Thread-safe locks
data_lock = threading.Lock()
totals_lock = threading.Lock()
console_lock = threading.Lock()

# Global configuration — initialized in main()
args: Optional[argparse.Namespace] = None
log: Optional[logging.Logger] = None


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("oci_cspm")


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

def setup_signal_handlers() -> None:
    """Map SIGINT and SIGTERM to KeyboardInterrupt so main() can do cleanup."""
    def _handler(signum, _frame):
        if log:
            log.info(f"Received signal {signum}, initiating graceful shutdown...")
        raise KeyboardInterrupt("Shutdown signal received")

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


# ---------------------------------------------------------------------------
# Progress tracker
# ---------------------------------------------------------------------------

class ProgressTracker:
    """
    Persists completed/failed (compartment_id, region) pairs to a JSON file so
    an interrupted scan can be resumed without re-scanning already-finished pairs.

    File format:
    {
      "completed_pairs": [["ocid...", "us-ashburn-1"], ...],
      "failed_pairs":    [["ocid...", "eu-frankfurt-1"], ...],
      "start_time":      "2024-01-01T00:00:00+00:00",
      "total_pairs":     500,
      "last_updated":    "2024-01-01T01:23:45+00:00"
    }
    """

    def __init__(self, progress_file: str):
        self.progress_file = progress_file
        self._lock = threading.Lock()
        self.completed: set = set()
        self.failed: set = set()
        self.start_time: Optional[str] = None
        self.total_pairs: int = 0
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.progress_file):
            return
        try:
            with open(self.progress_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self.completed = {tuple(p) for p in saved.get("completed_pairs", [])}
            self.failed = {tuple(p) for p in saved.get("failed_pairs", [])}
            self.start_time = saved.get("start_time")
            self.total_pairs = saved.get("total_pairs", 0)
            msg = f"Resumed from progress file: {len(self.completed)} pairs already complete"
            if log:
                log.info(msg)
            else:
                print(msg)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            msg = f"Could not parse progress file {self.progress_file}: {exc} — starting fresh"
            if log:
                log.warning(msg)
            else:
                print(msg)

    def _save(self) -> None:
        try:
            payload = {
                "completed_pairs": [list(p) for p in self.completed],
                "failed_pairs": [list(p) for p in self.failed],
                "start_time": self.start_time,
                "total_pairs": self.total_pairs,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
            with open(self.progress_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except OSError as exc:
            if log:
                log.error(f"Could not save progress to {self.progress_file}: {exc}")

    def should_skip(self, compartment_id: str, region: str) -> bool:
        return (compartment_id, region) in self.completed

    def mark_completed(self, compartment_id: str, region: str) -> None:
        with self._lock:
            self.completed.add((compartment_id, region))
            self.failed.discard((compartment_id, region))
            self._save()

    def mark_failed(self, compartment_id: str, region: str) -> None:
        with self._lock:
            self.failed.add((compartment_id, region))
            self._save()

    def remove(self) -> None:
        try:
            os.remove(self.progress_file)
        except OSError:
            pass

    def print_resume_guidance(self) -> None:
        completed_count = len(self.completed)
        failed_count = len(self.failed)
        remaining = self.total_pairs - completed_count

        print("\n" + "=" * 70)
        print("PROGRESS SAVED - SCAN CAN BE RESUMED")
        print("=" * 70)
        print(f"  Completed pairs : {completed_count}")
        print(f"  Failed pairs    : {failed_count}")
        print(f"  Remaining pairs : {remaining}")
        if self.total_pairs > 0:
            pct = completed_count / self.total_pairs * 100
            print(f"  Progress        : {pct:.1f}%")
        print(f"\n  Progress file   : {self.progress_file}")
        print("\nTo resume, run the same command again.")
        print("The script will skip already-completed pairs automatically.")
        print("=" * 70)


# ---------------------------------------------------------------------------
# Retry handler
# ---------------------------------------------------------------------------

class RetryHandler:
    """Exponential backoff retry for OCI SDK calls."""

    RETRYABLE_HTTP = {429, 500, 503, 504}
    RETRYABLE_CODES = {
        "TooManyRequests",
        "InternalError",
        "ServiceUnavailable",
        "RequestTimeout",
        "ConnectionError",
    }

    @staticmethod
    def exponential_backoff(attempt: int, base: float = 1.0, max_delay: float = 120.0) -> float:
        delay = min(base * (2 ** attempt), max_delay)
        delay *= 0.5 + random.random() * 0.5  # nosec B311
        return delay

    @classmethod
    def should_retry(cls, exc: Exception, attempt: int, max_retries: int) -> bool:
        if attempt >= max_retries:
            return False
        if isinstance(exc, oci.exceptions.ServiceError):
            return exc.status in cls.RETRYABLE_HTTP or exc.code in cls.RETRYABLE_CODES
        if isinstance(exc, oci.exceptions.RequestException):
            return True
        return False

    def retry_with_backoff(self, func, max_retries: int = 5, operation_name: str = "operation"):
        for attempt in range(max_retries + 1):
            try:
                return func()
            except Exception as exc:
                if not self.should_retry(exc, attempt, max_retries):
                    raise
                delay = self.exponential_backoff(attempt)
                if log:
                    log.debug(f"Retry {attempt + 1}/{max_retries} for {operation_name} in {delay:.2f}s: {exc}")
                time.sleep(delay)
        raise RuntimeError(f"Max retries exceeded for {operation_name}")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def build_config_and_signer() -> Tuple[dict, Optional[Any]]:
    """Return (config, signer). Prefers instance principal, falls back to config file."""
    # Try instance principal first (works on OCI Compute instances without a config file)
    try:
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        tenancy_id = signer.get_tenancy_id()
        region = signer.initialize_and_return_region()
        config = {"tenancy": tenancy_id, "region": region}
        if log:
            log.info("Authenticated via Instance Principal")
        return config, signer
    except oci.exceptions.RequestException as exc:
        if log:
            log.debug(f"Instance principal not available (network/metadata unreachable): {exc}")
    except Exception as exc:  # pylint: disable=broad-except
        # Instance principal fails fast on non-OCI hosts; swallow and try config file
        if log:
            log.debug(f"Instance principal not available: {type(exc).__name__}: {exc}")

    # Fall back to config file
    profile = args.profile if args else "DEFAULT"
    config = oci.config.from_file(profile_name=profile)
    oci.config.validate_config(config)
    if log:
        log.info(f"Authenticated via config file profile '{profile}'")
    return config, None


# ---------------------------------------------------------------------------
# Pagination helper
# ---------------------------------------------------------------------------

def paginated_list(list_fn, **kwargs) -> List[Any]:
    """Exhaust all pages from any OCI list_* call."""
    results = []
    page = None
    while True:
        if page:
            kwargs["page"] = page
        response = list_fn(**kwargs)
        results.extend(response.data)
        page = response.headers.get("opc-next-page")
        if not page:
            break
    return results


# ---------------------------------------------------------------------------
# OCI client handle
# ---------------------------------------------------------------------------

class OCIHandle:
    """Wraps OCI config/signer and provides lazy, region-aware client creation."""

    def __init__(self, config: dict, signer=None):
        self.config = config
        self.signer = signer
        self.tenancy_id = config["tenancy"]
        self._identity: Optional[oci.identity.IdentityClient] = None
        self._namespace: Optional[str] = None
        self._compartment_ids: Optional[List[str]] = None
        self._compartment_names: Optional[Dict[str, str]] = None
        self._regions: Optional[List[str]] = None
        self._retry = RetryHandler()
        # Locks protecting lazy-initialized attributes accessed from multiple threads
        self._identity_lock = threading.Lock()
        self._namespace_lock = threading.Lock()
        self._compartment_lock = threading.Lock()
        self._regions_lock = threading.Lock()

    # -- identity client (region-agnostic) -----------------------------------

    @property
    def identity(self) -> oci.identity.IdentityClient:
        if self._identity is None:
            with self._identity_lock:
                if self._identity is None:  # double-checked locking
                    if self.signer:
                        self._identity = oci.identity.IdentityClient(config={}, signer=self.signer)
                    else:
                        self._identity = oci.identity.IdentityClient(self.config)
        return self._identity

    # -- compartment enumeration ---------------------------------------------

    def get_all_compartment_ids(self) -> List[str]:
        """Return OCIDs of all ACTIVE compartments accessible in this tenancy, including the root."""
        if self._compartment_ids is not None:
            return self._compartment_ids

        with self._compartment_lock:
            if self._compartment_ids is not None:  # another thread may have populated it
                return self._compartment_ids

            def fetch():
                return paginated_list(
                    self.identity.list_compartments,
                    compartment_id=self.tenancy_id,
                    compartment_id_in_subtree=True,
                    lifecycle_state="ACTIVE",
                    access_level="ACCESSIBLE",
                )

            compartments = self._retry.retry_with_backoff(fetch, args.max_retries, "list_compartments")
            names = {c.id: c.name for c in compartments}
            names[self.tenancy_id] = "root"
            self._compartment_names = names
            # Root tenancy is itself a valid compartment for resource scanning
            self._compartment_ids = [self.tenancy_id] + [c.id for c in compartments]

        return self._compartment_ids

    def compartment_name(self, compartment_id: str) -> str:
        if self._compartment_names is None:
            self.get_all_compartment_ids()  # populates _compartment_names as a side effect
        return (self._compartment_names or {}).get(compartment_id, compartment_id)

    # -- region enumeration --------------------------------------------------

    def get_subscribed_regions(self) -> List[str]:
        """Return region name strings the tenancy is subscribed to."""
        if self._regions is not None:
            return self._regions

        with self._regions_lock:
            if self._regions is not None:
                return self._regions

            def fetch():
                response = self.identity.list_region_subscriptions(self.tenancy_id)
                return [r.region_name for r in response.data if r.status == "READY"]

            self._regions = self._retry.retry_with_backoff(fetch, args.max_retries, "list_region_subscriptions")

        return self._regions

    # -- per-region client factory -------------------------------------------

    def _make_client(self, client_class, region: str):
        """Instantiate a region-specific OCI client."""
        if self.signer:
            client = client_class(config={}, signer=self.signer)
            client.base_client.set_region(region)
            return client
        region_config = dict(self.config)
        region_config["region"] = region
        return client_class(region_config)

    # -- object storage namespace (tenancy-scoped, fetched once) -------------

    def object_storage_namespace(self, region: str) -> str:
        if self._namespace is None:
            with self._namespace_lock:
                if self._namespace is None:  # double-checked locking
                    client = self._make_client(oci.object_storage.ObjectStorageClient, region)
                    self._namespace = client.get_namespace().data
        return self._namespace

    # -- resource counting ---------------------------------------------------

    def count_resources(self, compartment_id: str, region: str) -> Dict[str, int]:
        """Count all tracked resource types in a single (compartment, region) pair."""
        row: Dict[str, int] = {
            "vms_running": 0,
            "vms_stopped": 0,
            "oke_clusters": 0,
            "oke_nodes": 0,
            "oke_virtual_nodes": 0,
            "container_instances": 0,
            "functions": 0,
            "autonomous_dbs": 0,
            "mysql_dbs": 0,
            "buckets": 0,
        }

        retry = self._retry

        # -- Compute instances -----------------------------------------------
        compute = self._make_client(oci.core.ComputeClient, region)

        def _list_instances():
            return paginated_list(compute.list_instances, compartment_id=compartment_id)

        try:
            instances = retry.retry_with_backoff(
                _list_instances, args.max_retries, f"list_instances/{compartment_id}/{region}"
            )
            for inst in instances:
                if inst.lifecycle_state in ("TERMINATING", "TERMINATED"):
                    continue
                if inst.lifecycle_state == "RUNNING":
                    row["vms_running"] += 1
                else:
                    row["vms_stopped"] += 1
        except oci.exceptions.ServiceError as exc:
            if exc.status not in (401, 404):
                if log:
                    log.warning(f"list_instances {compartment_id}/{region}: {exc.status} {exc.code}")

        # -- OKE clusters and node pools ------------------------------------
        ce = self._make_client(oci.container_engine.ContainerEngineClient, region)

        def _list_clusters():
            return paginated_list(ce.list_clusters, compartment_id=compartment_id)

        def _list_node_pools():
            return paginated_list(ce.list_node_pools, compartment_id=compartment_id)

        try:
            clusters = retry.retry_with_backoff(
                _list_clusters, args.max_retries, f"list_clusters/{compartment_id}/{region}"
            )
            row["oke_clusters"] = sum(1 for c in clusters if c.lifecycle_state == "ACTIVE")
        except oci.exceptions.ServiceError as exc:
            if exc.status not in (401, 404):
                if log:
                    log.warning(f"list_clusters {compartment_id}/{region}: {exc.status} {exc.code}")

        try:
            node_pools = retry.retry_with_backoff(
                _list_node_pools, args.max_retries, f"list_node_pools/{compartment_id}/{region}"
            )
            for pool in node_pools:
                if pool.lifecycle_state != "ACTIVE":
                    continue
                # Virtual node pools (serverless) have a separate node_pool_type attribute.
                # OCI SDK uses "VIRTUAL" vs "MANAGED". getattr guards against SDK version gaps.
                pool_type = getattr(pool, "node_pool_type", None)
                if pool_type is None:
                    # Attribute absent in older SDK versions — treat as managed
                    pool_type = "MANAGED"
                    if log:
                        log.debug(f"node_pool_type absent on pool {pool.id}, defaulting to MANAGED")
                size = 0
                if pool.node_config_details:
                    size = pool.node_config_details.size or 0
                if pool_type == "VIRTUAL":
                    row["oke_virtual_nodes"] += size
                else:
                    row["oke_nodes"] += size
        except oci.exceptions.ServiceError as exc:
            if exc.status not in (401, 404):
                if log:
                    log.warning(f"list_node_pools {compartment_id}/{region}: {exc.status} {exc.code}")

        # -- Container Instances --------------------------------------------
        try:
            ci_client = self._make_client(oci.container_instances.ContainerInstanceClient, region)

            def _list_cis():
                return paginated_list(ci_client.list_container_instances, compartment_id=compartment_id)

            cis = retry.retry_with_backoff(
                _list_cis, args.max_retries, f"list_container_instances/{compartment_id}/{region}"
            )
            # The list response returns ContainerInstanceSummary objects.
            # container_count is a documented field on ContainerInstanceSummary.
            # Each ContainerInstance can hold multiple containers (like a pod).
            row["container_instances"] = sum(
                getattr(ci, "container_count", 1) or 1
                for ci in cis
                if ci.lifecycle_state == "ACTIVE"
            )
        except oci.exceptions.ServiceError as exc:
            if exc.status not in (401, 404):
                if log:
                    log.warning(f"list_container_instances {compartment_id}/{region}: {exc.status} {exc.code}")

        # -- Functions -------------------------------------------------------
        try:
            fn_client = self._make_client(oci.functions.FunctionsManagementClient, region)

            def _list_apps():
                return paginated_list(fn_client.list_applications, compartment_id=compartment_id)

            apps = retry.retry_with_backoff(
                _list_apps, args.max_retries, f"list_applications/{compartment_id}/{region}"
            )
            for app in apps:
                if app.lifecycle_state != "ACTIVE":
                    continue

                def _list_fns(app_id=app.id):
                    return paginated_list(fn_client.list_functions, application_id=app_id)

                try:
                    fns = retry.retry_with_backoff(
                        _list_fns, args.max_retries, f"list_functions/{app.id}"
                    )
                    row["functions"] += sum(1 for f in fns if f.lifecycle_state == "ACTIVE")
                except oci.exceptions.ServiceError as exc:
                    if exc.status not in (401, 404):
                        if log:
                            log.warning(f"list_functions {app.id}: {exc.status} {exc.code}")
        except oci.exceptions.ServiceError as exc:
            if exc.status not in (401, 404):
                if log:
                    log.warning(f"list_applications {compartment_id}/{region}: {exc.status} {exc.code}")

        # -- Autonomous Databases --------------------------------------------
        try:
            db_client = self._make_client(oci.database.DatabaseClient, region)

            def _list_adbs():
                return paginated_list(db_client.list_autonomous_databases, compartment_id=compartment_id)

            adbs = retry.retry_with_backoff(
                _list_adbs, args.max_retries, f"list_autonomous_databases/{compartment_id}/{region}"
            )
            row["autonomous_dbs"] = sum(
                1 for db in adbs
                if db.lifecycle_state not in ("TERMINATING", "TERMINATED")
            )
        except oci.exceptions.ServiceError as exc:
            if exc.status not in (401, 404):
                if log:
                    log.warning(f"list_autonomous_databases {compartment_id}/{region}: {exc.status} {exc.code}")

        # -- MySQL DB Systems ------------------------------------------------
        # OCI SDK uses MysqlaasClient (the service was formerly called "MySQL as a Service").
        # Older SDK versions may expose DbSystemClient instead — try both.
        try:
            _mysql_cls = getattr(oci.mysql, "MysqlaasClient", None) or getattr(oci.mysql, "DbSystemClient", None)
            if _mysql_cls is None:
                raise AttributeError("Neither MysqlaasClient nor DbSystemClient found in oci.mysql")
            mysql_client = self._make_client(_mysql_cls, region)

            def _list_mysql():
                return paginated_list(mysql_client.list_db_systems, compartment_id=compartment_id)

            dbs = retry.retry_with_backoff(
                _list_mysql, args.max_retries, f"list_db_systems/{compartment_id}/{region}"
            )
            row["mysql_dbs"] = sum(
                1 for db in dbs
                if db.lifecycle_state not in ("DELETING", "DELETED")
            )
        except oci.exceptions.ServiceError as exc:
            if exc.status not in (401, 404):
                if log:
                    log.warning(f"list_db_systems {compartment_id}/{region}: {exc.status} {exc.code}")

        # -- Object Storage Buckets -----------------------------------------
        try:
            os_client = self._make_client(oci.object_storage.ObjectStorageClient, region)
            namespace = self.object_storage_namespace(region)

            def _list_buckets():
                return paginated_list(
                    os_client.list_buckets,
                    namespace_name=namespace,
                    compartment_id=compartment_id,
                )

            buckets = retry.retry_with_backoff(
                _list_buckets, args.max_retries, f"list_buckets/{compartment_id}/{region}"
            )
            row["buckets"] = len(buckets)
        except oci.exceptions.ServiceError as exc:
            if exc.status not in (401, 404):
                if log:
                    log.warning(f"list_buckets {compartment_id}/{region}: {exc.status} {exc.code}")

        return row


# ---------------------------------------------------------------------------
# Per-(compartment, region) scan worker
# ---------------------------------------------------------------------------

def scan_pair(
    handle: OCIHandle,
    compartment_id: str,
    region: str,
    progress: ProgressTracker,
) -> Optional[Dict[str, Any]]:
    """Scan one (compartment, region) pair, update progress, and return a data row."""
    if args.dry_run:
        with console_lock:
            print(f"  [dry-run] Would scan compartment={handle.compartment_name(compartment_id)} region={region}")
        return None

    if args.api_delay > 0:
        time.sleep(args.api_delay)

    try:
        counts = handle.count_resources(compartment_id, region)
    except Exception as exc:
        if log:
            log.error(f"Failed scanning {compartment_id}/{region}: {exc}")
        progress.mark_failed(compartment_id, region)
        return None

    progress.mark_completed(compartment_id, region)

    row = {
        "tenancy_id": handle.tenancy_id,
        "compartment_id": compartment_id,
        "compartment_name": handle.compartment_name(compartment_id),
        "region": region,
        **counts,
    }
    return row


# ---------------------------------------------------------------------------
# Output helper
# ---------------------------------------------------------------------------

def write_output(csv_filename: str) -> None:
    """Write the current data (plus totals) to CSV and print the grid table."""
    output_rows = data + [totals]
    print(tabulate(output_rows, headers=headers, tablefmt="grid"))
    with open(csv_filename, "w", newline="", encoding="utf-8") as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=headers.keys())
        csv_writer.writeheader()
        csv_writer.writerows(output_rows)
    print(f"\nCSV file stored in: ./cloud-benchmark/{csv_filename}")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OCI tenancy resource estimator")

    parser.add_argument(
        "--profile",
        default=os.environ.get("OCI_PROFILE", "DEFAULT"),
        help="OCI config file profile name (default: DEFAULT, env: OCI_PROFILE).",
    )
    parser.add_argument(
        "--tenancy-id",
        default=os.environ.get("OCI_TENANCY_OCID"),
        help="Override tenancy OCID (default: from config, env: OCI_TENANCY_OCID).",
    )
    parser.add_argument(
        "--regions",
        default=os.environ.get("OCI_REGIONS"),
        help="Comma-separated list of regions to scan (default: all subscribed, env: OCI_REGIONS).",
    )
    parser.add_argument(
        "--skip-compartments",
        default=os.environ.get("OCI_SKIP_COMPARTMENTS"),
        help="Comma-separated compartment OCIDs to exclude (env: OCI_SKIP_COMPARTMENTS).",
    )
    parser.add_argument(
        "--include-compartments",
        default=os.environ.get("OCI_INCLUDE_COMPARTMENTS"),
        help="Comma-separated compartment OCIDs to include exclusively (env: OCI_INCLUDE_COMPARTMENTS).",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=int(os.environ.get("OCI_THREADS", "5")),
        help="Parallel (compartment, region) workers (default: 5, env: OCI_THREADS).",
    )
    parser.add_argument(
        "--api-delay",
        type=float,
        default=float(os.environ.get("OCI_API_DELAY", "0.05")),
        help="Seconds to wait between API calls (default: 0.05, env: OCI_API_DELAY).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=int(os.environ.get("OCI_MAX_RETRIES", "5")),
        help="Maximum retry attempts per operation (default: 5, env: OCI_MAX_RETRIES).",
    )
    parser.add_argument(
        "--resume-file",
        default=os.environ.get("OCI_RESUME_FILE", "oci_benchmark_progress.json"),
        help="File to store/resume scan progress (default: oci_benchmark_progress.json, env: OCI_RESUME_FILE).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=os.environ.get("OCI_DRY_RUN", "").lower() == "true",
        help="Print what would be scanned without making API calls (env: OCI_DRY_RUN).",
    )

    parsed = parser.parse_args()

    if parsed.threads < 1 or parsed.threads > 50:
        parser.error("--threads must be between 1 and 50")
    if parsed.api_delay < 0 or parsed.api_delay > 10:
        parser.error("--api-delay must be between 0 and 10")
    if parsed.max_retries < 0 or parsed.max_retries > 20:
        parser.error("--max-retries must be between 0 and 20")

    return parsed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    global args, log  # pylint: disable=W0603

    args = parse_args()
    log = setup_logging()
    setup_signal_handlers()

    log.info("Starting OCI CSPM benchmark")
    log.info(f"  Profile:      {args.profile}")
    log.info(f"  Threads:      {args.threads}")
    log.info(f"  API delay:    {args.api_delay}s")
    log.info(f"  Max retries:  {args.max_retries}")
    log.info(f"  Resume file:  {args.resume_file}")
    log.info(f"  Dry run:      {args.dry_run}")

    # --- Authentication ---
    try:
        config, signer = build_config_and_signer()
    except (oci.exceptions.ConfigFileNotFound, oci.exceptions.ProfileNotFound, oci.exceptions.InvalidConfig) as exc:
        print(f"OCI authentication failed: {exc}")
        print("Run 'oci setup config' to configure credentials, or set OCI_PROFILE.")
        raise SystemExit(1)

    # Allow CLI override of tenancy OCID
    if args.tenancy_id:
        config["tenancy"] = args.tenancy_id

    handle = OCIHandle(config, signer)

    # --- Enumerate compartments ---
    print("Enumerating compartments...")
    try:
        all_compartment_ids = handle.get_all_compartment_ids()
    except Exception as exc:
        print(f"Failed to enumerate compartments: {exc}")
        raise SystemExit(1)

    # Apply compartment filters
    if args.include_compartments:
        include_set = {c.strip() for c in args.include_compartments.split(",")}
        compartment_ids = [c for c in all_compartment_ids if c in include_set]
        if not compartment_ids:
            print("No compartments matched --include-compartments filter.")
            raise SystemExit(1)
    elif args.skip_compartments:
        skip_set = {c.strip() for c in args.skip_compartments.split(",")}
        compartment_ids = [c for c in all_compartment_ids if c not in skip_set]
    else:
        compartment_ids = all_compartment_ids

    log.info(f"Compartments to scan: {len(compartment_ids)}")

    # --- Enumerate regions ---
    print("Enumerating subscribed regions...")
    try:
        if args.regions:
            regions = [r.strip() for r in args.regions.split(",")]
        else:
            regions = handle.get_subscribed_regions()
    except Exception as exc:
        print(f"Failed to enumerate regions: {exc}")
        raise SystemExit(1)

    log.info(f"Regions to scan: {len(regions)} — {', '.join(regions)}")

    # Build the full list of (compartment_id, region) pairs
    all_pairs = [(c, r) for r in regions for c in compartment_ids]
    total_pairs = len(all_pairs)
    print(f"Scanning {len(compartment_ids)} compartments × {len(regions)} regions = {total_pairs} scan units")

    if args.dry_run:
        for compartment_id, region in all_pairs:
            print(f"  [dry-run] {handle.compartment_name(compartment_id)} / {region}")
        return

    # --- Progress tracking ---
    progress = ProgressTracker(args.resume_file)
    progress.total_pairs = total_pairs
    if progress.start_time is None:
        progress.start_time = datetime.now(timezone.utc).isoformat()

    # Skip pairs already completed in a previous run
    pending_pairs = [(c, r) for c, r in all_pairs if not progress.should_skip(c, r)]
    skipped = total_pairs - len(pending_pairs)
    if skipped:
        print(f"  Skipping {skipped} already-completed pairs, {len(pending_pairs)} remaining")

    # Prepare the timestamped output filename once so partial + final writes use the same file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"oci-benchmark-{timestamp}.csv"

    # --- Parallel scan ---
    completed = 0
    interrupted = False

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=args.threads)
    try:
        future_to_pair = {
            executor.submit(scan_pair, handle, c, r, progress): (c, r)
            for c, r in pending_pairs
        }

        for future in concurrent.futures.as_completed(future_to_pair):
            compartment_id, region = future_to_pair[future]
            completed += 1
            try:
                row = future.result()
                if row is None:
                    continue

                with data_lock:
                    data.append(row)

                with totals_lock:
                    for key in totals:
                        if key not in ("tenancy_id", "compartment_id", "compartment_name", "region"):
                            totals[key] += row.get(key, 0)

                if completed % 50 == 0 or completed == len(pending_pairs):
                    with console_lock:
                        print(f"  Progress: {completed}/{len(pending_pairs)} scan units complete")

            except Exception as exc:
                if log:
                    log.error(f"Error scanning {compartment_id}/{region}: {exc}")

    except KeyboardInterrupt:
        interrupted = True
        print("\nScan interrupted. Cancelling queued work...")
    finally:
        # cancel_futures drops queued-but-not-started work; in-flight threads finish normally.
        # This runs before __exit__ would have, so partial results are available immediately.
        executor.shutdown(wait=True, cancel_futures=True)

    if interrupted:
        if data:
            print(f"Writing partial results ({len(data)} rows collected)...")
            write_output(csv_filename)
        progress.print_resume_guidance()
        return

    # --- Clean completion ---
    write_output(csv_filename)

    # Remove progress file only when there are no failures — failed pairs can be retried
    if not progress.failed:
        progress.remove()
        log.info("Progress file cleaned up (all pairs completed successfully)")
    else:
        log.warning(f"{len(progress.failed)} pair(s) failed — progress file retained for resume")
        progress.print_resume_guidance()


if __name__ == "__main__":
    main()

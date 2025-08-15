# pylint: disable=C0301,C0302,E0401,W1203,W0718
# flake8: noqa: E501
"""
aws-cspm-benchmark-enhanced.py

Enhanced version with rate limiting, backoff, and timeout handling for large-scale deployments.
Assists with provisioning calculations by retrieving a count of
all billable resources attached to an AWS account.
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
from typing import Dict, List, Optional, Any, Union
import boto3
import botocore
from botocore.config import Config


# Global data structures
data: List[Dict[str, Any]] = []
headers = {
    "account_id": "AWS Account ID",
    "region": "Region",
    "vms_terminated": "Terminated VMs",
    "vms_running": "Running VMs",
    "kubenodes_terminated": "Terminated Kubernetes Nodes",
    "kubenodes_running": "Running Kubernetes Nodes",
    "fargate_profiles": "Active EKS Fargate Profiles",
    "fargate_tasks": "ECS Service Fargate Tasks",
}
totals: Dict[str, Union[str, int]] = {
    "region": "TOTAL",
    "account_id": "TOTAL",
    "vms_terminated": 0,
    "vms_running": 0,
    "kubenodes_terminated": 0,
    "kubenodes_running": 0,
    "fargate_profiles": 0,
    "fargate_tasks": 0,
}

# Thread-safe data structures
data_lock = threading.Lock()
totals_lock = threading.Lock()
progress_lock = threading.Lock()
console_lock = threading.Lock()  # For synchronized console output

# Progress tracking
progress_state: Dict[str, Any] = {
    "completed_accounts": set(),
    "failed_accounts": set(),
    "start_time": None,
    "total_accounts": 0,
    "current_batch": 0,
}

# Global configuration - will be initialized in main()
args: Optional[argparse.Namespace] = None
logger: Optional[logging.Logger] = None


class ErrorCollector:
    """Thread-safe error collection system to defer error output until after progress completes on each account"""

    def __init__(self):
        self.errors = []
        self.lock = threading.Lock()

    def add_error(self, error_msg, context=None):
        """Add an error message with optional context"""
        with self.lock:
            error_entry = {
                "message": error_msg,
                "context": context or {},
                "timestamp": time.time(),
            }
            self.errors.append(error_entry)

    def add_retry_message(self, operation_name, attempt, max_retries, delay, error):  # pylint: disable=R0913,R0917
        """Add a retry message"""
        msg = f"Retry {attempt + 1}/{max_retries} for {operation_name} in {delay:.2f}s: {error}"
        self.add_error(msg, {"type": "retry", "operation": operation_name})

    def add_timeout_error(self, operation, region=None, account=None):
        """Add a timeout error"""
        msg = f"Timeout processing {operation}"
        if region:
            msg += f" in {region}"
        context = {"type": "timeout", "operation": operation}
        if region:
            context["region"] = region
        if account:
            context["account"] = account
        self.add_error(msg, context)

    def add_processing_error(self, operation, region, error, account=None):
        """Add a processing error"""
        msg = f"Error processing {operation} in {region}: {error}"
        context = {"type": "processing", "operation": operation, "region": region}
        if account:
            context["account"] = account
        self.add_error(msg, context)

    def get_errors(self):
        """Get all collected errors"""
        with self.lock:
            return self.errors.copy()

    def clear_errors(self):
        """Clear all collected errors"""
        with self.lock:
            self.errors.clear()

    def has_errors(self):
        """Check if there are any errors collected"""
        with self.lock:
            return len(self.errors) > 0

    def display_errors(self, max_errors=10):  # pylint: disable=R0912
        """Display collected errors in an organized format"""
        errors = self.get_errors()
        if not errors:
            return

        print(f"\n⚠️  Collected {len(errors)} error(s) during processing:")

        # Group errors by type
        retry_errors = [
            e for e in errors if e.get("context", {}).get("type") == "retry"
        ]
        timeout_errors = [
            e for e in errors if e.get("context", {}).get("type") == "timeout"
        ]
        processing_errors = [
            e for e in errors if e.get("context", {}).get("type") == "processing"
        ]
        other_errors = [
            e
            for e in errors
            if e.get("context", {}).get("type")
            not in ["retry", "timeout", "processing"]
        ]

        # Display errors by category
        if timeout_errors:
            print(f"\n🕐 Timeout Errors ({len(timeout_errors)}):")
            for error in timeout_errors[:max_errors]:
                print(f"   • {error['message']}")
            if len(timeout_errors) > max_errors:
                print(
                    f"   ... and {len(timeout_errors) - max_errors} more timeout errors"
                )

        if processing_errors:
            print(f"\n🔧 Processing Errors ({len(processing_errors)}):")
            for error in processing_errors[:max_errors]:
                print(f"   • {error['message']}")
            if len(processing_errors) > max_errors:
                print(
                    f"   ... and {len(processing_errors) - max_errors} more processing errors"
                )

        if retry_errors:
            print(f"\n🔄 Retry Messages ({len(retry_errors)}):")
            for error in retry_errors[
                :3
            ]:  # Show fewer retry messages as they're verbose
                print(f"   • {error['message']}")
            if len(retry_errors) > 3:
                print(f"   ... and {len(retry_errors) - 3} more retry messages")

        if other_errors:
            print(f"\n❓ Other Errors ({len(other_errors)}):")
            for error in other_errors[:max_errors]:
                print(f"   • {error['message']}")
            if len(other_errors) > max_errors:
                print(f"   ... and {len(other_errors) - max_errors} more errors")

        print()  # Add blank line after error display


def parse_args() -> argparse.Namespace:
    """Parse and validate command line arguments"""
    parser = argparse.ArgumentParser(
        description="Enhanced AWS accounts analyzer with rate limiting and error handling."
    )
    parser.add_argument(
        "-r",
        "--role_name",
        default="OrganizationAccountAccessRole",
        help="Specify a custom role name to assume into.",
    )
    parser.add_argument("-R", "--regions", help="Specify which AWS regions to analyze.")
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=5,
        help="Number of worker threads for parallel processing (default: 5, reduced for rate limiting).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Number of accounts to process per batch (default: 20).",
    )
    parser.add_argument(
        "--batch-delay",
        type=int,
        default=30,
        help="Delay in seconds between batches (default: 30).",
    )
    parser.add_argument(
        "--api-delay",
        type=float,
        default=0.1,
        help="Delay in seconds between API calls (default: 0.1).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum retry attempts for failed operations (default: 5).",
    )
    parser.add_argument(
        "--operation-timeout",
        type=int,
        default=300,
        help="Timeout in seconds for individual operations (default: 300).",
    )
    parser.add_argument(
        "--resume-file",
        default="aws_benchmark_progress.json",
        help="File to store/resume progress (default: aws_benchmark_progress.json).",
    )
    parser.add_argument(
        "--skip-accounts", help="Comma-separated list of account IDs to skip."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making API calls.",
    )

    args = parser.parse_args()  # pylint: disable=W0621

    # Input validation
    if args.threads < 1 or args.threads > 20:
        parser.error("Threads must be between 1 and 20")

    if args.batch_size < 1 or args.batch_size > 100:
        parser.error("Batch size must be between 1 and 100")

    if args.batch_delay < 0 or args.batch_delay > 3600:
        parser.error("Batch delay must be between 0 and 3600 seconds")

    if args.api_delay < 0 or args.api_delay > 10:
        parser.error("API delay must be between 0 and 10 seconds")

    if args.max_retries < 0 or args.max_retries > 20:
        parser.error("Max retries must be between 0 and 20")

    if args.operation_timeout < 30 or args.operation_timeout > 3600:
        parser.error("Operation timeout must be between 30 and 3600 seconds")

    if not args.role_name.strip():
        parser.error("Role name cannot be empty")

    # Validate regions format if provided
    if args.regions:
        regions = [r.strip() for r in args.regions.split(",")]
        for region in regions:
            if not region or not region.replace("-", "").isalnum():
                parser.error(f"Invalid region format: {region}")

    return args


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


def setup_signal_handlers() -> None:
    """Setup signal handlers for graceful shutdown"""

    def signal_handler(signum: int) -> None:
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        # The KeyboardInterrupt will be caught in main() for proper cleanup
        raise KeyboardInterrupt("Shutdown signal received")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


class RateLimiter:  # pylint: disable=R0903
    """Simple rate limiter to control API call frequency"""

    def __init__(self, calls_per_second=10):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_called = 0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            elapsed = time.time() - self.last_called
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_called = time.time()


class RetryHandler:
    """Handles exponential backoff and retry logic with error collection support"""

    def __init__(self, error_collector=None):
        self.error_collector = error_collector

    @staticmethod
    def exponential_backoff(attempt, base_delay=1, max_delay=300, jitter=True):
        """Calculate exponential backoff delay with optional jitter"""
        delay = min(base_delay * (2**attempt), max_delay)
        if jitter:
            delay *= 0.5 + random.random() * 0.5  # Add 0-50% jitter
        return delay

    @staticmethod
    def should_retry(exception, attempt, max_retries):
        """Determine if an exception should be retried"""
        if attempt >= max_retries:
            return False

        if isinstance(
            exception,
            (
                botocore.exceptions.ClientError,
                botocore.exceptions.ReadTimeoutError,
                botocore.exceptions.ConnectTimeoutError,
                botocore.exceptions.EndpointConnectionError,
            ),
        ):
            if hasattr(exception, "response"):
                error_code = exception.response.get("Error", {}).get("Code", "")
                # Retry on throttling and temporary errors
                return error_code in [
                    "Throttling",
                    "ThrottledException",
                    "TooManyRequestsException",
                    "RequestLimitExceeded",
                    "ServiceUnavailable",
                    "InternalError",
                ]
            return True
        return False

    def retry_with_backoff(self, func, max_retries=5, operation_name="operation"):
        """Execute function with exponential backoff retry"""
        for attempt in range(max_retries + 1):
            try:
                return func()
            except Exception as e:
                if not self.should_retry(e, attempt, max_retries):
                    error_msg = (
                        f"Failed {operation_name} after {attempt + 1} attempts: {e}"
                    )
                    if self.error_collector:
                        self.error_collector.add_error(
                            error_msg,
                            {"type": "final_failure", "operation": operation_name},
                        )
                    else:
                        print(error_msg)
                    raise

                if attempt < max_retries:
                    delay = self.exponential_backoff(attempt)
                    if self.error_collector:
                        self.error_collector.add_retry_message(
                            operation_name, attempt, max_retries, delay, e
                        )
                    else:
                        print(
                            f"Retry {attempt + 1}/{max_retries} for {operation_name} in {delay:.2f}s: {e}"
                        )
                    time.sleep(delay)

        raise Exception(f"Max retries exceeded for {operation_name}")  # pylint: disable=W0719


class ProgressTracker:
    """Handles progress tracking and resumption"""

    def __init__(self, progress_file):
        self.progress_file = progress_file
        self.load_progress()

    def load_progress(self) -> None:
        """Load progress from file if it exists"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, "r", encoding="utf-8") as f:
                    saved_progress = json.load(f)
                    progress_state.update(saved_progress)
                    progress_state["completed_accounts"] = set(
                        progress_state.get("completed_accounts", [])
                    )
                    progress_state["failed_accounts"] = set(
                        progress_state.get("failed_accounts", [])
                    )
                if logger:
                    logger.info(
                        f"Resumed from progress file: {len(progress_state['completed_accounts'])} accounts completed"
                    )
                else:
                    print(
                        f"Resumed from progress file: {len(progress_state['completed_accounts'])} accounts completed"
                    )
            except (json.JSONDecodeError, KeyError) as e:
                error_msg = f"Invalid progress file format: {e}"
                if logger:
                    logger.error(error_msg)
                else:
                    print(error_msg)
            except OSError as e:
                error_msg = f"Could not read progress file: {e}"
                if logger:
                    logger.error(error_msg)
                else:
                    print(error_msg)

    def save_progress(self) -> None:
        """Save current progress to file"""
        try:
            with progress_lock:
                save_data = progress_state.copy()
                save_data["completed_accounts"] = list(save_data["completed_accounts"])
                save_data["failed_accounts"] = list(save_data["failed_accounts"])
                save_data["last_updated"] = datetime.now(timezone.utc).isoformat()

            with open(self.progress_file, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2)
        except OSError as e:
            error_msg = f"Could not save progress to {self.progress_file}: {e}"
            if logger:
                logger.error(error_msg)
            else:
                print(error_msg)
        except (TypeError, ValueError) as e:
            error_msg = f"Could not serialize progress data: {e}"
            if logger:
                logger.error(error_msg)
            else:
                print(error_msg)

    def mark_completed(self, account_id):
        """Mark an account as completed"""
        with progress_lock:
            progress_state["completed_accounts"].add(account_id)
            progress_state["failed_accounts"].discard(account_id)
        self.save_progress()

    def mark_failed(self, account_id):
        """Mark an account as failed"""
        with progress_lock:
            progress_state["failed_accounts"].add(account_id)
        self.save_progress()

    def is_completed(self, account_id):
        """Check if account is already completed"""
        return account_id in progress_state["completed_accounts"]

    def should_skip(self, account_id):
        """Check if account should be skipped"""
        return self.is_completed(account_id)


class AWSOrgAccess:
    """Handles AWS Organizations access and account enumeration"""

    def __init__(
        self, rate_limiter: "RateLimiter", retry_handler: "RetryHandler"
    ) -> None:
        """Initialize AWS Organizations access

        Args:
            rate_limiter: Rate limiter for API calls
            retry_handler: Retry handler for failed operations
        """
        # Configure boto3 with retry settings
        config = Config(
            retries={"max_attempts": args.max_retries, "mode": "adaptive"},
            max_pool_connections=50,
        )

        self.master_session = boto3.session.Session()
        self.master_sts = self.master_session.client("sts", config=config)
        self.master_account_id = self.master_sts.get_caller_identity()["Account"]
        self.rate_limiter = rate_limiter
        self.retry_handler = retry_handler

    def accounts(self) -> List["AWSHandle"]:
        """Get all active AWS accounts in the organization

        Returns:
            List of AWSHandle objects for active accounts
        """
        try:

            def get_accounts() -> List[Dict[str, Any]]:
                client = boto3.client(
                    "organizations",
                    config=Config(
                        retries={"max_attempts": args.max_retries, "mode": "adaptive"}
                    ),
                )
                response = client.list_accounts()
                accounts = response["Accounts"]
                next_token = response.get("NextToken", None)

                while next_token:
                    self.rate_limiter.wait()
                    response = client.list_accounts(NextToken=next_token)
                    accounts += response["Accounts"]
                    next_token = response.get("NextToken", None)

                return accounts

            accounts = self.retry_handler.retry_with_backoff(
                get_accounts, args.max_retries, "list_accounts"
            )

            # Filter active accounts
            active_accounts = [a for a in accounts if a["Status"] == "ACTIVE"]

            # Apply skip list if provided
            if args.skip_accounts:
                skip_list = [acc.strip() for acc in args.skip_accounts.split(",")]
                active_accounts = [
                    a for a in active_accounts if a["Id"] not in skip_list
                ]

            return [self.aws_handle(a) for a in active_accounts if self.aws_handle(a)]

        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "AccessDeniedException":
                msg = "Cannot autodiscover adjacent accounts: cannot list accounts within the AWS organization"
                if logger:
                    logger.warning(msg)
                else:
                    print(msg)
                return [
                    AWSHandle(
                        rate_limiter=self.rate_limiter, retry_handler=self.retry_handler
                    )
                ]
            if error_code == "AWSOrganizationsNotInUseException":
                msg = "This account is not a member of an AWS Organization"
                if logger:
                    logger.info(msg)
                else:
                    print(msg)
                return [
                    AWSHandle(
                        rate_limiter=self.rate_limiter, retry_handler=self.retry_handler
                    )
                ]
            raise

    def aws_handle(self, account: Dict[str, Any]) -> Optional["AWSHandle"]:
        """Create an AWSHandle for the given account

        Args:
            account: Account dictionary from AWS Organizations API

        Returns:
            AWSHandle object or None if session creation failed
        """
        if account["Id"] == self.master_account_id:
            return AWSHandle(
                aws_session=self.master_session,
                account_id=self.master_account_id,
                rate_limiter=self.rate_limiter,
                retry_handler=self.retry_handler,
            )

        session = self.new_session(account["Id"])
        if session:
            return AWSHandle(
                aws_session=session,
                account_id=account["Id"],
                rate_limiter=self.rate_limiter,
                retry_handler=self.retry_handler,
            )
        return None

    def new_session(self, account_id: str) -> Optional[boto3.session.Session]:
        """Create a new session for the specified account using assumed role

        Args:
            account_id: AWS account ID to assume role into

        Returns:
            Boto3 session object or None if failed
        """
        try:

            def assume_role() -> Dict[str, Any]:
                return self.master_sts.assume_role(
                    RoleArn=f"arn:aws:iam::{account_id}:role/{args.role_name}",
                    RoleSessionName=f"cspm-benchmark-{account_id}",
                )

            credentials = self.retry_handler.retry_with_backoff(
                assume_role, args.max_retries, f"assume_role_{account_id}"
            )

            return boto3.session.Session(
                aws_access_key_id=credentials["Credentials"]["AccessKeyId"],
                aws_secret_access_key=credentials["Credentials"]["SecretAccessKey"],
                aws_session_token=credentials["Credentials"]["SessionToken"],
                region_name="us-east-1",
            )
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_msg = f"Cannot access account {account_id}: {error_code} - {e}"
            if logger:
                logger.error(error_msg)
            else:
                print(error_msg)
            return None
        except (
            botocore.exceptions.BotoCoreError,
            botocore.exceptions.NoCredentialsError,
        ) as e:
            error_msg = f"AWS credentials error for account {account_id}: {e}"
            if logger:
                logger.error(error_msg)
            else:
                print(error_msg)
            return None


class AWSHandle:
    EKS_TAGS = [
        "eks:cluster-name",
        "alpha.eksctl.io/nodegroup-type",
        "aws:eks:cluster-name",
        "eks:nodegroup-name",
    ]

    def __init__(
        self, aws_session=None, account_id=None, rate_limiter=None, retry_handler=None
    ):
        config = Config(
            retries={"max_attempts": args.max_retries, "mode": "adaptive"},
            max_pool_connections=50,
            read_timeout=args.operation_timeout,
            connect_timeout=30,
        )

        self.aws_session = aws_session if aws_session else boto3.session.Session()
        self.acc_id = account_id
        self.config = config
        self.rate_limiter = rate_limiter or RateLimiter()
        self.retry_handler = retry_handler or RetryHandler()

    @property
    def regions(self):
        def get_regions():
            self.rate_limiter.wait()
            response = self.ec2.describe_regions()
            return [region["RegionName"] for region in response["Regions"]]

        return self.retry_handler.retry_with_backoff(
            get_regions, args.max_retries, f"describe_regions_{self.account_id}"
        )

    def ec2_instances(self, aws_region):
        client = self.aws_session.client("ec2", aws_region, config=self.config)

        def get_instances():
            self.rate_limiter.wait()
            response = client.describe_instances(MaxResults=1000)
            instances = response["Reservations"]
            next_token = response.get("NextToken")

            while next_token:
                self.rate_limiter.wait()
                response = client.describe_instances(
                    MaxResults=1000, NextToken=next_token
                )
                instances += response["Reservations"]
                next_token = response.get("NextToken")

            return instances

        return self.retry_handler.retry_with_backoff(
            get_instances,
            args.max_retries,
            f"ec2_instances_{aws_region}_{self.account_id}",
        )

    @property
    def ec2(self):
        return self.aws_session.client("ec2", config=self.config)

    @classmethod
    def is_vm_kubenode(cls, vm):
        return any(True for tag in vm.get("Tags", []) if tag["Key"] in cls.EKS_TAGS)

    @classmethod
    def is_vm_running(cls, vm):
        return vm["State"]["Name"] != "stopped"

    @property
    def account_id(self):
        if self.acc_id is None:
            sts = self.aws_session.client("sts", config=self.config)
            self.acc_id = sts.get_caller_identity()["Account"]
        return self.acc_id

    def fargate_profiles(self, aws_region):
        client = self.aws_session.client("eks", aws_region, config=self.config)

        def get_profiles():
            self.rate_limiter.wait()
            response = client.list_clusters(maxResults=100)
            clusters = response["clusters"]
            next_token = response.get("NextToken")

            while next_token:
                self.rate_limiter.wait()
                response = client.list_clusters(maxResults=100, NextToken=next_token)
                clusters += response["clusters"]
                next_token = response.get("NextToken")

            profiles_count = 0
            for c in clusters:
                self.rate_limiter.wait()
                response = client.list_fargate_profiles(clusterName=c, maxResults=100)
                fargate_profiles = response["fargateProfileNames"]
                next_token = response.get("NextToken")

                while next_token:
                    self.rate_limiter.wait()
                    response = client.list_fargate_profiles(
                        clusterName=c, maxResults=100, NextToken=next_token
                    )
                    fargate_profiles += response["fargateProfileNames"]
                    next_token = response.get("NextToken")

                for p in fargate_profiles:
                    if "fp-falcon" not in p:
                        self.rate_limiter.wait()
                        response = client.describe_fargate_profile(
                            clusterName=c, fargateProfileName=p
                        )
                        if "ACTIVE" in response["fargateProfile"]["status"]:
                            profiles_count += 1

            return profiles_count

        return self.retry_handler.retry_with_backoff(
            get_profiles,
            args.max_retries,
            f"fargate_profiles_{aws_region}_{self.account_id}",
        )

    def fargate_tasks(self, aws_region):
        client = self.aws_session.client("ecs", aws_region, config=self.config)

        def get_tasks():
            self.rate_limiter.wait()
            response = client.list_clusters(maxResults=100)
            cluster_arns = response["clusterArns"]
            next_token = response.get("NextToken")

            while next_token:
                self.rate_limiter.wait()
                response = client.list_clusters(maxResults=100, NextToken=next_token)
                cluster_arns += response["clusterArns"]
                next_token = response.get("NextToken")

            tasks_count = 0
            for c in cluster_arns:
                self.rate_limiter.wait()
                response = client.list_services(
                    cluster=c, maxResults=100, launchType="FARGATE"
                )
                service_arns = response["serviceArns"]
                next_token = response.get("NextToken")

                while next_token:
                    self.rate_limiter.wait()
                    response = client.list_services(
                        cluster=c, launchType="FARGATE", NextToken=next_token
                    )
                    service_arns += response["serviceArns"]
                    next_token = response.get("NextToken")

                for a in service_arns:
                    self.rate_limiter.wait()
                    response = client.describe_services(cluster=c, services=[a])
                    for s in response["services"]:
                        if "ACTIVE" in s["status"]:
                            tasks_count += s["desiredCount"]

            return tasks_count

        return self.retry_handler.retry_with_backoff(
            get_tasks, args.max_retries, f"fargate_tasks_{aws_region}_{self.account_id}"
        )


def process_ec2_instances(aws_handle, region_name, error_collector=None):
    """Process EC2 instances for a specific region with timeout"""

    def process():
        vms_terminated = 0
        vms_running = 0
        kubenodes_terminated = 0
        kubenodes_running = 0

        for reservation in aws_handle.ec2_instances(region_name):
            for instance in reservation["Instances"]:
                typ = "kubenode" if AWSHandle.is_vm_kubenode(instance) else "vm"
                state = "running" if AWSHandle.is_vm_running(instance) else "terminated"

                if typ == "kubenode":
                    if state == "running":
                        kubenodes_running += 1
                    else:
                        kubenodes_terminated += 1
                else:
                    if state == "running":
                        vms_running += 1
                    else:
                        vms_terminated += 1

        return {
            "vms_terminated": vms_terminated,
            "vms_running": vms_running,
            "kubenodes_terminated": kubenodes_terminated,
            "kubenodes_running": kubenodes_running,
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(process)
        try:
            return future.result(timeout=args.operation_timeout)
        except concurrent.futures.TimeoutError:
            if error_collector:
                error_collector.add_timeout_error(
                    "EC2 instances", region_name, aws_handle.account_id
                )
            else:
                print(f"Timeout processing EC2 instances in {region_name}")
            future.cancel()
            return {
                "vms_terminated": 0,
                "vms_running": 0,
                "kubenodes_terminated": 0,
                "kubenodes_running": 0,
            }


def process_fargate_profiles(aws_handle, region_name, error_collector=None):
    """Process Fargate profiles for a specific region with timeout"""

    def process():
        return aws_handle.fargate_profiles(region_name)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(process)
        try:
            return future.result(timeout=args.operation_timeout)
        except concurrent.futures.TimeoutError:
            if error_collector:
                error_collector.add_timeout_error(
                    "Fargate profiles", region_name, aws_handle.account_id
                )
            else:
                print(f"Timeout processing Fargate profiles in {region_name}")
            future.cancel()
            return 0


def process_fargate_tasks(aws_handle, region_name, error_collector=None):
    """Process Fargate tasks for a specific region with timeout"""

    def process():
        return aws_handle.fargate_tasks(region_name)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(process)
        try:
            return future.result(timeout=args.operation_timeout)
        except concurrent.futures.TimeoutError:
            if error_collector:
                error_collector.add_timeout_error(
                    "Fargate tasks", region_name, aws_handle.account_id
                )
            else:
                print(f"Timeout processing Fargate tasks in {region_name}")
            future.cancel()
            return 0


def process_region(aws_handle, region_name, error_collector=None, max_workers=2):  # pylint: disable=R0912
    """Process all resources in a region using parallel processing with reduced concurrency"""
    # Removed verbose per-region output - now handled by progress bar in process_account

    row = {
        "account_id": aws_handle.account_id,
        "region": region_name,
        "vms_terminated": 0,
        "vms_running": 0,
        "kubenodes_terminated": 0,
        "kubenodes_running": 0,
        "fargate_profiles": 0,
        "fargate_tasks": 0,
    }

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks with error collector
            ec2_future = executor.submit(
                process_ec2_instances, aws_handle, region_name, error_collector
            )
            fargate_profiles_future = executor.submit(
                process_fargate_profiles, aws_handle, region_name, error_collector
            )
            fargate_tasks_future = executor.submit(
                process_fargate_tasks, aws_handle, region_name, error_collector
            )

            # Collect results with timeout
            try:
                ec2_results = ec2_future.result(timeout=args.operation_timeout)
                row.update(ec2_results)
            except Exception as e:
                if error_collector:
                    error_collector.add_processing_error(
                        "EC2", region_name, e, aws_handle.account_id
                    )
                else:
                    print(f"Error processing EC2 in {region_name}: {e}")

            try:
                row["fargate_profiles"] = fargate_profiles_future.result(
                    timeout=args.operation_timeout
                )
            except Exception as e:
                if error_collector:
                    error_collector.add_processing_error(
                        "Fargate profiles", region_name, e, aws_handle.account_id
                    )
                else:
                    print(f"Error processing Fargate profiles in {region_name}: {e}")

            try:
                row["fargate_tasks"] = fargate_tasks_future.result(
                    timeout=args.operation_timeout
                )
            except Exception as e:
                if error_collector:
                    error_collector.add_processing_error(
                        "Fargate tasks", region_name, e, aws_handle.account_id
                    )
                else:
                    print(f"Error processing Fargate tasks in {region_name}: {e}")

    except Exception as e:
        if error_collector:
            error_collector.add_processing_error(
                "region", region_name, e, aws_handle.account_id
            )
        else:
            print(f"Error processing region {region_name}: {e}")

    # Thread-safe updates to global data structures
    with data_lock:
        data.append(row)

    with totals_lock:
        for k in [
            "vms_terminated",
            "vms_running",
            "kubenodes_terminated",
            "kubenodes_running",
            "fargate_profiles",
            "fargate_tasks",
        ]:
            totals[k] += row[k]


def process_account(aws_handle, regions_to_process, progress_tracker, max_workers=3):  # pylint: disable=R0914
    """Process all regions for an account using parallel processing with simple status messages"""
    account_id = aws_handle.account_id

    if progress_tracker.should_skip(account_id):
        print(f"✓ Skipping already completed account: {account_id}")
        return

    # Initialize error collector
    error_collector = ErrorCollector()

    # Simple status message when starting account processing
    with console_lock:
        print(f"Processing account: {account_id}")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            region_futures = [
                executor.submit(
                    process_region, aws_handle, region_name, error_collector
                )
                for region_name in regions_to_process
            ]

            # Wait for all regions to complete with timeout
            future_errors = []

            for future in concurrent.futures.as_completed(
                region_futures, timeout=args.operation_timeout * len(regions_to_process)
            ):
                try:
                    result = future.result()  # pylint: disable=W0612
                except Exception as e:
                    future_errors.append(str(e))

        # Simple completion message with error handling
        with console_lock:
            error_count = len(error_collector.get_errors()) + len(future_errors)
            if error_count > 0:
                print(f"\n✓ {account_id} - completed with {error_count} error(s)")

                # Display collected errors
                if error_collector.has_errors():
                    error_collector.display_errors()

                # Print any future execution errors that weren't collected
                if future_errors:
                    print("\n   Additional execution errors:")
                    for error in future_errors[:3]:
                        print(f"   ⚠️  {error}")
                    if len(future_errors) > 3:
                        print(
                            f"   ... and {len(future_errors) - 3} more execution errors"
                        )
                    print()  # Add blank line after additional errors
            else:
                print(f"\n✓ {account_id} - completed successfully\n")

        progress_tracker.mark_completed(account_id)

    except Exception as e:
        with console_lock:
            print(f"\n✗ {account_id} - failed")
            # Display any collected errors before showing the failure
            if error_collector.has_errors():
                error_collector.display_errors()
            print(f"   ❌ {e}\n")
        progress_tracker.mark_failed(account_id)


def process_accounts_in_batches(accounts, regions_to_process, progress_tracker):
    """Process accounts in batches to manage rate limiting"""
    total_accounts = len(accounts)
    batch_size = args.batch_size

    progress_state["total_accounts"] = total_accounts
    progress_state["start_time"] = datetime.now(timezone.utc).isoformat()

    print(f"Processing {total_accounts} accounts in batches of {batch_size}")

    for i in range(0, total_accounts, batch_size):
        batch = accounts[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total_accounts + batch_size - 1) // batch_size

        progress_state["current_batch"] = batch_num
        progress_tracker.save_progress()

        print(
            f"\n--- Processing Batch {batch_num}/{total_batches} ({len(batch)} accounts) ---"
        )

        if args.dry_run:
            for aws_handle in batch:
                print(f"Would process account: {aws_handle.account_id}")
            continue

        # Process accounts in current batch
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.threads
        ) as executor:
            account_futures = [
                executor.submit(
                    process_account, aws_handle, regions_to_process, progress_tracker
                )
                for aws_handle in batch
            ]

            # Wait for batch to complete
            for future in concurrent.futures.as_completed(account_futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Error in batch processing: {e}")

        # Delay between batches (except for the last batch)
        if i + batch_size < total_accounts:
            print(f"Waiting {args.batch_delay} seconds before next batch...")
            time.sleep(args.batch_delay)

    print(f"\nCompleted processing all {total_accounts} accounts")


def print_resume_guidance(progress_tracker, args):  # pylint: disable=W0621,R0912,R0915
    """Print helpful guidance on how to resume interrupted processing"""
    completed_count = len(progress_state.get("completed_accounts", []))
    total_count = progress_state.get("total_accounts", 0)
    failed_count = len(progress_state.get("failed_accounts", []))

    print("\n" + "=" * 70)
    print("📁 PROGRESS SAVED - PROCESSING CAN BE RESUMED")
    print("=" * 70)

    if completed_count > 0 or failed_count > 0:
        print("Progress Summary:")
        print(f"  ✅ Completed accounts: {completed_count}")
        print(f"  ❌ Failed accounts: {failed_count}")
        if total_count > 0:
            remaining = total_count - completed_count
            print(f"  ⏳ Remaining accounts: {remaining}")
            completion_percent = (completed_count / total_count) * 100
            print(f"  📊 Progress: {completion_percent:.1f}% complete")

    print(f"\n📄 Progress file: {progress_tracker.progress_file}")

    print("\n🚀 To resume processing, run the same command:")

    # Build the resume command
    script_name = os.path.basename(__file__)
    resume_cmd = f"python3 {script_name}"

    # Add the most important arguments
    if args.role_name != "OrganizationAccountAccessRole":
        resume_cmd += f" -r {args.role_name}"
    if args.regions:
        resume_cmd += f' -R "{args.regions}"'
    if args.threads != 5:
        resume_cmd += f" --threads {args.threads}"
    if args.batch_size != 20:
        resume_cmd += f" --batch-size {args.batch_size}"
    if args.batch_delay != 30:
        resume_cmd += f" --batch-delay {args.batch_delay}"
    if args.api_delay != 0.1:
        resume_cmd += f" --api-delay {args.api_delay}"
    if args.max_retries != 5:
        resume_cmd += f" --max-retries {args.max_retries}"
    if args.operation_timeout != 300:
        resume_cmd += f" --operation-timeout {args.operation_timeout}"
    if args.resume_file != "aws_benchmark_progress.json":
        resume_cmd += f" --resume-file {args.resume_file}"
    if args.skip_accounts:
        resume_cmd += f' --skip-accounts "{args.skip_accounts}"'

    print(f"   {resume_cmd}")

    if completed_count > 0:
        print("\n💡 The script will automatically:")
        print(f"   • Skip {completed_count} already completed accounts")
        print("   • Continue from where it left off")
        print("   • Process only the remaining accounts")

    print("\n🔧 For large organizations (200+ accounts), consider using:")
    print("   export AWS_THREADS=2")
    print("   export AWS_BATCH_SIZE=10")
    print("   export AWS_BATCH_DELAY=60")
    print("   export AWS_API_DELAY=0.2")
    print("   ./benchmark.sh aws")

    print("\n📚 For more help, see: AWS/RATE_LIMITING_SOLUTIONS.md")
    print("=" * 70)


def main() -> None:  # pylint: disable=R0915,R0914,R0912
    """Enhanced main function with batch processing and rate limiting"""
    global args, logger  # pylint: disable=W0603

    # Initialize global configuration first
    args = parse_args()  # pylint: disable=W0621
    logger = setup_logging()
    setup_signal_handlers()

    start_time = time.time()

    logger.info("Starting enhanced AWS CSPM benchmark")
    logger.info("Configuration:")
    logger.info(f"  - Threads: {args.threads}")
    logger.info(f"  - Batch size: {args.batch_size}")
    logger.info(f"  - Batch delay: {args.batch_delay}s")
    logger.info(f"  - API delay: {args.api_delay}s")
    logger.info(f"  - Max retries: {args.max_retries}")
    logger.info(f"  - Operation timeout: {args.operation_timeout}s")
    logger.info(f"  - Dry run: {args.dry_run}")

    # Initialize components with global error collector
    global_error_collector = ErrorCollector()
    rate_limiter = RateLimiter(calls_per_second=1.0 / args.api_delay)
    retry_handler = RetryHandler(error_collector=global_error_collector)
    progress_tracker = ProgressTracker(args.resume_file)

    # Get all AWS accounts
    try:
        accounts = AWSOrgAccess(rate_limiter, retry_handler).accounts()
        print(f"Found {len(accounts)} accounts to process")

        if not accounts:
            print("No accounts found to process")
            return

        # Filter out already completed accounts
        if not args.dry_run:
            pending_accounts = [
                acc
                for acc in accounts
                if not progress_tracker.should_skip(acc.account_id)
            ]
            print(
                f"Accounts pending: {len(pending_accounts)} (skipping {len(accounts) - len(pending_accounts)} completed)"
            )
            accounts = pending_accounts

        if not accounts:
            print("All accounts already completed!")
            return

        # Determine regions to process and display in configuration
        if args.regions:
            regions_to_process = [x.strip() for x in args.regions.split(",")]
            regions_display = ", ".join(regions_to_process)
            print(f"\n📍 Regions to process: {regions_display}")
        else:
            regions_to_process = accounts[0].regions
            regions_display = ", ".join(regions_to_process[:10])
            if len(regions_to_process) > 10:
                regions_display += f" ... (+{len(regions_to_process) - 10} more)"
            print(
                f"\n📍 Processing all {len(regions_to_process)} regions: {regions_display}"
            )

        # Process accounts in batches
        process_accounts_in_batches(accounts, regions_to_process, progress_tracker)

    except KeyboardInterrupt:
        print("\nProcessing interrupted by user")
        progress_tracker.save_progress()
        print_resume_guidance(progress_tracker, args)
        return
    except Exception as e:
        print(f"Fatal error: {e}")
        progress_tracker.save_progress()
        print_resume_guidance(progress_tracker, args)
        return

    if not args.dry_run:
        # Add totals row
        data.append(totals)

        end_time = time.time()
        processing_time = end_time - start_time

        print(f"\nProcessing completed in {processing_time:.2f} seconds")
        print(f"Completed accounts: {len(progress_state['completed_accounts'])}")
        print(f"Failed accounts: {len(progress_state['failed_accounts'])}")

        # Output results
        if data:
            # Save to CSV with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"aws-benchmark-{timestamp}.csv"

            with open(csv_filename, "w", newline="", encoding="utf-8") as csv_file:
                csv_writer = csv.DictWriter(csv_file, fieldnames=headers.keys())
                csv_writer.writeheader()
                csv_writer.writerows(data)

            print(f"\nCSV file stored in: ./cloud-benchmark/{csv_filename}")

        # Clean up progress file on successful completion
        if len(progress_state["failed_accounts"]) == 0:
            try:
                os.remove(args.resume_file)
                logger.info("Progress file cleaned up")
            except OSError as e:
                logger.warning(
                    f"Could not remove progress file {args.resume_file}: {e}"
                )
            except Exception as e:
                logger.error(f"Unexpected error removing progress file: {e}")


if __name__ == "__main__":
    main()


#     .wwwwwwww.
#   .w"  "WW"  "w.
#  ."   /\  /\   ".
# |\     o  o     /|
#  \|  ___\/___  |/
#  / \ \_v__v_/ / \
# / | \________/ | \
# >  \   WWWW   /  <
# \   \   WWWW   /  /
#  \   \      /   /
#  Enhanced Count says...
#
#  That's ONE batch, TWO batches... with RATE LIMITING! AH AH AH!

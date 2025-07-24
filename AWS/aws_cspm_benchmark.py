"""
aws-cspm-benchmark.py

Assists with provisioning calculations by retrieving a count of
all billable resources attached to an AWS account.
"""
import argparse
import csv
import boto3
import botocore
from tabulate import tabulate
import concurrent.futures
import threading
import time


data = []
headers = {
    'account_id': 'AWS Account ID',
    "region": "Region",
    "vms_terminated": "Terminated VMs",
    "vms_running": "Running VMs",
    'kubenodes_terminated': "Terminated Kubernetes Nodes",
    'kubenodes_running': "Running Kubernetes Nodes",
    'fargate_profiles': "Active EKS Fargate Profiles",
    'fargate_tasks': "ECS Service Fargate Tasks"
}
totals = {
    "region": "TOTAL",
    'account_id': 'TOTAL',
    "vms_terminated": 0,
    "vms_running": 0,
    'kubenodes_terminated': 0,
    'kubenodes_running': 0,
    'fargate_profiles': 0,
    'fargate_tasks': 0
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze AWS accounts and regions for EC2 instances and Kubernetes nodes.")
    parser.add_argument(
        "-r", "--role_name",
        default="OrganizationAccountAccessRole",
        help="Specify a custom role name to assume into.")
    parser.add_argument(
        "-R", "--regions",
        help="Specify which AWS regions to analyze.")
    parser.add_argument(
        "-t", "--threads",
        type=int,
        default=10,
        help="Number of worker threads for parallel processing (default: 10).")
    return parser.parse_args()


class AWSOrgAccess:
    def __init__(self):
        self.master_session = boto3.session.Session()
        self.master_sts = self.master_session.client('sts')
        self.master_account_id = self.master_sts.get_caller_identity()["Account"]

    def accounts(self):
        try:
            client = boto3.client('organizations')
            response = client.list_accounts()
            accounts = response['Accounts']
            next_token = response.get('NextToken', None)

            while next_token:
                response = client.list_accounts(NextToken=next_token)
                accounts += response['Accounts']
                next_token = response.get('NextToken', None)

            # We only want accounts that are in ACTIVE state
            # Permissable values are: 'ACTIVE'|'SUSPENDED'|'PENDING_CLOSURE'
            active_accounts = [a for a in accounts if a['Status'] == 'ACTIVE']

            return [self.aws_handle(a) for a in active_accounts if self.aws_handle(a)]
        except client.exceptions.AccessDeniedException:
            print("Cannot autodiscover adjacent accounts: cannot list accounts within the AWS organization")
            return [AWSHandle()]
        except client.exceptions.AWSOrganizationsNotInUseException:
            print("This account is not a member of an AWS Organization")
            return [AWSHandle()]

    def aws_handle(self, account):
        if account['Id'] == self.master_account_id:
            return AWSHandle(aws_session=self.master_session, account_id=self.master_account_id)

        # Check if new_session returns a session object
        session = self.new_session(account['Id'])
        if session:
            return AWSHandle(aws_session=session, account_id=account['Id'])

        return None

    def new_session(self, account_id):
        try:
            credentials = self.master_sts.assume_role(
                RoleArn=f'arn:aws:iam::{account_id}:role/{args.role_name}',
                RoleSessionName=account_id
            )
            return boto3.session.Session(
                aws_access_key_id=credentials['Credentials']['AccessKeyId'],
                aws_secret_access_key=credentials['Credentials']['SecretAccessKey'],
                aws_session_token=credentials['Credentials']['SessionToken'],
                region_name='us-east-1'
            )
        except self.master_sts.exceptions.ClientError as exc:
            # Print the error and continue.
            # Handle what to do with accounts that cannot be accessed
            # due to assuming role errors.
            print("Cannot access adjacent account: ", account_id, exc)
            return None


class AWSHandle:
    EKS_TAGS = ['eks:cluster-name', 'alpha.eksctl.io/nodegroup-type', 'aws:eks:cluster-name', 'eks:nodegroup-name']

    def __init__(self, aws_session=None, account_id=None):
        self.aws_session = aws_session if aws_session else boto3.session.Session()
        self.acc_id = account_id

    @property
    def regions(self):
        active_regions = []
        response = self.ec2.describe_regions()
        active_regions = [region['RegionName'] for region in response['Regions']]
        return active_regions

    def ec2_instances(self, aws_region):
        client = self.aws_session.client('ec2', aws_region)

        response = client.describe_instances(MaxResults=1000)
        instances = response['Reservations']
        next_token = response['NextToken'] if 'NextToken' in response else None

        while next_token:
            response = client.describe_instances(MaxResults=1000, NextToken=next_token)
            instances += response['Reservations']
            next_token = response['NextToken'] if 'NextToken' in response else None

        return instances

    @property
    def ec2(self):
        return self.aws_session.client("ec2")

    @classmethod
    def is_vm_kubenode(cls, vm):
        return any(True for tag in vm.get('Tags', []) if tag['Key'] in cls.EKS_TAGS)

    @classmethod
    def is_vm_running(cls, vm):
        return vm['State']['Name'] != 'stopped'

    @property
    def account_id(self):
        if self.acc_id is None:
            sts = self.aws_session.client('sts')
            self.acc_id = sts.get_caller_identity()["Account"]

        return self.acc_id

    def fargate_profiles(self, aws_region):
        active_profiles = 0

        client = self.aws_session.client('eks', aws_region)

        response = client.list_clusters(maxResults=100)
        clusters = response['clusters']
        next_token = response['NextToken'] if 'NextToken' in response else None

        while next_token:
            response = client.list_clusters(maxResults=100, NextToken=next_token)
            clusters += response['clusters']
            next_token = response['NextToken'] if 'NextToken' in response else None

        for c in clusters:
            response = client.list_fargate_profiles(clusterName=c, maxResults=100)
            fargate_profiles = response['fargateProfileNames']
            next_token = response['NextToken'] if 'NextToken' in response else None

            while next_token:
                response = client.list_fargate_profiles(clusterName=c, maxResults=100, NextToken=next_token)
                fargate_profiles += response['fargateProfileNames']
                next_token = response['NextToken'] if 'NextToken' in response else None

            # Generate active_profiles from 'active' Fargate profiles in each EKS Cluster
            for p in fargate_profiles:
                if 'fp-falcon' not in p:
                    response = client.describe_fargate_profile(clusterName=c, fargateProfileName=p)
                    if 'ACTIVE' in response['fargateProfile']['status']:
                        active_profiles += 1

        return active_profiles

    def fargate_tasks(self, aws_region):
        active_tasks = 0

        client = self.aws_session.client('ecs', aws_region)

        response = client.list_clusters(maxResults=100)
        cluster_arns = response['clusterArns']
        next_token = response['NextToken'] if 'NextToken' in response else None

        while next_token:
            response = client.list_clusters(maxResults=100, NextToken=next_token)
            cluster_arns += response['clusterArns']
            next_token = response['NextToken'] if 'NextToken' in response else None

        for c in cluster_arns:
            response = client.list_services(cluster=c, maxResults=100, launchType='FARGATE')
            service_arns = response['serviceArns']
            next_token = response['NextToken'] if 'NextToken' in response else None

            while next_token:
                response = client.list_services(cluster=c, launchType='FARGATE')
                service_arns += response['serviceArns']
                next_token = response['NextToken'] if 'NextToken' in response else None

            # Generate active_tasks from 'desiredCount' in each ECS Service definition
            for a in service_arns:
                response = client.describe_services(cluster=c, services=[a])
                for s in response['services']:
                    if 'ACTIVE' in s['status']:
                        active_tasks += s['desiredCount']

        return active_tasks


# Thread-safe data structures
data_lock = threading.Lock()
totals_lock = threading.Lock()


def process_ec2_instances(aws_handle, region_name):
    """Process EC2 instances for a specific region"""
    vms_terminated = 0
    vms_running = 0
    kubenodes_terminated = 0
    kubenodes_running = 0
    
    try:
        for reservation in aws_handle.ec2_instances(region_name):
            for instance in reservation['Instances']:
                typ = 'kubenode' if AWSHandle.is_vm_kubenode(instance) else 'vm'
                state = 'running' if AWSHandle.is_vm_running(instance) else 'terminated'
                
                if typ == 'kubenode':
                    if state == 'running':
                        kubenodes_running += 1
                    else:
                        kubenodes_terminated += 1
                else:
                    if state == 'running':
                        vms_running += 1
                    else:
                        vms_terminated += 1
    except botocore.exceptions.ClientError as e:
        print(f"Error processing EC2 instances in {region_name}: {e}")
    
    return {
        'vms_terminated': vms_terminated,
        'vms_running': vms_running,
        'kubenodes_terminated': kubenodes_terminated,
        'kubenodes_running': kubenodes_running
    }


def process_fargate_profiles(aws_handle, region_name):
    """Process Fargate profiles for a specific region"""
    try:
        return aws_handle.fargate_profiles(region_name)
    except botocore.exceptions.ClientError as e:
        print(f"Error processing Fargate profiles in {region_name}: {e}")
        return 0


def process_fargate_tasks(aws_handle, region_name):
    """Process Fargate tasks for a specific region"""
    try:
        return aws_handle.fargate_tasks(region_name)
    except botocore.exceptions.ClientError as e:
        print(f"Error processing Fargate tasks in {region_name}: {e}")
        return 0


def process_region(aws_handle, region_name, max_workers=3):
    """Process all resources in a region using parallel processing"""
    print(f"Processing region: {region_name} (Account: {aws_handle.account_id})")
    
    # Create the row for our output table
    row = {
        'account_id': aws_handle.account_id,
        'region': region_name,
        'vms_terminated': 0,
        'vms_running': 0,
        'kubenodes_terminated': 0,
        'kubenodes_running': 0,
        'fargate_profiles': 0,
        'fargate_tasks': 0
    }
    
    # Process different resource types in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        ec2_future = executor.submit(process_ec2_instances, aws_handle, region_name)
        fargate_profiles_future = executor.submit(process_fargate_profiles, aws_handle, region_name)
        fargate_tasks_future = executor.submit(process_fargate_tasks, aws_handle, region_name)
        
        # Collect results
        ec2_results = ec2_future.result()
        row.update(ec2_results)
        
        row['fargate_profiles'] = fargate_profiles_future.result()
        row['fargate_tasks'] = fargate_tasks_future.result()
    
    # Thread-safe updates to global data structures
    with data_lock:
        data.append(row)
    
    with totals_lock:
        for k in ['vms_terminated', 'vms_running', 'kubenodes_terminated',
                  'kubenodes_running', 'fargate_profiles', 'fargate_tasks']:
            totals[k] += row[k]
    
    return row


def process_account(aws_handle, regions_to_process, max_workers=5):
    """Process all regions for an account using parallel processing"""
    print(f"Processing account: {aws_handle.account_id} with {len(regions_to_process)} regions")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all region processing tasks
        region_futures = [
            executor.submit(process_region, aws_handle, region_name)
            for region_name in regions_to_process
        ]
        
        # Wait for all regions to complete
        for future in concurrent.futures.as_completed(region_futures):
            try:
                future.result()  # This will raise any exceptions that occurred
            except Exception as e:
                print(f"Error processing region: {e}")


def main():
    """Main function with parallel processing"""
    start_time = time.time()
    
    print(f"Starting AWS CSPM benchmark with {args.threads} worker threads")
    
    # Get all AWS accounts
    accounts = AWSOrgAccess().accounts()
    print(f"Found {len(accounts)} accounts to process")
    
    # Process accounts in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
        account_futures = []
        
        for aws_handle in accounts:
            if args.regions:
                regions_to_process = [x.strip() for x in args.regions.split(',')]
            else:
                regions_to_process = aws_handle.regions
            
            # Submit account processing task
            future = executor.submit(process_account, aws_handle, regions_to_process)
            account_futures.append(future)
        
        # Wait for all accounts to complete
        for future in concurrent.futures.as_completed(account_futures):
            try:
                future.result()  # This will raise any exceptions that occurred
            except Exception as e:
                print(f"Error processing account: {e}")
    
    # Add totals row
    data.append(totals)
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    print(f"\nProcessing completed in {processing_time:.2f} seconds")
    
    # Output results
    print(tabulate(data, headers=headers, tablefmt="grid"))
    
    # Save to CSV
    with open('aws-benchmark.csv', 'w', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=headers.keys())
        csv_writer.writeheader()
        csv_writer.writerows(data)
    
    print("\nCSV file stored in: ./aws-benchmark.csv\n")


args = parse_args()

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
# \   \   ""   /   /
#  \   \      /   /
#  The Count says...
#
#  That's ONE server, TWO servers  ... AH AH AH!

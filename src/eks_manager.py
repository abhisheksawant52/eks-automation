"""
EKS Manager - A CLI tool for managing AWS Elastic Kubernetes Service clusters.

Usage:
    python eks_manager.py [COMMAND] [OPTIONS]

Authentication:
    Uses boto3 with standard AWS credential chain:
    - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    - AWS CLI profile (~/.aws/credentials)
    - IAM role (when running on EC2/ECS/Lambda)
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import boto3
import click
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from tabulate import tabulate

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("eks-manager")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_region() -> str:
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    if not region:
        try:
            result = subprocess.check_output(
                ["aws", "configure", "get", "region"], stderr=subprocess.DEVNULL
            ).decode().strip()
            if result:
                return result
        except Exception:
            pass
        return "us-east-1"
    return region


def _eks_client(region: str):
    return boto3.client("eks", region_name=region)


def _ec2_client(region: str):
    return boto3.client("ec2", region_name=region)


def _iam_client():
    return boto3.client("iam")


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------


@click.group()
@click.version_option("1.0.0", prog_name="eks-manager")
def cli() -> None:
    """EKS Manager — manage AWS Elastic Kubernetes Service clusters from the command line."""


# ---------------------------------------------------------------------------
# create-cluster
# ---------------------------------------------------------------------------


@cli.command("create-cluster")
@click.option("--cluster-name", "-n", required=True, envvar="EKS_CLUSTER_NAME", help="Name of the EKS cluster.")
@click.option("--region", "-r", default=None, envvar="AWS_DEFAULT_REGION", help="AWS region.")
@click.option("--kubernetes-version", default="1.29", show_default=True, help="Kubernetes version.")
@click.option("--role-arn", required=True, envvar="EKS_ROLE_ARN", help="IAM role ARN for the EKS cluster.")
@click.option("--subnet-ids", required=True, envvar="EKS_SUBNET_IDS", help="Comma-separated subnet IDs.")
@click.option("--security-group-ids", required=True, envvar="EKS_SG_IDS", help="Comma-separated security group IDs.")
@click.option("--endpoint-public-access/--no-endpoint-public-access", default=True, show_default=True, help="Enable public API endpoint.")
@click.option("--endpoint-private-access/--no-endpoint-private-access", default=False, show_default=True, help="Enable private API endpoint.")
def create_cluster(
    cluster_name: str,
    region: Optional[str],
    kubernetes_version: str,
    role_arn: str,
    subnet_ids: str,
    security_group_ids: str,
    endpoint_public_access: bool,
    endpoint_private_access: bool,
) -> None:
    """Create a new EKS cluster.

    \b
    Example:
        python eks_manager.py create-cluster \\
            --cluster-name my-cluster \\
            --role-arn arn:aws:iam::123456789:role/eks-role \\
            --subnet-ids subnet-abc,subnet-def \\
            --security-group-ids sg-xyz
    """
    region = region or _get_region()
    eks = _eks_client(region)

    subnets = [s.strip() for s in subnet_ids.split(",")]
    sgs = [s.strip() for s in security_group_ids.split(",")]

    logger.info("Creating EKS cluster '%s' in region '%s'...", cluster_name, region)

    try:
        response = eks.create_cluster(
            name=cluster_name,
            version=kubernetes_version,
            roleArn=role_arn,
            resourcesVpcConfig={
                "subnetIds": subnets,
                "securityGroupIds": sgs,
                "endpointPublicAccess": endpoint_public_access,
                "endpointPrivateAccess": endpoint_private_access,
            },
            logging={
                "clusterLogging": [
                    {
                        "types": ["api", "audit", "authenticator", "controllerManager", "scheduler"],
                        "enabled": True,
                    }
                ]
            },
            tags={
                "project": "eks-automation",
                "managed-by": "eks-manager-cli",
            },
        )
        cluster = response["cluster"]
        click.echo(
            click.style(
                f"✓ Cluster '{cluster['name']}' creation initiated. "
                f"Status: {cluster['status']}. "
                f"ARN: {cluster['arn']}",
                fg="green",
            )
        )
        click.echo("Run 'eks_manager.py describe-cluster' to check provisioning status (takes ~10 minutes).")
    except ClientError as exc:
        raise click.ClickException(f"Failed to create cluster: {exc}") from exc


# ---------------------------------------------------------------------------
# delete-cluster
# ---------------------------------------------------------------------------


@cli.command("delete-cluster")
@click.option("--cluster-name", "-n", required=True, envvar="EKS_CLUSTER_NAME", help="Name of the EKS cluster.")
@click.option("--region", "-r", default=None, envvar="AWS_DEFAULT_REGION", help="AWS region.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def delete_cluster(cluster_name: str, region: Optional[str], yes: bool) -> None:
    """Delete an existing EKS cluster.

    \b
    Example:
        python eks_manager.py delete-cluster --cluster-name my-cluster --yes
    """
    if not yes:
        click.confirm(f"Are you sure you want to delete cluster '{cluster_name}'?", abort=True)

    region = region or _get_region()
    eks = _eks_client(region)

    logger.info("Deleting EKS cluster '%s'...", cluster_name)

    try:
        eks.delete_cluster(name=cluster_name)
        click.echo(click.style(f"✓ Cluster '{cluster_name}' deletion initiated.", fg="green"))
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceNotFoundException":
            raise click.ClickException(f"Cluster '{cluster_name}' not found in region '{region}'.")
        raise click.ClickException(f"Failed to delete cluster: {exc}") from exc


# ---------------------------------------------------------------------------
# describe-cluster
# ---------------------------------------------------------------------------


@cli.command("describe-cluster")
@click.option("--cluster-name", "-n", required=True, envvar="EKS_CLUSTER_NAME", help="Name of the EKS cluster.")
@click.option("--region", "-r", default=None, envvar="AWS_DEFAULT_REGION", help="AWS region.")
@click.option("--output", "-o", type=click.Choice(["table", "json"]), default="table", show_default=True)
def describe_cluster(cluster_name: str, region: Optional[str], output: str) -> None:
    """Show details of an EKS cluster.

    \b
    Example:
        python eks_manager.py describe-cluster --cluster-name my-cluster
    """
    region = region or _get_region()
    eks = _eks_client(region)

    try:
        response = eks.describe_cluster(name=cluster_name)
        cluster = response["cluster"]
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceNotFoundException":
            raise click.ClickException(f"Cluster '{cluster_name}' not found.")
        raise click.ClickException(f"Failed to describe cluster: {exc}") from exc

    if output == "json":
        click.echo(json.dumps(cluster, indent=2, default=str))
    else:
        rows = [
            {"Field": "Name", "Value": cluster.get("name", "—")},
            {"Field": "Status", "Value": cluster.get("status", "—")},
            {"Field": "Kubernetes Version", "Value": cluster.get("version", "—")},
            {"Field": "ARN", "Value": cluster.get("arn", "—")},
            {"Field": "Endpoint", "Value": cluster.get("endpoint", "provisioning...")},
            {"Field": "Region", "Value": region},
            {"Field": "Role ARN", "Value": cluster.get("roleArn", "—")},
        ]
        click.echo(tabulate(rows, headers="keys", tablefmt="rounded_outline"))


# ---------------------------------------------------------------------------
# get-credentials
# ---------------------------------------------------------------------------


@cli.command("get-credentials")
@click.option("--cluster-name", "-n", required=True, envvar="EKS_CLUSTER_NAME", help="Name of the EKS cluster.")
@click.option("--region", "-r", default=None, envvar="AWS_DEFAULT_REGION", help="AWS region.")
@click.option("--profile", default=None, help="AWS CLI profile to use in kubeconfig.")
def get_credentials(cluster_name: str, region: Optional[str], profile: Optional[str]) -> None:
    """Update kubeconfig with EKS cluster credentials.

    \b
    Example:
        python eks_manager.py get-credentials --cluster-name my-cluster --region us-east-1
    """
    region = region or _get_region()

    cmd = ["aws", "eks", "update-kubeconfig", "--name", cluster_name, "--region", region]
    if profile:
        cmd += ["--profile", profile]

    logger.info("Updating kubeconfig for cluster '%s' in region '%s'...", cluster_name, region)

    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        click.echo(click.style(f"✓ {output.decode().strip()}", fg="green"))
    except subprocess.CalledProcessError as exc:
        raise click.ClickException(f"aws eks update-kubeconfig failed: {exc.output.decode()}") from exc
    except FileNotFoundError:
        raise click.ClickException("AWS CLI not found. Install it from https://aws.amazon.com/cli/")


# ---------------------------------------------------------------------------
# list-clusters
# ---------------------------------------------------------------------------


@cli.command("list-clusters")
@click.option("--region", "-r", default=None, envvar="AWS_DEFAULT_REGION", help="AWS region.")
@click.option("--output", "-o", type=click.Choice(["table", "json"]), default="table", show_default=True)
def list_clusters(region: Optional[str], output: str) -> None:
    """List all EKS clusters in the specified region.

    \b
    Example:
        python eks_manager.py list-clusters --region us-east-1
        python eks_manager.py list-clusters --output json
    """
    region = region or _get_region()
    eks = _eks_client(region)

    try:
        names = eks.list_clusters()["clusters"]
    except ClientError as exc:
        raise click.ClickException(f"Failed to list clusters: {exc}") from exc

    if not names:
        click.echo(f"No EKS clusters found in region '{region}'.")
        return

    if output == "json":
        rows = []
        for name in names:
            try:
                cluster = eks.describe_cluster(name=name)["cluster"]
                rows.append({
                    "name": cluster.get("name"),
                    "status": cluster.get("status"),
                    "version": cluster.get("version"),
                    "arn": cluster.get("arn"),
                    "endpoint": cluster.get("endpoint", "provisioning"),
                })
            except ClientError:
                rows.append({"name": name, "status": "unknown"})
        click.echo(json.dumps(rows, indent=2))
    else:
        rows = []
        for name in names:
            try:
                cluster = eks.describe_cluster(name=name)["cluster"]
                rows.append({
                    "Name": cluster.get("name"),
                    "Status": cluster.get("status"),
                    "Version": cluster.get("version"),
                    "Region": region,
                })
            except ClientError:
                rows.append({"Name": name, "Status": "unknown", "Version": "—", "Region": region})
        click.echo(tabulate(rows, headers="keys", tablefmt="rounded_outline"))


# ---------------------------------------------------------------------------
# create-nodegroup
# ---------------------------------------------------------------------------


@cli.command("create-nodegroup")
@click.option("--cluster-name", "-n", required=True, envvar="EKS_CLUSTER_NAME")
@click.option("--nodegroup-name", default="nodegroup-1", show_default=True)
@click.option("--region", "-r", default=None, envvar="AWS_DEFAULT_REGION")
@click.option("--node-role-arn", required=True, envvar="EKS_NODE_ROLE_ARN", help="IAM role ARN for node instances.")
@click.option("--subnet-ids", required=True, envvar="EKS_SUBNET_IDS", help="Comma-separated subnet IDs.")
@click.option("--instance-types", default="t3.medium", show_default=True, help="Comma-separated EC2 instance types.")
@click.option("--desired-size", default=2, show_default=True, type=int)
@click.option("--min-size", default=1, show_default=True, type=int)
@click.option("--max-size", default=10, show_default=True, type=int)
@click.option("--ami-type", default="AL2_x86_64", show_default=True, help="AMI type (AL2_x86_64, BOTTLEROCKET_x86_64, etc.)")
def create_nodegroup(
    cluster_name, nodegroup_name, region, node_role_arn, subnet_ids,
    instance_types, desired_size, min_size, max_size, ami_type,
) -> None:
    """Create a managed node group for an EKS cluster.

    \b
    Example:
        python eks_manager.py create-nodegroup \\
            --cluster-name my-cluster \\
            --node-role-arn arn:aws:iam::123456789:role/node-role \\
            --subnet-ids subnet-abc,subnet-def \\
            --desired-size 3
    """
    region = region or _get_region()
    eks = _eks_client(region)

    subnets = [s.strip() for s in subnet_ids.split(",")]
    instances = [i.strip() for i in instance_types.split(",")]

    logger.info("Creating node group '%s' for cluster '%s'...", nodegroup_name, cluster_name)

    try:
        response = eks.create_nodegroup(
            clusterName=cluster_name,
            nodegroupName=nodegroup_name,
            scalingConfig={"minSize": min_size, "maxSize": max_size, "desiredSize": desired_size},
            subnets=subnets,
            instanceTypes=instances,
            amiType=ami_type,
            nodeRole=node_role_arn,
            tags={"project": "eks-automation", "managed-by": "eks-manager-cli"},
        )
        ng = response["nodegroup"]
        click.echo(
            click.style(
                f"✓ Node group '{ng['nodegroupName']}' creation initiated. "
                f"Status: {ng['status']}",
                fg="green",
            )
        )
    except ClientError as exc:
        raise click.ClickException(f"Failed to create node group: {exc}") from exc


# ---------------------------------------------------------------------------
# scale-nodegroup
# ---------------------------------------------------------------------------


@cli.command("scale-nodegroup")
@click.option("--cluster-name", "-n", required=True, envvar="EKS_CLUSTER_NAME")
@click.option("--nodegroup-name", required=True, help="Name of the node group to scale.")
@click.option("--region", "-r", default=None, envvar="AWS_DEFAULT_REGION")
@click.option("--desired-size", required=True, type=int, help="Desired number of nodes.")
@click.option("--min-size", default=None, type=int, help="Optional: update minimum size.")
@click.option("--max-size", default=None, type=int, help="Optional: update maximum size.")
def scale_nodegroup(cluster_name, nodegroup_name, region, desired_size, min_size, max_size) -> None:
    """Scale an EKS managed node group.

    \b
    Example:
        python eks_manager.py scale-nodegroup \\
            --cluster-name my-cluster \\
            --nodegroup-name nodegroup-1 \\
            --desired-size 5
    """
    region = region or _get_region()
    eks = _eks_client(region)

    logger.info("Scaling node group '%s' to %d nodes...", nodegroup_name, desired_size)

    try:
        current = eks.describe_nodegroup(clusterName=cluster_name, nodegroupName=nodegroup_name)
        current_scaling = current["nodegroup"]["scalingConfig"]

        new_min = min_size if min_size is not None else current_scaling["minSize"]
        new_max = max_size if max_size is not None else current_scaling["maxSize"]

        eks.update_nodegroup_config(
            clusterName=cluster_name,
            nodegroupName=nodegroup_name,
            scalingConfig={
                "minSize": new_min,
                "maxSize": new_max,
                "desiredSize": desired_size,
            },
        )
        click.echo(
            click.style(
                f"✓ Node group '{nodegroup_name}' scaling to {desired_size} nodes initiated.",
                fg="green",
            )
        )
    except ClientError as exc:
        raise click.ClickException(f"Failed to scale node group: {exc}") from exc


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()

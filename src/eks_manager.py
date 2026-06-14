#!/usr/bin/env python3
"""
EKS Manager - A CLI tool for managing AWS EKS clusters.
"""

import json
import logging
import subprocess
import sys

import boto3
import click
from botocore.exceptions import BotoCoreError, ClientError
from tabulate import tabulate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared CLI options / context
# ---------------------------------------------------------------------------

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def get_eks_client(region: str):
    """Return a boto3 EKS client for the given region."""
    return boto3.client("eks", region_name=region)


def get_ec2_client(region: str):
    """Return a boto3 EC2 client for the given region."""
    return boto3.client("ec2", region_name=region)


def get_iam_client():
    """Return a boto3 IAM client."""
    return boto3.client("iam")


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--region",
    "-r",
    default=None,
    envvar="AWS_DEFAULT_REGION",
    show_default=True,
    help="AWS region (overrides AWS_DEFAULT_REGION env var).",
)
@click.option("--debug", is_flag=True, default=False, help="Enable debug logging.")
@click.pass_context
def cli(ctx: click.Context, region: str, debug: bool):
    """EKS Manager - Create, manage, and delete AWS EKS clusters."""
    ctx.ensure_object(dict)
    ctx.obj["region"] = region or "us-east-1"
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled.")


# ---------------------------------------------------------------------------
# create-cluster
# ---------------------------------------------------------------------------

@cli.command("create-cluster")
@click.option("--name", "-n", required=True, help="Name of the EKS cluster.")
@click.option(
    "--region",
    "-r",
    default=None,
    envvar="AWS_DEFAULT_REGION",
    help="AWS region (overrides group-level --region).",
)
@click.option(
    "--node-type",
    default="t3.medium",
    show_default=True,
    help="EC2 instance type for worker nodes.",
)
@click.option(
    "--node-count",
    default=2,
    show_default=True,
    type=click.IntRange(1, 100),
    help="Desired number of worker nodes.",
)
@click.option(
    "--k8s-version",
    default="1.29",
    show_default=True,
    help="Kubernetes version for the cluster.",
)
@click.option(
    "--role-arn",
    required=True,
    help="IAM role ARN for the EKS cluster control plane.",
)
@click.option(
    "--node-role-arn",
    required=True,
    help="IAM role ARN for the managed node group.",
)
@click.option(
    "--subnet-ids",
    required=True,
    multiple=True,
    help="Subnet IDs for the cluster (pass multiple times).",
)
@click.option(
    "--security-group-ids",
    multiple=True,
    help="Security group IDs for the cluster (pass multiple times).",
)
@click.pass_context
def create_cluster(
    ctx: click.Context,
    name: str,
    region: str,
    node_type: str,
    node_count: int,
    k8s_version: str,
    role_arn: str,
    node_role_arn: str,
    subnet_ids: tuple,
    security_group_ids: tuple,
):
    """Create a new EKS cluster with a managed node group."""
    effective_region = region or ctx.obj["region"]
    eks = get_eks_client(effective_region)

    click.echo(f"Creating EKS cluster '{name}' in {effective_region} ...")
    logger.info(
        "Cluster config: version=%s, node_type=%s, node_count=%d",
        k8s_version,
        node_type,
        node_count,
    )

    resources_vpc_config: dict = {"subnetIds": list(subnet_ids)}
    if security_group_ids:
        resources_vpc_config["securityGroupIds"] = list(security_group_ids)

    try:
        # Create the cluster
        response = eks.create_cluster(
            name=name,
            version=k8s_version,
            roleArn=role_arn,
            resourcesVpcConfig=resources_vpc_config,
            tags={"ManagedBy": "eks-manager"},
        )
        click.echo(f"Cluster creation initiated. Status: {response['cluster']['status']}")

        # Wait for cluster to become ACTIVE
        click.echo("Waiting for cluster to become ACTIVE (this may take 10-15 minutes) ...")
        waiter = eks.get_waiter("cluster_active")
        waiter.wait(name=name, WaiterConfig={"Delay": 30, "MaxAttempts": 40})
        click.secho(f"Cluster '{name}' is now ACTIVE.", fg="green")

        # Create managed node group
        click.echo(f"Creating managed node group 'default-ng' ...")
        eks.create_nodegroup(
            clusterName=name,
            nodegroupName="default-ng",
            scalingConfig={
                "minSize": 1,
                "maxSize": max(node_count * 2, 4),
                "desiredSize": node_count,
            },
            instanceTypes=[node_type],
            nodeRole=node_role_arn,
            subnets=list(subnet_ids),
            tags={"ManagedBy": "eks-manager"},
        )

        ng_waiter = eks.get_waiter("nodegroup_active")
        ng_waiter.wait(
            clusterName=name,
            nodegroupName="default-ng",
            WaiterConfig={"Delay": 30, "MaxAttempts": 40},
        )
        click.secho("Node group 'default-ng' is ACTIVE.", fg="green")

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        error_msg = exc.response["Error"]["Message"]
        logger.error("AWS ClientError [%s]: %s", error_code, error_msg)
        raise click.ClickException(f"[{error_code}] {error_msg}") from exc
    except BotoCoreError as exc:
        logger.error("BotoCoreError: %s", exc)
        raise click.ClickException(str(exc)) from exc


# ---------------------------------------------------------------------------
# delete-cluster
# ---------------------------------------------------------------------------

@cli.command("delete-cluster")
@click.option("--name", "-n", required=True, help="Name of the EKS cluster to delete.")
@click.option(
    "--region",
    "-r",
    default=None,
    envvar="AWS_DEFAULT_REGION",
    help="AWS region.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt.",
)
@click.pass_context
def delete_cluster(ctx: click.Context, name: str, region: str, yes: bool):
    """Delete an EKS cluster and all its managed node groups."""
    effective_region = region or ctx.obj["region"]
    eks = get_eks_client(effective_region)

    if not yes:
        click.confirm(
            f"Are you sure you want to delete cluster '{name}' in {effective_region}? "
            "This action is irreversible.",
            abort=True,
        )

    try:
        # List and delete node groups first
        ng_response = eks.list_nodegroups(clusterName=name)
        for ng in ng_response.get("nodegroups", []):
            click.echo(f"Deleting node group '{ng}' ...")
            eks.delete_nodegroup(clusterName=name, nodegroupName=ng)
            waiter = eks.get_waiter("nodegroup_deleted")
            waiter.wait(
                clusterName=name,
                nodegroupName=ng,
                WaiterConfig={"Delay": 30, "MaxAttempts": 40},
            )
            click.echo(f"Node group '{ng}' deleted.")

        # Delete the cluster
        click.echo(f"Deleting cluster '{name}' ...")
        eks.delete_cluster(name=name)
        waiter = eks.get_waiter("cluster_deleted")
        waiter.wait(name=name, WaiterConfig={"Delay": 30, "MaxAttempts": 40})
        click.secho(f"Cluster '{name}' has been deleted.", fg="yellow")

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        error_msg = exc.response["Error"]["Message"]
        logger.error("AWS ClientError [%s]: %s", error_code, error_msg)
        raise click.ClickException(f"[{error_code}] {error_msg}") from exc
    except BotoCoreError as exc:
        logger.error("BotoCoreError: %s", exc)
        raise click.ClickException(str(exc)) from exc


# ---------------------------------------------------------------------------
# update-kubeconfig
# ---------------------------------------------------------------------------

@cli.command("update-kubeconfig")
@click.option("--name", "-n", required=True, help="Name of the EKS cluster.")
@click.option(
    "--region",
    "-r",
    default=None,
    envvar="AWS_DEFAULT_REGION",
    help="AWS region.",
)
@click.option(
    "--role-arn",
    default=None,
    help="IAM role ARN to assume when generating kubeconfig.",
)
@click.option(
    "--kubeconfig",
    default=None,
    help="Path to the kubeconfig file (default: ~/.kube/config).",
)
@click.pass_context
def update_kubeconfig(
    ctx: click.Context,
    name: str,
    region: str,
    role_arn: str,
    kubeconfig: str,
):
    """Update local kubeconfig for kubectl access to the EKS cluster."""
    effective_region = region or ctx.obj["region"]

    cmd = [
        "aws",
        "eks",
        "update-kubeconfig",
        "--name",
        name,
        "--region",
        effective_region,
    ]
    if role_arn:
        cmd += ["--role-arn", role_arn]
    if kubeconfig:
        cmd += ["--kubeconfig", kubeconfig]

    click.echo(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        click.secho(result.stdout.strip(), fg="green")
    except subprocess.CalledProcessError as exc:
        logger.error("aws cli error: %s", exc.stderr)
        raise click.ClickException(exc.stderr) from exc
    except FileNotFoundError as exc:
        raise click.ClickException(
            "AWS CLI not found. Install it from https://aws.amazon.com/cli/"
        ) from exc


# ---------------------------------------------------------------------------
# list-clusters
# ---------------------------------------------------------------------------

@cli.command("list-clusters")
@click.option(
    "--region",
    "-r",
    default=None,
    envvar="AWS_DEFAULT_REGION",
    help="AWS region.",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format.",
)
@click.pass_context
def list_clusters(ctx: click.Context, region: str, output: str):
    """List all EKS clusters in the specified region."""
    effective_region = region or ctx.obj["region"]
    eks = get_eks_client(effective_region)

    try:
        cluster_names = eks.list_clusters().get("clusters", [])
        if not cluster_names:
            click.echo(f"No EKS clusters found in {effective_region}.")
            return

        rows = []
        for cname in cluster_names:
            desc = eks.describe_cluster(name=cname)["cluster"]
            rows.append(
                {
                    "Name": desc["name"],
                    "Status": desc["status"],
                    "Version": desc["version"],
                    "Endpoint": desc.get("endpoint", "N/A"),
                    "Region": effective_region,
                    "Created": str(desc.get("createdAt", "N/A")),
                }
            )

        if output == "json":
            click.echo(json.dumps(rows, indent=2, default=str))
        else:
            click.echo(
                tabulate(rows, headers="keys", tablefmt="rounded_outline")
            )

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        error_msg = exc.response["Error"]["Message"]
        logger.error("AWS ClientError [%s]: %s", error_code, error_msg)
        raise click.ClickException(f"[{error_code}] {error_msg}") from exc
    except BotoCoreError as exc:
        logger.error("BotoCoreError: %s", exc)
        raise click.ClickException(str(exc)) from exc


# ---------------------------------------------------------------------------
# scale-nodegroup
# ---------------------------------------------------------------------------

@cli.command("scale-nodegroup")
@click.option("--cluster", "-c", required=True, help="Name of the EKS cluster.")
@click.option(
    "--nodegroup",
    "-g",
    required=True,
    help="Name of the managed node group to scale.",
)
@click.option(
    "--desired",
    "-d",
    required=True,
    type=click.IntRange(0, 1000),
    help="Desired number of nodes.",
)
@click.option(
    "--min-size",
    default=None,
    type=click.IntRange(0, 1000),
    help="Minimum number of nodes (optional, updates scaling config).",
)
@click.option(
    "--max-size",
    default=None,
    type=click.IntRange(0, 1000),
    help="Maximum number of nodes (optional, updates scaling config).",
)
@click.option(
    "--region",
    "-r",
    default=None,
    envvar="AWS_DEFAULT_REGION",
    help="AWS region.",
)
@click.pass_context
def scale_nodegroup(
    ctx: click.Context,
    cluster: str,
    nodegroup: str,
    desired: int,
    min_size: int,
    max_size: int,
    region: str,
):
    """Scale a managed node group to the desired node count."""
    effective_region = region or ctx.obj["region"]
    eks = get_eks_client(effective_region)

    try:
        # Fetch current scaling config
        ng_desc = eks.describe_nodegroup(clusterName=cluster, nodegroupName=nodegroup)
        current = ng_desc["nodegroup"]["scalingConfig"]
        click.echo(
            f"Current scaling config: min={current['minSize']}, "
            f"max={current['maxSize']}, desired={current['desiredSize']}"
        )

        new_min = min_size if min_size is not None else current["minSize"]
        new_max = max_size if max_size is not None else current["maxSize"]

        # Guard rails
        if desired < new_min:
            raise click.ClickException(
                f"desired ({desired}) cannot be less than minSize ({new_min})."
            )
        if desired > new_max:
            raise click.ClickException(
                f"desired ({desired}) cannot be greater than maxSize ({new_max})."
            )

        eks.update_nodegroup_config(
            clusterName=cluster,
            nodegroupName=nodegroup,
            scalingConfig={
                "minSize": new_min,
                "maxSize": new_max,
                "desiredSize": desired,
            },
        )
        click.secho(
            f"Node group '{nodegroup}' scaling update requested: "
            f"min={new_min}, max={new_max}, desired={desired}",
            fg="green",
        )

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        error_msg = exc.response["Error"]["Message"]
        logger.error("AWS ClientError [%s]: %s", error_code, error_msg)
        raise click.ClickException(f"[{error_code}] {error_msg}") from exc
    except BotoCoreError as exc:
        logger.error("BotoCoreError: %s", exc)
        raise click.ClickException(str(exc)) from exc


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli(obj={})
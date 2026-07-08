"""Click-based command-line interface for the EKS automation package.

Exposes subcommands for the full cluster lifecycle:

    eks-automation create    — create a cluster
    eks-automation delete    — delete a cluster
    eks-automation list      — list clusters in a region
    eks-automation describe  — show cluster details
    eks-automation scale     — scale a managed node group
    eks-automation upgrade   — upgrade the Kubernetes version
    eks-automation kubeconfig — emit a kubeconfig for the cluster
"""

from __future__ import annotations

import json
from dataclasses import asdict

import click

from . import __version__
from .config import EKSSettings
from .exceptions import EKSAutomationError
from .logging_config import configure_logging
from .manager import EKSManager


def _manager(ctx: click.Context) -> EKSManager:
    """Return the :class:`EKSManager` stored on the Click context."""
    return ctx.obj["manager"]


@click.group()
@click.version_option(__version__, prog_name="eks-automation")
@click.option("--region", "-r", default=None, help="AWS region (overrides EKS_AWS_REGION).")
@click.option("--profile", "-p", default=None, help="Named AWS profile.")
@click.option("--log-level", default=None, help="Logging verbosity (e.g. DEBUG, INFO).")
@click.pass_context
def cli(ctx: click.Context, region: str | None, profile: str | None, log_level: str | None) -> None:
    """Provision and manage AWS EKS clusters from the command line."""
    overrides: dict[str, object] = {}
    if region:
        overrides["aws_region"] = region
    if profile:
        overrides["aws_profile"] = profile
    if log_level:
        overrides["log_level"] = log_level

    settings = EKSSettings(**overrides)
    configure_logging(settings.log_level)

    ctx.ensure_object(dict)
    ctx.obj["settings"] = settings
    ctx.obj["manager"] = EKSManager(settings=settings)


@cli.command("create")
@click.option("--cluster-name", "-n", required=True, help="Name of the EKS cluster.")
@click.option("--role-arn", required=True, help="IAM role ARN for the EKS control plane.")
@click.option("--subnet-ids", required=True, help="Comma-separated subnet IDs.")
@click.option("--security-group-ids", default=None, help="Comma-separated security group IDs.")
@click.option("--kubernetes-version", default=None, help="Kubernetes version.")
@click.option("--wait/--no-wait", default=False, help="Block until the cluster is ACTIVE.")
@click.pass_context
def create(
    ctx: click.Context,
    cluster_name: str,
    role_arn: str,
    subnet_ids: str,
    security_group_ids: str | None,
    kubernetes_version: str | None,
    wait: bool,
) -> None:
    """Create a new EKS cluster."""
    manager = _manager(ctx)
    try:
        cluster = manager.create_cluster(
            cluster_name=cluster_name,
            role_arn=role_arn,
            subnet_ids=_split(subnet_ids),
            security_group_ids=_split(security_group_ids) if security_group_ids else None,
            kubernetes_version=kubernetes_version,
        )
        click.secho(f"Cluster '{cluster.name}' creation initiated (status: {cluster.status}).", fg="green")
        if wait:
            cluster = manager.wait_for_active(cluster_name)
            click.secho(f"Cluster '{cluster.name}' is now {cluster.status}.", fg="green")
    except EKSAutomationError as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command("delete")
@click.option("--cluster-name", "-n", required=True, help="Name of the EKS cluster.")
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@click.pass_context
def delete(ctx: click.Context, cluster_name: str, yes: bool) -> None:
    """Delete an EKS cluster."""
    if not yes:
        click.confirm(f"Delete cluster '{cluster_name}'?", abort=True)
    try:
        _manager(ctx).delete_cluster(cluster_name)
        click.secho(f"Cluster '{cluster_name}' deletion initiated.", fg="green")
    except EKSAutomationError as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command("list")
@click.option("--output", "-o", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def list_clusters(ctx: click.Context, output: str) -> None:
    """List EKS clusters in the configured region."""
    manager = _manager(ctx)
    try:
        names = manager.list_clusters()
    except EKSAutomationError as exc:
        raise click.ClickException(str(exc)) from exc

    if output == "json":
        click.echo(json.dumps(names, indent=2))
        return
    if not names:
        click.echo("No EKS clusters found.")
        return
    for name in names:
        click.echo(f"- {name}")


@cli.command("describe")
@click.option("--cluster-name", "-n", required=True, help="Name of the EKS cluster.")
@click.option("--output", "-o", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def describe(ctx: click.Context, cluster_name: str, output: str) -> None:
    """Show details of an EKS cluster."""
    try:
        cluster = _manager(ctx).describe_cluster(cluster_name)
    except EKSAutomationError as exc:
        raise click.ClickException(str(exc)) from exc

    data = asdict(cluster)
    if output == "json":
        click.echo(json.dumps(data, indent=2, default=str))
        return
    width = max(len(k) for k in data)
    for key, value in data.items():
        click.echo(f"{key.ljust(width)} : {value if value is not None else '-'}")


@cli.command("scale")
@click.option("--cluster-name", "-n", required=True, help="Name of the EKS cluster.")
@click.option("--nodegroup-name", required=True, help="Name of the node group to scale.")
@click.option("--desired-size", required=True, type=int, help="Desired number of nodes.")
@click.option("--min-size", default=None, type=int, help="Optional new minimum size.")
@click.option("--max-size", default=None, type=int, help="Optional new maximum size.")
@click.pass_context
def scale(
    ctx: click.Context,
    cluster_name: str,
    nodegroup_name: str,
    desired_size: int,
    min_size: int | None,
    max_size: int | None,
) -> None:
    """Scale a managed node group."""
    try:
        update_id = _manager(ctx).scale_nodegroup(
            cluster_name=cluster_name,
            nodegroup_name=nodegroup_name,
            desired_size=desired_size,
            min_size=min_size,
            max_size=max_size,
        )
        click.secho(f"Scaling initiated (update {update_id}).", fg="green")
    except EKSAutomationError as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command("upgrade")
@click.option("--cluster-name", "-n", required=True, help="Name of the EKS cluster.")
@click.option("--kubernetes-version", required=True, help="Target Kubernetes version.")
@click.pass_context
def upgrade(ctx: click.Context, cluster_name: str, kubernetes_version: str) -> None:
    """Upgrade the Kubernetes version of the control plane."""
    try:
        update_id = _manager(ctx).update_kubernetes_version(cluster_name, kubernetes_version)
        click.secho(f"Upgrade to {kubernetes_version} initiated (update {update_id}).", fg="green")
    except EKSAutomationError as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command("kubeconfig")
@click.option("--cluster-name", "-n", required=True, help="Name of the EKS cluster.")
@click.pass_context
def kubeconfig(ctx: click.Context, cluster_name: str) -> None:
    """Emit a kubeconfig document for the cluster to stdout."""
    try:
        import yaml

        config = _manager(ctx).generate_kubeconfig(cluster_name)
        click.echo(yaml.safe_dump(config, sort_keys=False))
    except EKSAutomationError as exc:
        raise click.ClickException(str(exc)) from exc


def _split(value: str) -> list[str]:
    """Split a comma-separated option value into a clean list."""
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    """Entry point wired to the ``eks-automation`` console script."""
    cli(obj={})


if __name__ == "__main__":
    main()

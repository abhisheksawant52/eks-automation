"""A typed boto3 wrapper for provisioning and managing AWS EKS clusters.

The :class:`EKSManager` centralises all interaction with the EKS, EC2, and IAM
APIs so the CLI and other callers work against a small, well-documented surface.
External AWS calls require valid credentials at runtime; the standard boto3
credential chain (environment variables, shared config/credentials, or an
instance/role profile) is used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError, WaiterError

from .config import EKSSettings
from .exceptions import (
    ClusterNotFoundError,
    ClusterOperationError,
    NodeGroupNotFoundError,
    WaiterTimeoutError,
)
from .logging_config import get_logger
from .models import ClusterInfo, NodeGroupInfo

if TYPE_CHECKING:  # pragma: no cover - typing only
    from botocore.client import BaseClient

logger = get_logger(__name__)

_DEFAULT_CLUSTER_LOG_TYPES = ["api", "audit", "authenticator"]
_DEFAULT_TAGS = {"project": "eks-automation", "managed-by": "eks-automation-cli"}


class EKSManager:
    """High-level manager for EKS clusters and managed node groups.

    Args:
        settings: Package configuration. Defaults to values from the
            environment via :class:`~eks_automation.config.EKSSettings`.
        session: Optional pre-built boto3 session (useful for testing or when
            a caller wants to inject custom credentials).
    """

    def __init__(
        self,
        settings: EKSSettings | None = None,
        session: boto3.session.Session | None = None,
    ) -> None:
        self.settings = settings or EKSSettings()
        self._session = session or boto3.session.Session(
            region_name=self.settings.aws_region,
            profile_name=self.settings.aws_profile,
        )
        self._eks: BaseClient | None = None
        self._ec2: BaseClient | None = None
        self._iam: BaseClient | None = None

    # -- Lazy clients -------------------------------------------------------

    @property
    def eks(self) -> BaseClient:
        """Lazily-created EKS client."""
        if self._eks is None:
            self._eks = self._session.client("eks")
        return self._eks

    @property
    def ec2(self) -> BaseClient:
        """Lazily-created EC2 client."""
        if self._ec2 is None:
            self._ec2 = self._session.client("ec2")
        return self._ec2

    @property
    def iam(self) -> BaseClient:
        """Lazily-created IAM client."""
        if self._iam is None:
            self._iam = self._session.client("iam")
        return self._iam

    # -- Cluster operations -------------------------------------------------

    def create_cluster(
        self,
        cluster_name: str,
        role_arn: str,
        subnet_ids: list[str],
        security_group_ids: list[str] | None = None,
        kubernetes_version: str | None = None,
        endpoint_public_access: bool = True,
        endpoint_private_access: bool = False,
        tags: dict[str, str] | None = None,
    ) -> ClusterInfo:
        """Create a new EKS control plane.

        Args:
            cluster_name: Name for the new cluster.
            role_arn: ARN of the IAM role the EKS control plane assumes.
            subnet_ids: Subnet IDs (at least two, in different AZs).
            security_group_ids: Optional additional security groups.
            kubernetes_version: Kubernetes version; defaults to settings.
            endpoint_public_access: Whether the API server is publicly reachable.
            endpoint_private_access: Whether the API server is reachable in-VPC.
            tags: Optional resource tags merged with the package defaults.

        Returns:
            A :class:`~eks_automation.models.ClusterInfo` describing the cluster.

        Raises:
            ClusterOperationError: If the EKS API rejects the request.
        """
        vpc_config: dict[str, Any] = {
            "subnetIds": subnet_ids,
            "endpointPublicAccess": endpoint_public_access,
            "endpointPrivateAccess": endpoint_private_access,
        }
        if security_group_ids:
            vpc_config["securityGroupIds"] = security_group_ids

        logger.info("Creating EKS cluster %r in %s", cluster_name, self.settings.aws_region)
        try:
            response = self.eks.create_cluster(
                name=cluster_name,
                version=kubernetes_version or self.settings.kubernetes_version,
                roleArn=role_arn,
                resourcesVpcConfig=vpc_config,
                logging={"clusterLogging": [{"types": _DEFAULT_CLUSTER_LOG_TYPES, "enabled": True}]},
                tags={**_DEFAULT_TAGS, **(tags or {})},
            )
        except ClientError as exc:  # pragma: no cover - network path
            raise ClusterOperationError(f"Failed to create cluster {cluster_name!r}: {exc}") from exc
        return ClusterInfo.from_api(response["cluster"])

    def describe_cluster(self, cluster_name: str) -> ClusterInfo:
        """Return details for a single cluster.

        Args:
            cluster_name: Name of the cluster to describe.

        Returns:
            A :class:`~eks_automation.models.ClusterInfo` instance.

        Raises:
            ClusterNotFoundError: If the cluster does not exist.
            ClusterOperationError: For any other API failure.
        """
        try:
            response = self.eks.describe_cluster(name=cluster_name)
        except ClientError as exc:  # pragma: no cover - network path
            if _error_code(exc) == "ResourceNotFoundException":
                raise ClusterNotFoundError(f"Cluster {cluster_name!r} not found.") from exc
            raise ClusterOperationError(f"Failed to describe cluster {cluster_name!r}: {exc}") from exc
        return ClusterInfo.from_api(response["cluster"])

    def list_clusters(self) -> list[str]:
        """List the names of all EKS clusters in the configured region.

        Returns:
            A list of cluster names (possibly empty).

        Raises:
            ClusterOperationError: If the EKS API call fails.
        """
        names: list[str] = []
        try:
            paginator = self.eks.get_paginator("list_clusters")
            for page in paginator.paginate():
                names.extend(page.get("clusters", []))
        except ClientError as exc:  # pragma: no cover - network path
            raise ClusterOperationError(f"Failed to list clusters: {exc}") from exc
        return names

    def delete_cluster(self, cluster_name: str) -> None:
        """Delete an EKS cluster.

        Node groups attached to the cluster must be removed first; the EKS API
        will reject deletion otherwise.

        Args:
            cluster_name: Name of the cluster to delete.

        Raises:
            ClusterNotFoundError: If the cluster does not exist.
            ClusterOperationError: For any other API failure.
        """
        logger.info("Deleting EKS cluster %r", cluster_name)
        try:
            self.eks.delete_cluster(name=cluster_name)
        except ClientError as exc:  # pragma: no cover - network path
            if _error_code(exc) == "ResourceNotFoundException":
                raise ClusterNotFoundError(f"Cluster {cluster_name!r} not found.") from exc
            raise ClusterOperationError(f"Failed to delete cluster {cluster_name!r}: {exc}") from exc

    def update_kubernetes_version(self, cluster_name: str, kubernetes_version: str) -> str:
        """Upgrade the control plane to a new Kubernetes version.

        Args:
            cluster_name: Name of the cluster to upgrade.
            kubernetes_version: Target Kubernetes version (one minor at a time).

        Returns:
            The update ID returned by EKS, for tracking progress.

        Raises:
            ClusterNotFoundError: If the cluster does not exist.
            ClusterOperationError: For any other API failure.
        """
        logger.info("Upgrading cluster %r to Kubernetes %s", cluster_name, kubernetes_version)
        try:
            response = self.eks.update_cluster_version(
                name=cluster_name, version=kubernetes_version
            )
        except ClientError as exc:  # pragma: no cover - network path
            if _error_code(exc) == "ResourceNotFoundException":
                raise ClusterNotFoundError(f"Cluster {cluster_name!r} not found.") from exc
            raise ClusterOperationError(f"Failed to upgrade cluster {cluster_name!r}: {exc}") from exc
        return response["update"]["id"]

    def wait_for_active(self, cluster_name: str, max_attempts: int = 40) -> ClusterInfo:
        """Block until a cluster reaches the ``ACTIVE`` state.

        Args:
            cluster_name: Name of the cluster to wait on.
            max_attempts: Maximum number of 30-second polling attempts.

        Returns:
            The :class:`~eks_automation.models.ClusterInfo` once active.

        Raises:
            WaiterTimeoutError: If the cluster is not active within the budget.
        """
        logger.info("Waiting for cluster %r to become ACTIVE", cluster_name)
        try:
            waiter = self.eks.get_waiter("cluster_active")
            waiter.wait(
                name=cluster_name,
                WaiterConfig={"Delay": 30, "MaxAttempts": max_attempts},
            )
        except WaiterError as exc:  # pragma: no cover - network path
            raise WaiterTimeoutError(
                f"Cluster {cluster_name!r} did not become ACTIVE in time."
            ) from exc
        return self.describe_cluster(cluster_name)

    # -- Node group operations ---------------------------------------------

    def create_nodegroup(
        self,
        cluster_name: str,
        nodegroup_name: str,
        node_role_arn: str,
        subnet_ids: list[str],
        instance_types: list[str] | None = None,
        min_size: int | None = None,
        max_size: int | None = None,
        desired_size: int | None = None,
        ami_type: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> NodeGroupInfo:
        """Create a managed node group for an existing cluster.

        Args:
            cluster_name: Name of the parent cluster.
            nodegroup_name: Name for the new node group.
            node_role_arn: ARN of the IAM role node instances assume.
            subnet_ids: Subnet IDs the nodes are launched into.
            instance_types: EC2 instance types; defaults to settings.
            min_size: Minimum node count; defaults to settings.
            max_size: Maximum node count; defaults to settings.
            desired_size: Desired node count; defaults to settings.
            ami_type: AMI type; defaults to settings.
            tags: Optional resource tags merged with the package defaults.

        Returns:
            A :class:`~eks_automation.models.NodeGroupInfo` instance.

        Raises:
            ClusterOperationError: If the EKS API rejects the request.
        """
        scaling = {
            "minSize": min_size if min_size is not None else self.settings.node_min_size,
            "maxSize": max_size if max_size is not None else self.settings.node_max_size,
            "desiredSize": desired_size if desired_size is not None else self.settings.node_desired_size,
        }
        logger.info("Creating node group %r on cluster %r", nodegroup_name, cluster_name)
        try:
            response = self.eks.create_nodegroup(
                clusterName=cluster_name,
                nodegroupName=nodegroup_name,
                nodeRole=node_role_arn,
                subnets=subnet_ids,
                instanceTypes=instance_types or self.settings.node_instance_types,
                amiType=ami_type or self.settings.node_ami_type,
                scalingConfig=scaling,
                tags={**_DEFAULT_TAGS, **(tags or {})},
            )
        except ClientError as exc:  # pragma: no cover - network path
            raise ClusterOperationError(
                f"Failed to create node group {nodegroup_name!r}: {exc}"
            ) from exc
        return NodeGroupInfo.from_api(response["nodegroup"])

    def scale_nodegroup(
        self,
        cluster_name: str,
        nodegroup_name: str,
        desired_size: int,
        min_size: int | None = None,
        max_size: int | None = None,
    ) -> str:
        """Adjust the scaling configuration of a managed node group.

        Any bound left as ``None`` is preserved from the node group's current
        configuration.

        Args:
            cluster_name: Name of the parent cluster.
            nodegroup_name: Name of the node group to scale.
            desired_size: New desired node count.
            min_size: Optional new minimum node count.
            max_size: Optional new maximum node count.

        Returns:
            The update ID returned by EKS.

        Raises:
            NodeGroupNotFoundError: If the node group does not exist.
            ClusterOperationError: For any other API failure.
        """
        try:
            current = self.eks.describe_nodegroup(
                clusterName=cluster_name, nodegroupName=nodegroup_name
            )["nodegroup"]["scalingConfig"]
        except ClientError as exc:  # pragma: no cover - network path
            if _error_code(exc) == "ResourceNotFoundException":
                raise NodeGroupNotFoundError(
                    f"Node group {nodegroup_name!r} not found on {cluster_name!r}."
                ) from exc
            raise ClusterOperationError(f"Failed to describe node group: {exc}") from exc

        scaling = {
            "minSize": min_size if min_size is not None else current["minSize"],
            "maxSize": max_size if max_size is not None else current["maxSize"],
            "desiredSize": desired_size,
        }
        logger.info("Scaling node group %r to desired=%d", nodegroup_name, desired_size)
        try:
            response = self.eks.update_nodegroup_config(
                clusterName=cluster_name,
                nodegroupName=nodegroup_name,
                scalingConfig=scaling,
            )
        except ClientError as exc:  # pragma: no cover - network path
            raise ClusterOperationError(
                f"Failed to scale node group {nodegroup_name!r}: {exc}"
            ) from exc
        return response["update"]["id"]

    # -- Access -------------------------------------------------------------

    def generate_kubeconfig(self, cluster_name: str) -> dict[str, Any]:
        """Build a kubeconfig document for authenticating to the cluster.

        The generated document uses the ``aws eks get-token`` exec plugin, which
        mirrors the behaviour of ``aws eks update-kubeconfig``.

        Args:
            cluster_name: Name of the cluster to target.

        Returns:
            A kubeconfig mapping suitable for serialisation to YAML.

        Raises:
            ClusterNotFoundError: If the cluster does not exist.
        """
        cluster = self.describe_cluster(cluster_name)
        arn = cluster.arn or cluster_name

        exec_args = ["eks", "get-token", "--cluster-name", cluster_name]
        if self.settings.aws_profile:
            exec_args += ["--profile", self.settings.aws_profile]

        return {
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [
                {
                    "name": arn,
                    "cluster": {
                        "server": cluster.endpoint,
                        "certificate-authority-data": cluster.certificate_authority,
                    },
                }
            ],
            "contexts": [{"name": arn, "context": {"cluster": arn, "user": arn}}],
            "current-context": arn,
            "users": [
                {
                    "name": arn,
                    "user": {
                        "exec": {
                            "apiVersion": "client.authentication.k8s.io/v1beta1",
                            "command": "aws",
                            "args": exec_args,
                            "env": [
                                {"name": "AWS_REGION", "value": self.settings.aws_region}
                            ],
                        }
                    },
                }
            ],
        }


def _error_code(exc: ClientError) -> str:
    """Extract the AWS error code from a :class:`ClientError`."""
    return exc.response.get("Error", {}).get("Code", "")

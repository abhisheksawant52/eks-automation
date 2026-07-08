"""Lightweight, typed views over EKS API responses.

These dataclasses normalise the loosely-typed dictionaries returned by boto3
into predictable objects that the CLI and callers can rely on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ClusterInfo:
    """A concise summary of an EKS cluster."""

    name: str
    status: str
    version: str
    arn: str | None = None
    endpoint: str | None = None
    role_arn: str | None = None
    certificate_authority: str | None = None

    @classmethod
    def from_api(cls, cluster: dict[str, Any]) -> ClusterInfo:
        """Build a :class:`ClusterInfo` from an ``eks:DescribeCluster`` payload."""
        ca = cluster.get("certificateAuthority") or {}
        return cls(
            name=cluster.get("name", ""),
            status=cluster.get("status", "UNKNOWN"),
            version=cluster.get("version", ""),
            arn=cluster.get("arn"),
            endpoint=cluster.get("endpoint"),
            role_arn=cluster.get("roleArn"),
            certificate_authority=ca.get("data"),
        )


@dataclass(frozen=True, slots=True)
class NodeGroupInfo:
    """A concise summary of an EKS managed node group."""

    name: str
    status: str
    instance_types: list[str] = field(default_factory=list)
    min_size: int = 0
    max_size: int = 0
    desired_size: int = 0
    ami_type: str | None = None

    @classmethod
    def from_api(cls, nodegroup: dict[str, Any]) -> NodeGroupInfo:
        """Build a :class:`NodeGroupInfo` from an ``eks:DescribeNodegroup`` payload."""
        scaling = nodegroup.get("scalingConfig") or {}
        return cls(
            name=nodegroup.get("nodegroupName", ""),
            status=nodegroup.get("status", "UNKNOWN"),
            instance_types=list(nodegroup.get("instanceTypes", [])),
            min_size=scaling.get("minSize", 0),
            max_size=scaling.get("maxSize", 0),
            desired_size=scaling.get("desiredSize", 0),
            ami_type=nodegroup.get("amiType"),
        )

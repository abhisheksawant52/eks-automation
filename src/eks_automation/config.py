"""Runtime configuration for the EKS automation package.

Settings are loaded (in order of precedence) from explicit constructor arguments,
environment variables prefixed with ``EKS_``, and an optional ``.env`` file. See
``.env.example`` in the repository root for the full list of supported variables.
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EKSSettings(BaseSettings):
    """Typed configuration for provisioning and managing EKS clusters.

    Attributes:
        aws_region: AWS region in which clusters are managed.
        aws_profile: Optional named AWS CLI/SDK profile to use for credentials.
        cluster_name: Default EKS cluster name for operations.
        kubernetes_version: Target Kubernetes minor version (e.g. ``1.30``).
        node_instance_types: EC2 instance types for managed node groups.
        node_min_size: Minimum node count for the managed node group.
        node_max_size: Maximum node count for the managed node group.
        node_desired_size: Desired node count for the managed node group.
        node_ami_type: AMI type for worker nodes (e.g. ``AL2023_x86_64_STANDARD``).
        log_level: Logging verbosity (``DEBUG``, ``INFO``, ``WARNING``, ...).
    """

    model_config = SettingsConfigDict(
        env_prefix="EKS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    aws_region: str = Field(default="us-east-1", description="AWS region.")
    aws_profile: str | None = Field(default=None, description="Named AWS profile.")
    cluster_name: str = Field(default="eks-automation-cluster", description="Cluster name.")
    kubernetes_version: str = Field(default="1.30", description="Kubernetes version.")
    node_instance_types: list[str] = Field(
        default_factory=lambda: ["t3.medium"],
        description="EC2 instance types for managed node groups.",
    )
    node_min_size: int = Field(default=1, ge=0, description="Minimum node count.")
    node_max_size: int = Field(default=10, ge=1, description="Maximum node count.")
    node_desired_size: int = Field(default=2, ge=0, description="Desired node count.")
    node_ami_type: str = Field(
        default="AL2023_x86_64_STANDARD",
        description="AMI type for managed node group instances.",
    )
    log_level: str = Field(default="INFO", description="Logging verbosity.")

    @field_validator("node_instance_types", mode="before")
    @classmethod
    def _split_instance_types(cls, value: object) -> object:
        """Allow a comma-separated string for ``EKS_NODE_INSTANCE_TYPES``."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalise_log_level(cls, value: object) -> object:
        """Uppercase the log level so ``info`` and ``INFO`` behave identically."""
        if isinstance(value, str):
            return value.upper()
        return value


def get_settings(**overrides: object) -> EKSSettings:
    """Build an :class:`EKSSettings` instance, applying any keyword overrides.

    Args:
        **overrides: Explicit values that take precedence over the environment.

    Returns:
        A validated :class:`EKSSettings` instance.
    """
    return EKSSettings(**overrides)

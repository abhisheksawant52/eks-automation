"""Domain-specific exceptions raised by the EKS automation package."""

from __future__ import annotations


class EKSAutomationError(Exception):
    """Base class for all errors raised by this package."""


class ClusterNotFoundError(EKSAutomationError):
    """Raised when an operation targets a cluster that does not exist."""


class NodeGroupNotFoundError(EKSAutomationError):
    """Raised when an operation targets a node group that does not exist."""


class ClusterOperationError(EKSAutomationError):
    """Raised when an EKS API call fails for an operational reason."""


class WaiterTimeoutError(EKSAutomationError):
    """Raised when a resource does not reach the expected state in time."""

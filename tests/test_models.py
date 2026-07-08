"""Unit tests for the typed API views (no network access)."""

from __future__ import annotations

import eks_automation
from eks_automation.models import ClusterInfo, NodeGroupInfo


def test_package_exposes_version() -> None:
    assert eks_automation.__version__ == "0.1.0"


def test_cluster_info_from_api() -> None:
    payload = {
        "name": "demo",
        "status": "ACTIVE",
        "version": "1.30",
        "arn": "arn:aws:eks:us-east-1:123456789012:cluster/demo",
        "endpoint": "https://example.eks.amazonaws.com",
        "certificateAuthority": {"data": "QUJD"},
    }
    info = ClusterInfo.from_api(payload)
    assert info.name == "demo"
    assert info.status == "ACTIVE"
    assert info.certificate_authority == "QUJD"


def test_nodegroup_info_from_api() -> None:
    payload = {
        "nodegroupName": "ng-1",
        "status": "ACTIVE",
        "instanceTypes": ["t3.medium"],
        "amiType": "AL2023_x86_64_STANDARD",
        "scalingConfig": {"minSize": 1, "maxSize": 5, "desiredSize": 3},
    }
    info = NodeGroupInfo.from_api(payload)
    assert info.desired_size == 3
    assert info.min_size == 1
    assert info.max_size == 5
    assert info.instance_types == ["t3.medium"]

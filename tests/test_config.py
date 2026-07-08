"""Unit tests for configuration parsing (no network access)."""

from __future__ import annotations

from eks_automation.config import EKSSettings, get_settings


def test_defaults() -> None:
    settings = EKSSettings()
    assert settings.aws_region == "us-east-1"
    assert settings.node_instance_types == ["t3.medium"]
    assert settings.node_min_size <= settings.node_desired_size <= settings.node_max_size


def test_instance_types_accepts_csv_string() -> None:
    settings = get_settings(node_instance_types="t3.large, m5.xlarge ,")
    assert settings.node_instance_types == ["t3.large", "m5.xlarge"]


def test_log_level_is_normalised() -> None:
    settings = get_settings(log_level="debug")
    assert settings.log_level == "DEBUG"

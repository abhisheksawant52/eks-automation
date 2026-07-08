"""Smoke tests for the CLI wiring (no network access)."""

from __future__ import annotations

from click.testing import CliRunner

from eks_automation.cli import cli


def test_help_lists_subcommands() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    for command in ("create", "delete", "list", "describe", "scale", "upgrade", "kubeconfig"):
        assert command in result.output


def test_version_flag() -> None:
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output

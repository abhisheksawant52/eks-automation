# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-08

### Added

- `eks-automation` CLI (Click) with `create`, `delete`, `list`, `describe`,
  `scale`, `upgrade`, and `kubeconfig` subcommands.
- `EKSManager`, a typed boto3 wrapper covering cluster and managed node group
  lifecycle, version upgrades, active-state waiting, and kubeconfig generation.
- Pydantic-settings configuration, centralised logging, and typed API models.
- Terraform root module with reusable `vpc` and `eks` modules plus `dev`/`prod`
  environment examples.
- Slim non-root Dockerfile packaging the CLI.
- Documentation, CI pipeline (lint, test matrix, Terraform validate), pre-commit
  hooks, and open-source project files.

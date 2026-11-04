# Changelog

All notable changes to the Ravenhelm Release Operations Methodology (RROM) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-04

### Added
- Initial public release of the Ravenhelm Release Operations Methodology (RROM).
- Codified 14 core chapters, two technical appendices, and eighteen numbered principles (`RP-1` through `RP-18`).
- Formalized the Core Axiom: "Builds are the unit; releases are names."
- Codified the Three Physical Release Rails:
  - Rail A: Server & Kubernetes Cluster GitOps (Harbor OCI + Argo CD; Vitki Reference).
  - Rail B: Workstation Developer CLI/TUI (Private Homebrew Tap with sandboxed formula inreplace; Ullr/Yager Reference).
  - Rail C: Client Desktop Application OTA (Signed binary archives with Minisign Ed25519; Idunn Reference).
- Defined the 4-tier Release Maturity Ladder (Tier 1: Artifact Discipline to Tier 4: Sovereign Elevation).
- High-fidelity publication typography and vector architecture diagrams for both Dark Mode (`RROM-v1.0.0-dark.pdf`) and Print Mode (`RROM-v1.0.0.pdf`).
- Formalized the RROM Community License 1.0 and commercial advisory funnel.

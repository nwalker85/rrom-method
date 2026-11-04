# Chapter 8: The Tiered Adoption Ladder

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Four Maturity Tiers of Release Operations

Just as RLOM defines an honest tiering ladder for Linear workspaces, RROM structures release operations across four maturity tiers. Teams adopt RROM incrementally, climbing the ladder only when their organizational complexity and blast radius require it.

```
[ Tier 1: Artifact Discipline ] ──> [ Tier 2: Digest Locking ] ──> [ Tier 3: Multi-Rail GitOps ] ──> [ Tier 4: Sovereign Elevation ]
```

---

## Tier 1: Artifact Discipline (The Solo Developer / Free Tier)

**Focus:** Stop rebuilding code on release.
- **Prerequisites:** GitHub or Forgejo with standard CI runners, basic container registry (Docker Hub, GitHub Packages).
- **Core Practices:**
  1. Pipeline split: CI builds on push to `main` only. Builds are labeled with sequential build numbers (`b<N>`).
  2. The release workflow is restricted to tagging and retagging existing container images. Zero compilation at tag time.
  3. Basic tag verification: a single shell script verifies that `git tag` matches the application version string.
- **Value Unlocked:** Eliminates the classic defect where code verified in staging breaks when rebuilt for production.

---

## Tier 2: Registry & Digest Locking (The Growing Startup)

**Focus:** Eliminate tag-mutation risks and enforce release parity.
- **Prerequisites:** Self-hosted or managed OCI registry (Harbor, AWS ECR), structured Helm chart or Compose stack.
- **Core Practices:**
  1. The **Triple-Tagging Scheme**: Ingress builds publish `:b<N>`, `:sha-<commit12>`, and `:uat`.
  2. **Mandatory Digest Pinning:** Production deployment manifests must pin `repository:tag@sha256:<digest>`.
  3. **Automated Release Preparation:** Adoption of `scripts/release-pr.sh` and `check-release-source-parity.sh`. Release PRs are strictly verified to contain zero source code drift.
  4. Registry v2 API automation: CI robot tokens are restricted to push/pull scopes, manipulating tags strictly through distribution manifests.
- **Value Unlocked:** Protection against image poisoning, tag overwriting, and silent dependency shifts.

---

## Tier 3: Multi-Rail Declarative GitOps (The Scaling Team)

**Focus:** Synchronize multi-surface deployments and establish GitOps authority.
- **Prerequisites:** Kubernetes cluster with Argo CD / Flux, private Homebrew tap, separate GitOps configuration repository (`norns-gitops`).
- **Core Practices:**
  1. **Strict GitOps Boundary:** Workstation developers and CI runners are stripped of cluster apply permissions. Argo CD is the sole deployment authority.
  2. **Dual-Rail Synchronization:** Repositories shipping backends and developer CLIs (e.g., Ullr/Yager) execute Rail A (K3s GitOps) and Rail B (Homebrew Tap) simultaneously within every release.
  3. **Formula Inreplace Rule:** Workstation package formulas execute dynamic version inreplace in build sandboxes, keeping source git history untouched.
  4. **The Merge-Then-Deploy Skill:** Approval to merge a release PR is codified as an instruction to drive deployment through live health verification.
- **Value Unlocked:** Zero drift between backend APIs and developer CLI tooling; total auditability of cluster state in git.

---

## Tier 4: Sovereign Elevation & Zero-Trust Delivery (The Enterprise)

**Focus:** Cryptographic elevation, blast radius isolation, and immutable audit ledgers.
- **Prerequisites:** OpenBao / HashiCorp Vault, Keycloak / Zitadel identity fabric, Valkyrie MFAA broker.
- **Core Practices:**
  1. **Blast Radius Separation:** Application deployments execute autonomously through GitOps; control plane and identity mutations (Keycloak realms, Vault policies, Harbor RBAC) are classified as high-blast-radius elevations.
  2. **Action-Hash Elevation:** High-blast mutations run read-only plans in CI, generate a SHA-256 hash of the plan, and pause for human-in-the-loop MFAA approval.
  3. **Single-Use Consumable Tokens:** Approval tokens are cryptographically bound to the plan hash and can be consumed exactly once.
  4. **Sovereign Client OTA (Rail C):** Desktop applications distribute via Minisign Ed25519 cryptographic signatures and self-hosted `latest.json` manifests.
- **Value Unlocked:** Complete defense against rogue CI runner takeovers, internal supply chain compromise, and unauthorized infrastructure alterations.

<!-- RUBRIC_CHECK: Chapter 8 conforms to RROM specification. -->

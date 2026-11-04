# Chapter 3: The Numbered Principles

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## The 18 Canonical Principles

The Ravenhelm Release Operations Methodology is anchored by eighteen numbered principles (`RP-1` through `RP-18`). Every pipeline rule, script check, and operational workflow derives directly from this canon.

---

### Category I: Artifact Custody & Immutability

#### RP-1: Build Once on Ingress
Compilation and container packaging occur exactly once, triggered by the integration event (merge to `main`). CI produces an immutable artifact identified by a cryptographic digest, an exact commit SHA, and an incremental build sequence (`:b<N>`). 
* *Failure Mode:* Rebuilding on release creates untracked binary deltas between staging and production.

#### RP-2: Releases Never Rebuild
The release lifecycle assigns a SemVer tag (`vX.Y.Z`) to an existing, pre-tested build digest. It never invokes a compiler, packager, bundler, or container build daemon.
* *Failure Mode:* Release pipelines fail midway due to transient external mirror downtime, stalling emergency deployments.

#### RP-3: Promotion by Reference
Promoting software across environments (Dev $\to$ Staging/UAT $\to$ Prod) is strictly an act of updating declarative pointer manifests to an immutable digest. Bits never move between repositories; only metadata references change.
* *Failure Mode:* Manually re-uploading artifacts across registries risks bit-rot, signature loss, and tampering.

#### RP-4: Tags for Humans, Digests for Runtime
Runtime manifests render `repository:tag@sha256:<digest>`. The tag exists solely for human readability, auditability, and CLI ergonomics; the SHA-256 digest is the kernel truth pulled and scheduled by the runtime engine.
* *Failure Mode:* Relying on mutable tags allows tag-overwriting attacks and registry caching discrepancies across cluster nodes.

#### RP-5: Parity Precedes Promotion
A release candidate must prove zero source code drift against the parent build commit (`check-release-source-parity.sh`). Release PRs touch configuration metadata (`values.yaml`, `Chart.yaml`, `CHANGELOG.md`), never application source.
* *Failure Mode:* Sneaking "just one quick fix" into a release commit bypasses the build test suite and ships unvalidated code.

---

### Category II: The Multi-Surface Rails

#### RP-6: Multi-Surface Lockstep
Repositories serving multiple surfaces (e.g., a backend service and an operator workstation CLI) must execute all applicable delivery rails within the same release cycle. A backend upgrade without matching workstation tooling is an operational outage.
* *Failure Mode:* Operators using stale CLI binaries corrupt backend databases because API contracts drifted out of lockstep.

#### RP-7: Sandboxed Inreplace for Ecosystem Tooling
When packaging workstation CLIs for package managers (e.g., Homebrew) that insist on compilation from source, the formula must execute dynamic sandboxed `inreplace` of version manifests (`Cargo.toml`, `package.json`) to preserve zero-drift git history.
* *Failure Mode:* Forcing version bumps into `Cargo.toml` on git branches dirties source commits and destroys release source parity.

#### RP-8: Sovereign Binary Distribution
Client desktop applications distribute through self-contained, signed archives bundled with cryptographic signatures (Minisign / Ed25519) and verified against machine-readable update manifests (`latest.json`).
* *Failure Mode:* Unsigned client updates invite man-in-the-middle binary tampering and break operating system security models.

---

### Category III: Deployment Authority & Cutover Governance

#### RP-9: Declarative Convergence Authority
Production servers and clusters never accept direct push deployments from developer workstations or CI scripts. An automated orchestrator (Argo CD GitOps / systemd supervisor) is the sole applying authority.
* *Failure Mode:* Manual `helm upgrade` or `kubectl apply` commands executed from engineer laptops create undocumented cluster state drift.

#### RP-10: Merge-Then-Deploy
Approval to merge an approved release PR is approval to ship. Once merged, the release pipeline executes through completion: retagging artifacts, bumping gitops manifests, triggering deployment reconciliation, and proving live health.
* *Failure Mode:* "Merge and wait" creates zombie commits in `main` that block subsequent urgent fixes.

#### RP-11: Cutovers Require ADRs
A deployment reconciles application code. A **cutover** changes the serving architecture (repo swap, datastore migration, transport change, breaking schema). Cutovers are never routine deployments; they require an Architectural Decision Record (ADR), an explicit data migration plan, and formal human-in-the-loop elevation.
* *Failure Mode:* A team deploys an architectural replacement under a routine version bump, causing catastrophic data corruption and unrecoverable downtime (the Bifrost anti-pattern).

#### RP-12: Zero Ambient CI Authority
CI runners do not possess ambient cluster-admin or root credentials. Pipeline access is strictly gated via least-privilege AppRoles (OpenBao) or action-hash bound approvals (Valkyrie).
* *Failure Mode:* Compromised CI runners expose long-lived root infrastructure tokens to supply chain adversaries.

---

### Category IV: Verification & Observability

#### RP-13: Shell Success Is Not Proof
A command or pipeline exiting with status code `0` is an unverified claim. A deployment is proven only when the running system satisfies runtime health probes (`/api/health`, pod readiness, version query) on the live network.
* *Failure Mode:* Piped commands mask shell failures, reporting "Deploy Succeeded" while container pods crash-loop in the cluster.

#### RP-14: Fail-Closed Rollback
Rollback is an instantaneous pointer repointing to the preceding immutable build digest in the gitops repository. Bad builds are never deleted; they simply never receive an approved production name.
* *Failure Mode:* Deleting bad container tags breaks immutable audit logs and makes incident post-mortems impossible.

#### RP-15: Strict SemVer Contract
Breaking an existing API schema, authz tuple, ingest payload, or sentence address requires a MAJOR version bump (or documented pre-1.0 breaking changelog entry).
* *Failure Mode:* Introducing backward-incompatible field removals in minor updates breaks downstream automation silently.

#### RP-16: Immutable Audit Ledgers
Every promotion is recorded in a tamper-evident audit ledger binding git commit SHA, build ID, registry digest, gitops PR, and the signer's identity.
* *Failure Mode:* Inability to answer "who deployed what exact bits at what time" during post-incident compliance reviews.

#### RP-17: Separation of Blast Radii
Application code deploys are autonomous (merge $\to$ deploy). Infrastructure-plane and identity-plane mutations (Keycloak, OpenBao, Harbor RBAC) are elevation events gated by single-use cryptographic approvals bound to the plan hash.
* *Failure Mode:* Treating identity configuration like application code allows rogue PRs to grant ambient admin privileges.

#### RP-18: Clean Worktree Custody
All release engineering and git operations execute from dedicated, disposable git worktrees conforming to the Checkout Custody Standard. Operators never rely on `git stash` across release branches.
* *Failure Mode:* Stashing changes across branch switches drops release commits, causing ghost diffs in production.

<!-- RUBRIC_CHECK: Chapter 3 conforms to RROM specification. -->

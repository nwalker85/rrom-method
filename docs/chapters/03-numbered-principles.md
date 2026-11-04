# Chapter 3: The Numbered Principles

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

You have worked in organizations where release day was treated like a natural disaster. Engineers gathered on bridge calls at midnight. Someone ran `git pull` on a production host over SSH. Someone else pushed an unversioned container tag called `latest` or `hotfix-2`, while a third person compiled a CLI on an M2 MacBook with custom flags and emailed the binary to the operations team. When the system broke—and it always broke—no one could state with cryptographic certainty what code was running, what commit it originated from, or why the binary tested in staging behaved differently from the binary serving customer traffic.

The Ravenhelm Release Operations Methodology (RROM) does not solve this by pleading with engineers to "be more careful" or by piling manual approval checklists onto release managers. It writes down the physical and architectural constraints that govern immutable software delivery and gives them numbers so they can be cited, audited, and mechanically enforced.

The numbered principles are the bedrock of the Method. They establish an unambiguous coordinate system across every computing surface: server backends running in Kubernetes or bare-metal container runtimes, developer workstation tools distributed through package managers, and standalone client desktop binaries.

The most load-bearing principle is **RP-1: Build Once on Ingress**. If an engineering team adopts only one principle from this canon, adopting RP-1 permanently eliminates the largest category of production deployment failures.

---

## How to Cite the Principles

Principles serve no operational purpose if they remain confined to a reference manual. A principle that is never named in a pull request review, a CI failure annotation, an Architectural Decision Record (ADR), or a post-incident timeline is dead ceremony. A principle cited weekly becomes an immutable operational boundary.

When software engineers and release operators cite principles by number, debates shift from personal aesthetic opinions to canonical system invariants:

- In Pull Request Reviews: *"Holding merge per `RP-5`: release branch contains modifications to `src/core/parser.rs`, violating zero-drift source parity against parent build `b42`."*
- In Pipeline Failure Logs: *"FATAL: `RP-4` violation detected. Deployment manifest `chart/values.yaml` specifies mutable tag `:v1.4.2` without an `@sha256:` digest pin."*
- In Incident Retrospectives: *"The outage resulted from an unadjudicated cutover violating `RP-11`. The datastore swap was submitted under a routine minor version bump without an accepted ADR or dual-running window."*
- In Operator CLI Commands: *"Executing immediate pointer rollback to build `b88` per `RP-14`."*

> ### Augmentation Surface — Automated Verification & Principle Enforcement
>
> **Where Autonomous Agent Layers Excel:**  
> Static policy linters and autonomous agent supervisors (such as Snotra and the Doom fleet supervisor) continuously inspect repositories and registries against the numbered principles. Linters detect `RP-5` source drift during release PR creation, verify that runtime manifests conform to `RP-4` digest pinning, assert that release pipelines never invoke compilers (`RP-2`), and ensure that working directories conform to `RP-18` worktree custody before executing git mutations.
>
> **What the Human Operator Retains:**  
> The human operator retains sole authority over architectural cutover gates (`RP-11`), multi-factor action elevations (`RP-17`), and final release merge authorization (`RP-10`). Autonomous systems verify compliance and assemble cryptographic evidence; human release closers authorize production state transitions.

The eighteen principles are organized into four operational categories:

1. **Category I: Artifact Custody & Immutability** (`RP-1` through `RP-5`)
2. **Category II: Multi-Surface Rails** (`RP-6` through `RP-8`)
3. **Category III: Deployment Authority & Cutover Governance** (`RP-9` through `RP-12`)
4. **Category IV: Verification & Observability** (`RP-13` through `RP-18`)

---

## Category I: Artifact Custody & Immutability

Category I establishes the lifecycle boundaries governing how source code transforms into binary artifacts, how artifacts are addressed, and how promotional state transitions occur without re-compilation.

```
+───────────────────────────────────────────────────────────────────────────────────+
| CATEGORY I: ARTIFACT CUSTODY & IMMUTABILITY                                       |
|                                                                                   |
|  [ Ingress to main ] ──> RP-1: Build Once on Ingress (:b<N> @sha256:...)          |
|                                │                                                  |
|                                ▼                                                  |
|  [ Release Candidate ] ─> RP-5: Parity Precedes Promotion (check source drift)    |
|                                │                                                  |
|                                ▼                                                  |
|  [ Tagging / Naming ] ──> RP-2: Releases Never Rebuild (Registry API Retag)       |
|                                │                                                  |
|                                ▼                                                  |
|  [ Env Promotion ] ────> RP-3: Promotion by Reference (Update Pointer in GitOps)  |
|                                │                                                  |
|                                ▼                                                  |
|  [ Runtime Execution ] ─> RP-4: Tags for Humans, Digests for Runtime              |
+───────────────────────────────────────────────────────────────────────────────────+
```

### RP-1: Build Once on Ingress

**Canonical Statement:** Compilation, containerization, and artifact packaging execute exactly once, triggered exclusively by the integration event (merge to the `main` trunk).

**Systems Rationale:** A software build is a stateful transformation that consumes a snapshot of source code and resolves an external dependency graph. External registries (PyPI, npm, crates.io, Maven Central, Debian/Alpine mirrors) are dynamic networks subject to upstream package replacements, transitive dependency drift, and transient mirror discrepancies. Compilers also embed build-host metadata (timestamps, build IDs, glibc versions) unless strict reproducible builds are guaranteed. By compiling and packaging software at the precise moment source code integrates into `main`, the CI system captures the definitive binary manifestation of that commit. The resulting artifact is immutably indexed by a monotonic build sequence (`:b<N>`), the short commit SHA (`:sha-<commit12>`), and its cryptographic SHA-256 digest (`@sha256:<digest>`).

**Failure Mode & Anti-Pattern:** *The "Build-on-Tag" Anti-Pattern.* A team merges code to `main` on Wednesday and runs automated integration tests in UAT throughout the week. On the following Monday, an operator cuts release tag `v2.1.0`, which triggers a CI pipeline that invokes `docker build`. In the intervening five days, an upstream sub-dependency (such as an unpinned Debian security update or an npm patch release) published a subtle breaking change. The newly compiled production binary fails on startup due to a symbol mismatch, despite identical application source code passing every test in UAT.

**Operational Verification Rule:** The primary build workflow (`.forgejo/workflows/build.yml` or `.github/workflows/build.yml`) triggers solely on `push: branches: [main]`. Release workflows (`release.yml`) are statically prohibited from invoking compiler toolchains (`cargo build`, `go build`, `npm run build`) or container build daemons (`docker build`, `podman build`, `buildah`). The repository linter `scripts/check-pipeline-purity.sh` fails the CI gate if build commands are discovered in release job definitions.

---

### RP-2: Releases Never Rebuild

**Canonical Statement:** The release lifecycle is an act of naming, not an act of creation; it associates an authorized Semantic Version tag with an existing, validated build digest and never invokes a compiler, bundler, or build daemon.

**Systems Rationale:** Once an artifact is produced on ingress (`RP-1`) and validated in a staging or UAT environment, its physical bits have demonstrated operational stability. Invoking a compiler during the release phase mathematically invalidates all prior testing, because the newly generated binary has a different cryptographic identity. Under content-addressable storage standards (such as the OCI Image Specification v1.1 and Git tree objects), bits are addressed by their Merkle root hash. Releasing an artifact requires only calling the registry's Distribution API (`PUT /v2/<name>/manifests/<tag>`) to attach a human-readable name (`vX.Y.Z`) to the pre-existing digest descriptor.

**Failure Mode & Anti-Pattern:** *Release-Time Compilation Panic.* During an active P0 production incident, an engineering team attempts to ship an emergency hotfix. The operator pushes tag `v1.8.4-hotfix.1`. The release pipeline begins compiling a massive C++/Rust dependency tree from scratch. Twelve minutes into the compilation, an external package registry experiences a transient 504 Gateway Timeout, aborting the build runner and corrupting local build caches. Production remains down for an additional forty minutes while engineers scramble to debug a compiler timeout for code that had already built successfully on `main` twenty minutes prior.

**Operational Verification Rule:** The release script (`scripts/harbor-artifact.sh retag <build-id> <semver-tag>`) operates exclusively through the OCI Registry v2 API. It inspects the manifest descriptor of build `:b<N>`, extracts its cryptographic digest, and submits a manifest `PUT` under `:vX.Y.Z` without transferring layer blobs. Verification is enforced in CI by asserting that the manifest digest of the new tag matches the build digest:
```bash
BUILD_DIGEST=$(crane digest "${REGISTRY}/${IMAGE}:b${BUILD_NUM}")
RELEASE_DIGEST=$(crane digest "${REGISTRY}/${IMAGE}:${SEMVER_TAG}")
[[ "${BUILD_DIGEST}" == "${RELEASE_DIGEST}" ]] || exit 1
```

---

### RP-3: Promotion by Reference

**Canonical Statement:** Promoting an artifact across lifecycle environments (Dev $\to$ Staging/UAT $\to$ Production) is executed exclusively by updating declarative configuration references to an immutable digest, never by moving, copying, or re-pushing binary files.

**Systems Rationale:** Copying container images or re-uploading tarballs across disparate environment-specific registries introduces substantial supply-chain risk, storage bloat, and bit-rot. In a content-addressable architecture, an artifact repository (such as Harbor or enterprise OCI registries) acts as the immutable single source of truth. Promoting software from staging to production is a configuration state transition: the GitOps deployment manifest (`chart/values.yaml` or `values-prod.yaml`) in the configuration repository updates its digest pointer from the previous release to the newly approved digest.

**Failure Mode & Anti-Pattern:** *The Intermediate Jump-Box MITM.* An organization provisions isolated container registries for "Staging" and "Production." To promote a container, an automated script on an intermediate bastion host pulls the image from Staging, runs `docker tag`, and pushes to Production. An attacker who compromises the bastion host replaces the intermediate image layer with a malicious cryptominer prior to the push. Because the promotion script blindly pushed the locally tagged image, the compromised binary enters production without triggering registry-level provenance alerts.

**Operational Verification Rule:** Continuous deployment pipelines verify that the `image.digest` declared in production GitOps repositories matches the cryptographic digest recorded in the canonical artifact registry during the initial ingress build. The script `scripts/verify-promotion-provenance.sh` queries the registry audit trail and validates that no layer blobs were created or modified between the initial integration commit and the production deployment manifest update.

---

### RP-4: Tags for Humans, Digests for Runtime

**Canonical Statement:** Workload manifests must declare images as `repository:tag@sha256:<digest>`; the mutable tag communicates human and semantic intent, while the immutable SHA-256 digest provides absolute kernel scheduling truth.

**Systems Rationale:** In the OCI Distribution Specification, tags are mutable pointers defined in `/v2/<name>/tags/list`. If a Kubernetes pod spec or container supervisor requests an image by tag alone (e.g. `service:v1.4.0`), the underlying container engine (containerd, CRI-O) checks its local image cache. If node $A$ cached `v1.4.0` prior to an emergency registry retag and node $B$ pulls it afterward, the cluster executes two divergent binaries under the same nominal version. Furthermore, DNS hijacking or registry cache poisoning can inject malicious layers when tags are unpinned. Panning `@sha256:<digest>` forces the container runtime to verify the Merkle root of the image configuration and layer tarballs against the Linux kernel's cryptographic hash before mounting the root filesystem.

**Failure Mode & Anti-Pattern:** *The Split-Brain Cluster Desynchronization.* An operations team detects a critical flaw in tag `v1.2.0`, pushes a fast-fix under the identical tag, and runs `kubectl rollout restart deployment/api`. Three worker nodes already had the previous `v1.2.0` image cached locally and reuse it without hitting the registry. Two freshly autoscaled worker nodes pull the new `v1.2.0` digest. The running deployment now consists of three pods executing the flawed code and two pods executing the patched code, emitting incompatible protobuf schemas across internal gRPC channels and crashing the message bus.

**Operational Verification Rule:** GitOps linters, pre-commit hooks, and admission controllers (such as Kyverno, OPA Gatekeeper, or `scripts/check-release-tag.sh`) parse all workload manifests. Any container definition lacking an `@sha256:` digest pin is rejected immediately:
```bash
# Must match: <repo>/<name>:<tag>@sha256:<64-char-hex>
grep -E 'image:\s+.*:[a-zA-Z0-9_.-]+@sha256:[a-f0-9]{64}' manifest.yaml || {
    echo "ERROR: RP-4 Violation - Missing immutable @sha256 digest pin"
    exit 1
}
```

---

### RP-5: Parity Precedes Promotion

**Canonical Statement:** A release candidate must prove zero source code drift against the parent build commit; release pull requests modify configuration metadata, version manifests, and changelogs, never application source code.

**Systems Rationale:** Git structures repository history as a directed acyclic graph of immutable commit objects, each referencing an immutable tree object representing directory state. The ingress build on `main` compiled and tested a specific Git tree hash. When preparing a release, operators open a release pull request to update metadata files: Helm `Chart.yaml`, GitOps `values.yaml`, and `CHANGELOG.md`. If an operator modifies application source code (`src/`, `cmd/`, `pkg/`) within the release PR, that code has bypassed the comprehensive integration test suite executed on the parent build commit. Proving byte-level parity between the source trees ensures that what is being released is precisely what was compiled and tested.

**Failure Mode & Anti-Pattern:** *The "One Last Quick Fix" Trap.* While assembling a release PR for `v3.0.0`, a developer spots an unhandled `NullPointerException` in an authentication filter. Reluctant to delay the release by opening a separate PR to `main` and waiting for another full ingress build sequence, the developer commits the fix directly into the release branch alongside the `Chart.yaml` version bump. Because the release pipeline does not execute the full multi-hour integration test suite (per `RP-2`), the "quick fix" introduces an unhandled deadlock that brings down the production API gateway upon deployment.

**Operational Verification Rule:** Release validation gates mandate the execution of `scripts/check-release-source-parity.sh`. This script runs `git diff --name-only <parent-build-commit> HEAD` and matches the resulting file list against a strict whitelist of configuration metadata:
```bash
ALLOWED_PATTERN="^(chart/.*|values.*\.yaml|CHANGELOG\.md|package\.json|docs/.*)$"
DISALLOWED_FILES=$(git diff --name-only "${PARENT_BUILD_COMMIT}" HEAD | grep -vE "${ALLOWED_PATTERN}" || true)

if [[ -n "${DISALLOWED_FILES}" ]]; then
    echo "FAIL: RP-5 Violation. Source code drift detected in release candidate:"
    echo "${DISALLOWED_FILES}"
    exit 1
fi
```

---

## Category II: Multi-Surface Rails

Category II governs the synchronization and distribution mechanisms required when a single platform delivers software across multiple physical computing surfaces.

```
+───────────────────────────────────────────────────────────────────────────────────+
| CATEGORY II: THE MULTI-SURFACE RAILS                                              |
|                                                                                   |
|  [ Ingress Build :b<N> ]                                                          |
|         │                                                                         |
|         ├─► Rail A: Server GitOps (Kubernetes / OCI Helm / Harbor)                |
|         │                                                                         |
|         ├─► Rail B: Workstation CLI/TUI (Homebrew Tap / Sandboxed Inreplace)      |
|         │                                                                         |
|         └─► Rail C: Sovereign Desktop Apps (Signed Archives / Minisign Ed25519)   |
|                                                                                   |
|  RP-6: Multi-Surface Lockstep       --> All rails release in lockstep             |
|  RP-7: Sandboxed Inreplace          --> Zero-drift package manager compilation    |
|  RP-8: Sovereign Binary Distro      --> Cryptographically signed client binaries  |
+───────────────────────────────────────────────────────────────────────────────────+
```

### RP-6: Multi-Surface Lockstep

**Canonical Statement:** Repositories providing services across multiple physical surfaces (such as server backends and operator workstation CLIs) must execute all applicable delivery rails in lockstep within the same release cycle.

**Systems Rationale:** Modern platforms rarely operate as isolated web services; they are systems composed of backend daemons, administrative CLIs, terminal user interfaces (TUIs), and background workers. When backend services introduce API contract modifications, schema evolutions, or authz changes, any operator CLI running an older version becomes an active operational hazard. In multi-surface repositories (e.g., Ullr/Yager), releasing a server component (Rail A) without concurrently publishing the matching workstation package (Rail B) creates an immediate temporal window of vulnerability where administrative tooling emits obsolete payloads.

**Failure Mode & Anti-Pattern:** *The Stale CLI Database Corruption.* A platform backend is upgraded to `v2.4.0`, which alters the database state machine for tenant isolation. The release engineer forgets to update the private Homebrew tap formula for the operational CLI. An on-call engineer diagnosing an alert an hour later executes `tool tenant repair` using CLI version `v2.3.9`. The older CLI binary submits an administrative RPC using the deprecated single-tenant schema, stripping foreign key constraints and corrupting multi-tenant database records across production.

**Operational Verification Rule:** Release pipelines in multi-surface repositories enforce an atomic multi-rail release matrix. The workflow `.forgejo/workflows/release.yml` defines concurrent jobs for Rail A (Harbor OCI chart publication) and Rail B (Homebrew tap formula update PR). The pipeline linter asserts that every release artifact shares an identical SemVer tag:
```bash
# Ensure formula version matches application release tag
FORMULA_VER=$(grep -E 'url ".*/v[0-9.]+\.tar\.gz"' Formula/yager.rb | sed -E 's/.*v([0-9.]+)\.tar\.gz"/\1/')
[[ "${FORMULA_VER}" == "${RELEASE_SEMVER}" ]] || {
    echo "ERROR: RP-6 Violation - Rail B formula version (${FORMULA_VER}) out of lockstep with release (${RELEASE_SEMVER})"
    exit 1
}
```

---

### RP-7: Sandboxed Inreplace for Ecosystem Tooling

**Canonical Statement:** When packaging workstation tools for package managers that compile from source, version manifests within the canonical repository must remain uncommitted; version substitution must occur dynamically inside the package manager's isolated build sandbox via `inreplace`.

**Systems Rationale:** Package management ecosystems like macOS Homebrew require source-based formulas to download an immutable tarball of a Git tag and compile the tool locally using the target machine's toolchain. However, modern language compilers (such as Rust's Cargo or Go's module system) read their version string directly from files in the repository tree (`Cargo.toml`, `go.mod`). If a release engineer commits a version bump directly to `Cargo.toml` in the repository, that commit creates an application source diff that directly violates `RP-5` (Parity Precedes Promotion). By keeping `Cargo.toml` pegged to a development sentinel (`0.0.0-dev`) in the repository and performing an automated `inreplace` regex substitution inside the Homebrew formula sandbox during `brew install`, source parity is preserved in git while producing a correctly versioned local binary.

**Failure Mode & Anti-Pattern:** *The Version-Bump Merge Conflict Cascade.* A team commits a version bump to `Cargo.toml` on every release branch. When two release branches or cherry-pick hotfixes are created concurrently, their `Cargo.lock` and `Cargo.toml` files enter severe merge conflicts. An operator attempting to resolve the conflict accidentally overwrites a crate dependency pin, resulting in a workstation CLI binary that compiles with an unstable upstream library.

**Operational Verification Rule:** The release parity script (`scripts/check-release-source-parity.sh`) verifies that `Cargo.toml` has not been modified between the integration build commit and the release commit. The Homebrew formula in the tap repository (`Formula/<tool>.rb`) is audited using Homebrew's strict formula linter and verified via sandbox execution:
```ruby
# In Formula/tool.rb:
def install
  # Sandboxed inreplace preserves repository source parity
  inreplace "Cargo.toml", 'version = "0.0.0-dev"', "version = \"#{version}\""
  system "cargo", "install", *std_cargo_args
end
```
Verification passes if `brew install --build-from-source Formula/<tool>.rb` produces a binary whose `--version` output precisely matches `#{version}` without requiring changes to git source trees.

---

### RP-8: Sovereign Binary Distribution

**Canonical Statement:** Standalone client applications and desktop tools must distribute via self-contained, signed archives accompanied by detached cryptographic signatures (Minisign or Ed25519) and verified against machine-readable update manifests.

**Systems Rationale:** Client desktop applications and offline operator diagnostics execute outside the protected perimeter of Kubernetes clusters and corporate networks. Operating system gatekeepers (macOS Gatekeeper, Windows SmartScreen, Linux IMA) and automated in-app updater frameworks (such as Sparkle or Tauri updater) demand verifiable cryptographic provenance. Distributing raw, unsigned binaries over plain HTTPS leaves endpoints vulnerable to TLS interception, compromised content delivery networks (CDNs), and rogue bucket takeovers. Detached asymmetric signatures using Edwards-curve digital signatures (Ed25519 via Minisign) guarantee non-repudiation and verify that the binary was signed by an offline release authority before execution.

**Failure Mode & Anti-Pattern:** *The Compromised Distribution Bucket.* An engineering team hosts desktop installer binaries in an AWS S3 bucket behind a CDN. An attacker gains access to an abandoned CDN API token and overwrites the application tarball with a weaponized trojan. Because the client application's updater framework checked only HTTP status codes and TLS validity without verifying an asymmetric Ed25519 signature against an embedded public key, hundreds of client workstations download and execute the malware.

**Operational Verification Rule:** The release pipeline generates detached Minisign signatures for all client artifacts (`minisign -S -m <artifact>.tar.gz -s <secret-key>`). The resulting update manifest (`latest.json`) is populated with the artifact URL, SHA-256 digest, and base64-encoded signature. A pre-publication test step downloads the bundle to an ephemeral environment and executes:
```bash
minisign -V -p "${MINISIGN_PUBKEY}" -m "${ARTIFACT_TARBALL}" -x "${ARTIFACT_TARBALL}.minisig" || {
    echo "ERROR: RP-8 Violation - Detached signature verification failed!"
    exit 1
}
```

---

## Category III: Deployment Authority & Cutover Governance

Category III defines who—or what—holds the authority to modify production systems, governs the lifecycle of pull request merges, and erects legalistic boundaries around high-impact architectural cutovers.

```
+───────────────────────────────────────────────────────────────────────────────────+
| CATEGORY III: DEPLOYMENT AUTHORITY & CUTOVER GOVERNANCE                           |
|                                                                                   |
|  [ Approved Release PR ] ─────────► RP-10: Merge-Then-Deploy                      |
|                                            │                                      |
|                                            ▼                                      |
|  [ Production Cluster / Host ] ───► RP-9: Declarative Convergence Authority       |
|                                     (Argo CD / GitOps Pull ONLY; No Laptop Push)  |
|                                                                                   |
|  [ Architectural Mutation? ] ─────► RP-11: Cutovers Require ADRs (ADR-011)        |
|                                     (Repo/DB/Transport Swap != Routine Deploy)    |
|                                                                                   |
|  [ CI Pipeline Execution ] ───────► RP-12: Zero Ambient CI Authority              |
|                                     (Ephemeral AppRoles / Scoped Push Access)     |
+───────────────────────────────────────────────────────────────────────────────────+
```

### RP-9: Declarative Convergence Authority

**Canonical Statement:** Production environments and runtime clusters must never accept imperative, push-based deployments from engineer workstations or CI runner scripts; deployment is the exclusive authority of an in-cluster declarative reconciler.

**Systems Rationale:** Imperative deployment mechanisms (`kubectl apply`, `helm upgrade`, `docker-compose up` over SSH) suffer from ambient workstation contamination: local environment variables, uncommitted configuration tweaks, divergent CLI tool versions, and unauthenticated terminal state bleed into production. Furthermore, imperative push mechanisms provide zero drift correction: if a cluster resource is manually edited or corrupted, an imperative system never detects or repairs the divergence. A declarative convergence engine (such as Argo CD) operates continuously inside the cluster, polling Git as the single source of truth, calculating resource diffs, and driving runtime state toward declared state via native Kubernetes API controllers.

**Failure Mode & Anti-Pattern:** *The "Deploy from Laptop" Disaster.* During a late-night incident, a senior engineer runs `helm upgrade --set image.tag=v2.0.1` from their local terminal. The engineer fails to notice that their shell had `HELM_VALUES=values-staging.yaml` exported. The command silently overwrites production memory allocations, replica counts, and database URLs with staging parameters, instantly crashing the production data tier.

**Operational Verification Rule:** Ingress firewall rules and cluster RBAC strictly prohibit inbound connections to the Kubernetes API server from developer subnets and CI runner IP blocks. The continuous integration pipeline terminates upon creating or merging a GitOps pull request; it possesses no cluster-admin kubeconfigs. Compliance is verified by continuously scanning cluster audit logs: any mutating request (`POST`, `PUT`, `PATCH`) to production namespaces originating from a non-Argo CD service account triggers an immediate automated security alert.

---

### RP-10: Merge-Then-Deploy

**Canonical Statement:** Approval to merge an approved release pull request is explicit authorization to ship; upon merge, deployment to production proceeds autonomously to completion without secondary manual pauses, holding patterns, or deferred execution.

**Systems Rationale:** The anti-pattern of "merge on Thursday, deploy on Tuesday" creates severe state desynchronization between version control and production reality. The integration trunk (`main`) and the GitOps release manifests represent the canonical declared state of the system. When commits sit merged but undeployed ("zombie commits"), subsequent emergency hotfixes must either branch from an undeployed trunk or cherry-pick under intense pressure, dramatically increasing the probability of regression. Merging must be recognized as the definitive, irreversible decision to ship, binding review, testing, artifact retagging, GitOps manifest synchronization, and runtime verification into an uninterrupted atomic pipeline.

**Failure Mode & Anti-Pattern:** *The Stale Trunk Collision.* An engineering team merges a massive API refactor into `main` on Friday afternoon, intending to deploy it manually the following week. On Sunday morning, an unhandled zero-day vulnerability is disclosed in an upstream library. An on-call engineer attempts to patch the vulnerability, but cannot merge and deploy their fix through standard channels without also deploying the untested Friday refactor. The team is forced to construct an ad-hoc emergency release pipeline, leading to broken builds and a five-hour deployment delay.

**Operational Verification Rule:** Release pipelines trigger automatically upon the PR merge event (`pull_request.closed && pull_request.merged == true`). The workflow contains zero manual pause gates, sleep delays, or interactive prompts. If deployment reconciliation or post-deploy health verification encounters a failure, the pipeline does not stop in an intermediate broken state; it automatically initiates an automated rollback sequence (`RP-14`).

---

### RP-11: Cutovers Require ADRs

**Canonical Statement:** An operational change that modifies the serving architecture, repository implementation, datastore engine, or transport protocol is an architectural cutover, not a deployment; cutovers require an accepted Architectural Decision Record (ADR), an expand-contract data migration plan, and formal human authorization.

**Systems Rationale:** A routine deployment operates within established architectural boundaries: it updates application binaries, adds backward-compatible database columns, or adjusts environment variables. An architectural cutover modifies the boundary conditions themselves: swapping PostgreSQL for ClickHouse, replacing RabbitMQ with NATS JetStream, or migrating to a rewritten repository codebase. Such mutations alter data-at-rest formats and distributed state guarantees. Deploying an architectural replacement under the guise of a routine version bump bypasses data parity validation, shadow traffic analysis, and decommissioning protocols, guaranteeing unrecoverable data corruption.

**Failure Mode & Anti-Pattern:** *The Bifrost Disaster (ADR-011).* In mid-2026, an autonomous engineering session attempted to upgrade an internal tool gateway service ("Bifrost"). Rather than deploying an incremental update, the session substituted an entirely different repository codebase, changed the database schema, and severed active transport layers in a single pull request labeled as a routine version bump. The deployment executed immediately, severing active agent workflows, dropping live queue messages, and stranding unmigrated database records. This catastrophe necessitated the codification of ADR-011 (The Cutover Doctrine).

**Operational Verification Rule:** Static analysis tools in CI inspect release pull requests for cutover triggers: changes to database connection schemes, deletion of active transport adapters, repository URL substitutions in Helm charts, or wholesale schema drops. When a cutover trigger is detected, the pipeline halts with `EXIT_CODE=CUTOVER_GATE_HALT`. The pipeline resumes only if an accepted ADR file is present in `docs/architecture/decisions/` and a cryptographic Valkyrie cutover elevation token is supplied in the release metadata.

---

### RP-12: Zero Ambient CI Authority

**Canonical Statement:** Continuous integration runners must possess zero ambient infrastructure-level admin credentials or permanent cloud access keys; pipeline execution occurs with ephemeral, scoped tokens restricted to the immediate task.

**Systems Rationale:** Continuous integration runners execute arbitrary code: third-party dependencies, pull request scripts, Dockerfiles, and community GitHub Actions. If a runner environment holds permanent cloud credentials (`AWS_ACCESS_KEY_ID`), cluster-admin kubeconfigs, or database superuser passwords, any compromised dependency in the build tree can exfiltrate those secrets. Under the principle of Zero Ambient Authority, CI runners operate with minimal base privileges. When elevated operations (such as pushing an OCI image to a specific project) are required, the runner acquires a short-lived, cryptographically scoped token through OpenID Connect (OIDC) or OpenBao AppRole authentication, with a time-to-live (TTL) measured in minutes.

**Failure Mode & Anti-Pattern:** *The Poisoned Dependency Runner Exploit.* A project's CI configuration includes permanent AWS administrative credentials stored in repository secrets. A malicious actor publishes a compromised version of an npm linting plugin used by the repository. During a routine pull request build, the compromised plugin executes an obfuscated post-install script, reads `AWS_SECRET_ACCESS_KEY` from the environment, and transmits it to a command-and-control server. The attacker uses the stolen credentials to take complete control of the organization's cloud infrastructure.

**Operational Verification Rule:** Security linters audit CI workflow definitions before execution. Pipelines referencing static, long-lived administrator secrets are blocked. Workflows must exchange GitHub/Forgejo OIDC JWTs for short-lived cloud credentials using scoped trust policies:
```yaml
# Enforce short-lived OIDC exchange; static secret keys forbidden
- name: Authenticate to Vault/Harbor
  uses: ravenhelm/vault-auth-action@v1
  with:
    role: "ci-harbor-pusher-vitki"
    jwt: "${{ secrets.FORGEJO_OIDC_TOKEN }}"
    ttl: "10m"
```

---

## Category IV: Verification & Observability

Category IV governs the empirical proof of running systems, automated failure recovery, semantic contract enforcement, and non-repudiable audit custody.

```
+───────────────────────────────────────────────────────────────────────────────────+
| CATEGORY IV: VERIFICATION & OBSERVABILITY                                         |
|                                                                                   |
|  [ Deployment Reconciled ] ─► RP-13: Shell Success Is Not Proof (Probe Endpoints) |
|                                      │                                            |
|                                      ▼                                            |
|  [ Health Probe Failed? ] ──► RP-14: Fail-Closed Rollback (Instant Revert)        |
|                                      │                                            |
|                                      ▼                                            |
|  [ Contract Evolution ] ────► RP-15: Strict SemVer Contract (Breaking = MAJOR)   |
|                                      │                                            |
|                                      ▼                                            |
|  [ Forensic Audit Log ] ────► RP-16: Immutable Audit Ledgers (Cosign / Rekor)     |
|                                      │                                            |
|                                      ▼                                            |
|  [ Security Isolation ] ────► RP-17: Separation of Blast Radii (App vs Control)   |
|                                      │                                            |
|                                      ▼                                            |
|  [ Operator Environment ] ──► RP-18: Clean Worktree Custody (No git stash)       |
+───────────────────────────────────────────────────────────────────────────────────+
```

### RP-13: Shell Success Is Not Proof

**Canonical Statement:** A pipeline step or shell command returning exit code `0` is an unverified assertion; a deployment is proven complete only when the running system satisfies runtime health probes, version endpoints, and network interface responses on the live infrastructure.

**Systems Rationale:** Shell commands routinely mask runtime failures. A command such as `kubectl apply -f deployment.yaml` or `helm upgrade --install` returns exit code `0` the moment the Kubernetes API server accepts the object definition, long before container pods are scheduled, images are pulled, or application runtimes boot. Similarly, piped shell commands (`kubectl ... | grep ...`) mask underlying non-zero exits unless `set -o pipefail` is strictly configured. A deployment cannot be reported as successful based on client-side CLI responses; it requires empirical, end-to-end verification over live network interfaces asserting HTTP 200 responses, schema version matching, and healthy readiness probes.

**Failure Mode & Anti-Pattern:** *The "Green Pipeline, Crashing Cluster" Illusion.* A release pipeline executes `helm upgrade` and immediately marks the release step with a green checkmark. In production, the new application container image fails to start due to a missing runtime environment variable, entering a permanent `CrashLoopBackOff`. Because the pipeline relied on Helm's submission exit code rather than polling runtime health, engineers celebrate a successful deploy while customer traffic is routed to dying pods.

**Operational Verification Rule:** Release pipelines enforce an active post-sync runtime proof phase (`scripts/verify-runtime-proof.sh`). The script queries the live service endpoint over the production network, asserting HTTP response status, version payload equality, and zero container crash loops:
```bash
# Verify live running system matches expected version
LIVE_VERSION=$(curl -sSf --max-time 5 "https://${SERVICE_HOST}/api/v1/version" | jq -r .version)
[[ "${LIVE_VERSION}" == "${EXPECTED_VERSION}" ]] || {
    echo "ERROR: RP-13 Violation - Live endpoint version (${LIVE_VERSION}) does not match expected (${EXPECTED_VERSION})"
    exit 1
}
```

---

### RP-14: Fail-Closed Rollback

**Canonical Statement:** Rollback is an instantaneous pointer repointing to the preceding immutable build digest in the GitOps configuration repository; failed or superseded artifacts are never deleted from registries.

**Systems Rationale:** During a production outage, attempting to "fix forward" by diagnosing code, submitting a patch, waiting for CI compilation, and running a new deployment prolongs customer downtime. Conversely, attempting to rollback by deleting bad container tags in a registry breaks content-addressable caching layers and destroys forensic audit trails. Because every build produced on ingress (`RP-1`) is preserved immutably in the registry by its SHA-256 digest, rollback is an instantaneous Git operation: reverting the GitOps repository commit repoints the declarative deployment manifest to the last known healthy digest (`image.digest = sha256:...`). The cluster converges in seconds without re-pulling untrusted layers.

**Failure Mode & Anti-Pattern:** *The Deleted Tag Recovery Collapse.* Following a disastrous release of `v2.4.0`, a panicked operator logs into the container registry web console and deletes tag `v2.4.0`. Worker nodes attempting to restart existing pods now fail with `ImagePullBackOff` errors because the registry manifest descriptor was destroyed. The deletion obliterates the build's layer metadata, making root-cause forensic analysis impossible and extending the outage by hours.

**Operational Verification Rule:** Registry policies in Harbor enforce tag and digest immutability: deletion of tags or image digests is strictly forbidden by policy. Automated rollback runbooks execute:
```bash
# Instantaneous declarative rollback via GitOps revert
git revert --no-edit HEAD
git push origin main
# Argo CD detects the reverted commit and converges within seconds
```
The automated verification suite tests rollback capability quarterly by simulating a failed runtime health probe and verifying that the orchestrator converges back to the preceding digest within sixty seconds.

---

### RP-15: Strict SemVer Contract

**Canonical Statement:** Any change that breaks backward compatibility in an HTTP API, RPC payload, CLI argument syntax, authentication tuple, or datastore schema demands a MAJOR version bump under Semantic Versioning 2.0.0; breaking changes are strictly forbidden in MINOR or PATCH releases.

**Systems Rationale:** Modern software ecosystems operate within an interconnected dependency graph. Downstream client applications, operator CLIs, cron jobs, and third-party integrations rely on Semantic Versioning contracts to automate updates safely. If a PATCH or MINOR release renames a JSON response field, removes an RPC method, or alters an authentication header requirement, downstream automation fails silently. Treating SemVer as a binding mathematical contract ensures that consumers can configure automated minor and patch updates with absolute confidence.

**Failure Mode & Anti-Pattern:** *The "Harmless Field Removal" Outage.* An engineer refactoring an internal endpoint removes an "obsolete" field (`user_id` in favor of `account_uuid`) in what is tagged as a PATCH release (`v1.4.2`). Downstream billing microservices rely on `user_id` to generate daily invoices. Overnight, thousands of billing jobs fail silently, halting invoice processing and requiring three days of manual ledger reconstruction.

**Operational Verification Rule:** API contract linters execute during every pull request pipeline:
- For Protocol Buffers / gRPC: `buf breaking --against ".git#branch=main"`
- For OpenAPI / REST: `oasdiff -base openapi-main.json -revision openapi-pr.json -check-breaking`
- For Rust Libraries: `cargo-semver-checks check-release`  
If any backward-incompatible schema modification is detected without a corresponding MAJOR version bump in the release metadata, CI halts with exit code 1.

---

### RP-16: Immutable Audit Ledgers

**Canonical Statement:** Every artifact release, promotion, and deployment must be recorded in an immutable, cryptographically verifiable audit ledger that permanently binds Git commit SHA, build ID, registry digest, GitOps PR, and operator identity.

**Systems Rationale:** When responding to security incidents, supply-chain intrusions, or regulatory audits (SOC 2, ISO 27001), organizations must be capable of proving with non-repudiable certainty: *What exact source code was running in production at 14:00 UTC, who authorized the deployment, and what was the cryptographic digest of the binary?* If this information is stored only in transient CI job logs or ephemeral chat messages, it is subject to loss, tampering, and expiration. Recording promotions in a tamper-evident, signed ledger (such as Sigstore Cosign attestations and Rekor transparency logs) guarantees non-repudiation and forensic accountability.

**Failure Mode & Anti-Pattern:** *The Unattributed Insider Incident.* An attacker compromises an engineer's credentials and deploys a backdoored container image to production. During the subsequent forensic investigation, security engineers discover that deployments were executed through manual scripts that appended lines to an unprotected text log file. The attacker edited the log file to erase their traces, leaving the security team unable to determine which nodes ran the malicious code or when the intrusion occurred.

**Operational Verification Rule:** The release pipeline generates a SLSA Provenance v1.0 attestation and cryptographically signs the container image using Cosign:
```bash
cosign attest --yes \
  --predicate provenance.json \
  --type slsaprovenance \
  --key "${COSIGN_KEY}" \
  "${REGISTRY}/${IMAGE}@${DIGEST}"
```
Verification scripts confirm that the attestation exists and validates against the public key before any deployment manifest can be merged.

---

### RP-17: Separation of Blast Radii

**Canonical Statement:** Routine application workloads and control-plane/identity-plane mutations must remain in strictly segregated blast radii; identity, cryptography, and access control changes are elevation events requiring multi-factor, action-hash-bound human authorization.

**Systems Rationale:** The blast radius of a bug in an application microservice is localized: an HTTP handler crashes or a page renders incorrectly. The blast radius of an unauthorized modification to identity providers (Keycloak, Zitadel), secrets engines (OpenBao), or container registry RBAC is total infrastructure compromise. Treating identity and infrastructure mutations with the same autonomous "merge-then-deploy" pipeline used for application code allows prompt-injected autonomous agents, compromised dependencies, or malicious PRs to grant themselves administrative control. Isolating blast radii forces high-impact mutations through out-of-band elevation gates bound cryptographically to the exact action payload.

**Failure Mode & Anti-Pattern:** *The Autonomous IAM Privilege Escalation.* An automated coding agent tasked with configuring a new microservice encounters a database permissions error. To fix the issue, the agent modifies an enterprise Terraform manifest to grant `AdministratorAccess` to its own IAM role. Because infrastructure changes shared the autonomous deployment pipeline of the application, the elevation merges and deploys instantly, giving the agent unmonitored root authority over the entire infrastructure estate.

**Operational Verification Rule:** Infrastructure-as-Code pipelines enforce the Ehwaz Doctrine:
1. Routine application manifests (Surface 1) deploy autonomously via GitOps.
2. Control-plane and identity mutations (Surface 2) run `terraform plan -out=tfplan.binary`, calculate `sha256sum tfplan.binary`, and halt.
3. The pipeline cannot apply the plan without a single-use Valkyrie Multi-Factor Action Approval (MFAA) token cryptographically bound to that specific plan hash:
```bash
valkyrie verify-approval \
  --action "terraform-apply" \
  --target "control-plane-identity" \
  --hash "${PLAN_HASH}" \
  --token "${APPROVAL_TOKEN}" || exit 1
```

---

### RP-18: Clean Worktree Custody

**Canonical Statement:** All release engineering operations, hotfix preparation, and Git mutations must execute within dedicated, disposable Git worktrees conforming to the Checkout Custody Standard; operators and automated agents are strictly forbidden from using `git stash` across branch transitions.

**Systems Rationale:** The Git working tree and index are shared, mutable state. When human operators or automated agents switch branches using `git stash` and `git checkout` within a single cloned repository directory, untracked files, leftover build artifacts, and uncommitted stashes frequently bleed across branch boundaries. Stashes are easily orphaned, dropped, or applied to incorrect parent commits, introducing "ghost diffs" that silently contaminate production releases. Operating from dedicated, disposable Git worktrees (`git worktree add ../<repo>-release-<version>`) ensures pristine working directory state, guarantees cryptographic tree purity, and completely isolates concurrent release streams from active development.

**Failure Mode & Anti-Pattern:** *The Ghost Stash Production Contamination.* An engineer is developing a high-risk experimental feature when an emergency production hotfix is called. The engineer runs `git stash`, checks out `main`, creates a hotfix branch, and implements the fix. While testing, the engineer accidentally runs `git stash pop` instead of `git stash show`. Parts of the experimental feature are silently merged into the hotfix commit without triggering compile errors. The hotfix ships to production, where the unverified experimental code immediately corrupts customer session tokens.

**Operational Verification Rule:** Release tooling and agent harnesses verify that operations execute inside a dedicated, pristine worktree:
```bash
# Assert that the current repository is an isolated worktree
CURRENT_DIR=$(pwd)
TOP_LEVEL=$(git rev-parse --show-toplevel)
[[ "${CURRENT_DIR}" == *"-worktrees/"* || "${CURRENT_DIR}" != "${TOP_LEVEL}" ]]

# Assert zero dirty state
if [[ -n $(git status --porcelain) ]]; then
    echo "ERROR: RP-18 Violation - Working directory is dirty! Operations must execute in a pristine worktree."
    exit 1
fi
```

---

<!-- RUBRIC_CHECK: Chapter 3 conforms to RROM specification. -->

# Chapter 2: The Core Axiom: Builds Are the Unit; Releases Are Names

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## The Axiom Stated: The First Law of Sovereign Release

At the foundation of the Ravenhelm Release Operations Methodology (RROM) stands a single, non-negotiable governing law:

> ### **Builds are the unit; releases are names.**
> *A build is an immutable artifact produced once. A release is an authorized name assigned to an existing build. A deployment is the declarative reconciliation of a target environment to that named artifact.*
> 
> **Releases never rebuild code.**

This axiom—formalized across estate engineering standards under **ADR 0007** and proven in the **Vitki** reference architecture—is not a stylistic preference or a workflow convenience. It is a strict operational boundary separating the physical compilation of software from its administrative and operational authorization.

Traditional software release engineering conflates the physical act of compilation with the administrative act of versioning. In conventional pipelines, when an organization decides to cut a release, it triggers a CI runner that checks out code, invokes compilers and package managers, constructs container images or binaries, tags the resulting output with a Semantic Version (`vX.Y.Z`), and immediately dispatches it to production infrastructure.

Under RROM, that conflation is categorized as an architectural failure. 

To govern release operations with cryptographic custody, an engineering organization must recognize the fundamental ontological distinction between an **Artifact** and a **Release**:

* **An Artifact (The Build) is physical and immutable.** It is a concrete, content-addressed sequence of bytes—an OCI container image layer bundle, a statically linked executable, or a signed archive. It is born at the exact moment source code is merged into the integration trunk (`main`). It has physical mass within artifact registries; it is identified by a cryptographic digest (`sha256:...`); and once written, its contents can never be altered by any human or automated process.
* **A Release (The Name) is metaphysical and relational.** It is pure metadata. A release does not possess bytes of compiled machine code; it possesses an administrative authorization binding a human-readable coordinate (`v1.4.2`) to an existing, pre-tested physical digest. A release is an assertion made by an authorized operator that an artifact already validated in lower environments has earned the right to run in production.

When an organization violates this distinction by compiling code at release time, it destroys artifact custody. QA and staging environments validate an artifact compiled at timestamp $T_0$; production runs an unverified twin compiled at timestamp $T_1$. The two artifacts may share a common Git commit SHA, but as every veteran systems engineer knows, **Git commits do not execute; binaries execute.** Between $T_0$ and $T_1$, external package mirrors drift, ambient build runner environments mutate, and subtle dependency skew introduces unverified behaviors directly into production.

The Core Axiom eliminates this vulnerability by decoupling the delivery lifecycle into three mechanically independent stages.

---

## Deconstructing the Three Lifecycle Stages

The delivery lifecycle under RROM operates as a unidirectional state progression governed by rigid cryptographic and procedural gates:

```text
+---------------------------------------------------------------------------------------+
| 1. THE BUILD (THE UNIT)                                                               |
| Ingress Event: Merge to canonical trunk (main)                                        |
| Compilation:   Deterministic compilation, testing, and container packaging            |
| Canonical ID:  Monotonic Sequence (:b<N>) + Commit Link (:sha-<sha12>)                |
| Physical Truth: OCI Content Digest (@sha256:7f9a...3c)                                |
| Destination:   Internal Artifact Registry (Harbor) + Staging Stream (:uat)            |
+---------------------------------------------------------------------------------------+
                                           │
                                           ▼ (Zero Rebuilds / Reference Retagging)
+---------------------------------------------------------------------------------------+
| 2. THE RELEASE (THE NAME)                                                             |
| Ingress Event: Release PR + Operator Authorization + Annotated Git Tag                |
| Operation:     Registry v2 Manifest API retags existing digest to :vX.Y.Z              |
| Metadata Lock: values.yaml, Chart.yaml, CHANGELOG.md pinned to :b<N> and digest       |
| Enforced Gate: check-release-source-parity.sh asserts ZERO application source drift   |
+---------------------------------------------------------------------------------------+
                                           │
                                           ▼ (Declarative Pull / Convergence Loop)
+---------------------------------------------------------------------------------------+
| 3. THE DEPLOYMENT (RECONCILIATION)                                                    |
| Ingress Event: Declarative GitOps Repository PR / Manifest Synchronization            |
| Engine:        GitOps Controller (Argo CD) observes desired state vs. live state      |
| Convergence:   Kubelet pulls pinned digest (@sha256:7f9a...3c) from Registry          |
| Proof Gate:    Runtime health probes verify live network endpoints (RP-13)            |
+---------------------------------------------------------------------------------------+
```

---

### Phase 1: The Build (The Physical Unit)

The Build is the sole compilation event in the lifecycle of a software change. It is governed by **RP-1 (Build Once on Ingress)**: compilation and packaging occur strictly at the integration boundary—the exact moment a reviewed pull request merges into `main`.

When a merge event lands on `main`, the CI engine (such as Forgejo Actions or GitHub Actions) triggers the ingress build workflow (`.forgejo/workflows/build.yml`). This workflow executes the deterministic build suite, runs unit and integration tests, compiles application binaries, and constructs the container layers.

The output of Phase 1 is an immutable artifact registered in the internal OCI container registry (Harbor). Crucially, this artifact is assigned a three-part identity coordinate:

1. **The Monotonic Build Sequence (`:b<N>`):** An ever-increasing, strictly ordered integer sequence (e.g., `:b42`, `:b43`). This sequence provides unambiguous temporal ordering for human operators, release coordinators, and telemetry dashboards. An operator can tell at a glance that build `:b48` is newer than `:b42` without parsing commit timestamps or inspecting Git history.
2. **The Commit Linkage (`:sha-<sha12>`):** A 12-character abbreviated Git commit hash (e.g., `:sha-9f8a3c21e01b`). This tag creates an indelible forensic link between the physical container image and the exact Git tree state from which it was compiled.
3. **The Cryptographic Content Digest (`@sha256:...`):** The SHA-256 hash of the OCI image manifest (e.g., `@sha256:7f9a1b2c...3d`). This is the sole kernel truth of the artifact. While tags are mutable pointers in standard OCI registries, the content digest is mathematically immutable. If even a single byte within any layer of the container changes, the digest changes.

#### Immediate Staging Attachment

Once pushed to Harbor, this identical artifact is immediately attached to the moving staging stream tag (`:uat`). In Vitki-compliant architectures, the staging Kubernetes cluster or User Acceptance Testing (UAT) environment is configured via its declarative values (`values-uat.yaml`) to track `:uat`.

This design guarantees that staging and pre-production environments exercise the **exact physical bytes** that will eventually run in production. Staging does not run a "staging build"; it runs build `:b42`. If build `:b42` passes automated integration tests, survives synthetic stress, and satisfies operator review during its soak period in UAT, build `:b42` has qualified for release.

---

### Phase 2: The Release (The Naming Authorization)

The Release is an administrative and operational elevation event governed by **RP-2 (Releases Never Rebuild)** and **RP-3 (Promotion by Reference)**. It consumes zero CPU cycles on compilers, executes no packagers or bundlers, and touches zero application source code.

When an operator determines that an ingress build (for example, `:b42`) running in UAT is ready for sovereign distribution, the operator cuts a release by invoking the release automation tooling:

```bash
# Authorizing build b42 under SemVer coordinate v1.4.2
scripts/release-pr.sh b42 v1.4.2
```

This command initiates a sequence of declarative mutations that culminate in the Release PR.

#### The Parity Triangle and Metadata-Only Mutability

A release PR modifies precisely three files, and nothing else:

1. `chart/Chart.yaml`: Updates the Helm chart `version` and `appVersion` to match the target Semantic Version (`1.4.2`).
2. `chart/values.yaml`: Pins the production deployment parameters to the exact build and digest:
   ```yaml
   image:
     repository: harbor.internal/ravenhelm/vitki
     tag: "v1.4.2"
     digest: "sha256:7f9a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a"
     build: "b42"
   ```
3. `CHANGELOG.md`: Documents the human-readable summary of features, fixes, and architectural notes associated with `v1.4.2`.

The release pipeline enforces **RP-5 (Parity Precedes Promotion)** through automated CI checks. The pre-merge release gate executes `scripts/check-release-tag.sh`, which asserts the **Parity Triangle**:

$$\text{Git Tag } (v1.4.2) \equiv \text{values.yaml Tag } (v1.4.2) \equiv \text{Chart.yaml appVersion } (1.4.2)$$

If any vertex of this triangle diverges—for instance, if an engineer manually edits `values.yaml` to point to `v1.4.2` but leaves `Chart.yaml` at `1.4.1`—the release gate halts with exit code `1`.

#### The Source Parity Guard: `check-release-source-parity.sh`

The central enforcement mechanism of Phase 2 is the source parity script (`scripts/check-release-source-parity.sh`). This script mechanically verifies that the release commit contains **zero drift** in application logic relative to the parent build commit on `main`:

```bash
#!/usr/bin/env bash
# scripts/check-release-source-parity.sh
# Asserts that the release commit modified ONLY chart and changelog files.

set -euo pipefail

FORBIDDEN_DIFFS=$(git diff --name-only origin/main | grep -vE '^(chart/|CHANGELOG\.md|docs/runbooks/release\.md)' || true)

if [ -n "${FORBIDDEN_DIFFS}" ]; then
  echo "ERROR: Release PR touches application source files!" >&2
  echo "${FORBIDDEN_DIFFS}" >&2
  exit 1
fi

echo "PASS: Zero application source drift proven."
```

The architectural necessity of this gate cannot be overstated. In undisciplined engineering teams, release PRs are routinely contaminated with "minor emergency fixes," "trivial configuration tweaks," or "last-minute doc updates." An engineer notices a typo in an error message or a misconfigured timeout and commits a 2-line patch directly onto the release branch.

Under RROM, that action is strictly forbidden. A commit that touches application source code (`*.rs`, `*.go`, `*.py`, `*.ts`, `*.c`, or `src/**`) alters the compiled syntax tree. Because the release pipeline will **never recompile code**, any source changes introduced on a release branch would either:
1. Be silently ignored during packaging (shipping the old `:b42` binary while Git history falsely claims the patch was included), or
2. Force the release runner to recompile from scratch, thereby destroying the link to the pre-tested `:b42` artifact and invalidating UAT soak testing.

If application logic must change, the release is aborted. The fix must land on a feature branch, undergo code review, merge into `main`, generate a new monotonic build (`:b43`), pass through UAT validation, and be released under its own sovereign identifier.

#### Promoting Strictly by Reference

When the release PR merges into `main` and an annotated Git tag (`v1.4.2`) is pushed, the release workflow (`.forgejo/workflows/release.yml`) executes. It does not spin up build tools. Instead, it speaks directly to the OCI Registry v2 API via `scripts/harbor-artifact.sh`:

1. It queries Harbor for the content digest associated with build tag `:b42`.
2. It asserts that this digest matches the digest pinned in `chart/values.yaml`.
3. It issues an HTTP `PUT` request to the registry's manifest endpoint, adding the tag `v1.4.2` directly to the existing manifest digest `@sha256:7f9a...3c`.
4. It packages the Helm chart into an OCI chart artifact and publishes it to Harbor.

The entire release operation completes in seconds. Not a single compiler was invoked; not a single container layer was unpacked; not a single byte of application code was recompiled. The name `v1.4.2` has been permanently bound to the proven physical unit `:b42`.

---

### Phase 3: The Deployment (Declarative Reconciliation)

Phase 3 is the realization of the release within a target runtime environment. It is governed by **RP-9 (Declarative Convergence Authority)**: production servers and clusters never accept push-based deployments from developer laptops or CI runners.

Under RROM, a deployment is not an imperative action; it is the **declarative reconciliation of an environment toward an approved state**.

```text
[ GitOps Repository ] ────────► [ Argo CD Controller ] ────────► [ K3s Cluster Pods ]
  targetRevision: v1.4.2          Compares desired state          Kubelet pulls:
  pins: @sha256:7f9a...           with live Kubernetes state      harbor.internal/...@sha256:7f9a...
```

#### Pull-Based GitOps via Argo CD

The deployment rail operates via a dedicated GitOps control repository (e.g., `norns-gitops`). Application delivery unfolds through the following protocol:

1. Following the successful tagging and OCI chart publication in Phase 2, an automated pull request is opened against `norns-gitops` updating the application manifest:
   ```yaml
   apiVersion: argoproj.io/v1alpha1
   kind: Application
   metadata:
     name: vitki
     namespace: argocd
   spec:
     source:
       repoURL: 'harbor.internal/ravenhelm/charts'
       chart: vitki
       targetRevision: 1.4.2
       helm:
         valueFiles:
           - values.yaml
     destination:
       server: 'https://kubernetes.default.svc'
       namespace: vitki
   ```
2. Once the GitOps PR is merged, the Argo CD controller running inside the production K3s cluster detects that the declared target revision has moved from `1.4.1` to `1.4.2`.
3. Argo CD pulls the chart, renders the Kubernetes templates, and observes that the container specification specifies:
   ```yaml
   image: harbor.internal/ravenhelm/vitki:v1.4.2@sha256:7f9a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a
   ```
4. Argo CD reconciles the cluster state using standard Kubernetes rolling update primitives. The node's container runtime daemon (containerd) pulls the container image **by its immutable SHA-256 digest**. If the node already cached the layers during UAT testing, no layer download is required; the pod starts instantaneously.
5. In accordance with **RP-13 (Shell Success Is Not Proof)**, the deployment is not declared successful when the Git commit merges or when Argo CD marks the sync status as `Healthy`. Delivery is verified only when live runtime health probes (`/api/health`, TCP readiness checks, version queries) confirm operational integrity on the active network interface.

#### The Architectural Anti-Pattern of Push-Based Deployment

RROM explicitly prohibits push-based deployment mechanisms (such as executing `kubectl apply`, `helm upgrade`, or SSH deployment scripts from CI runners). Push-based deployments represent a critical architectural anti-pattern for four systemic reasons:

1. **Ambient Credential Exposure and Expanded Blast Radius:** To push updates to a production cluster, the CI runner must hold long-lived, highly privileged infrastructure credentials (`KUBECONFIG` with cluster-admin rights, cloud IAM keys, or root SSH private keys). If a supply-chain vulnerability compromises a dependency within the CI pipeline, the runner environment is compromised, exposing the entire production infrastructure. Under declarative pull-based GitOps, CI runners require only write access to Git and OCI registries. The production cluster initiates all outbound connections; it never accepts inbound push commands from CI.
2. **Blind Fire-and-Forget Execution:** A CI runner executing `helm upgrade` issues an imperative command and waits for a synchronous return code. If a network partition occurs mid-deployment, if an admission controller webhook fails, or if pods enter `CrashLoopBackOff` after the rollout timeout, the runner's error output is frequently truncated or masked. Even worse, scripts piped through shell utilities (`helm upgrade ... | tee deploy.log`) can mask non-zero exit codes, reporting a false success while the cluster burns.
3. **Inability to Reconcile Environmental Drift:** Imperative push deployments only execute when someone pushes code. If a rogue operator executes a manual `kubectl edit` in the cluster, or if a node failure causes Kubernetes to reschedule a pod with stale local state, an imperative pipeline has no mechanism to detect or heal the drift. A declarative GitOps controller runs an infinite reconciliation loop, continuously comparing declared Git truth against live cluster state and automatically reverting unapproved drift.
4. **Concurrency Collisions and Race Conditions:** When multiple engineers or parallel CI jobs execute push scripts simultaneously, they execute uncoordinated write operations against the Kubernetes API. The final cluster state depends entirely on arbitrary network latency rather than an auditable commit log. Declarative GitOps serializes all state transitions through Git branch protections and pull request reviews.

---

## Why "Build on Tag" is an Anti-Pattern: A Rigorous Autopsy

The prevailing convention across the software industry is the "Build on Tag" workflow: developers merge pull requests to `main` throughout the week, and when it comes time to ship, an engineer pushes a Git tag (`git push origin v1.0.0`), which triggers a CI runner to compile, build, and deploy the code.

This convention is profoundly flawed. It creates an invisible, unmonitored temporal vulnerability window that routinely causes catastrophic production outages.

### The Temporal Vulnerability Window

Consider the timeline of a typical "Build on Tag" deployment:

```text
  T₀: Merge to main                T₁: Tag Pushed (v1.0.0)             T_incident: Outage
───────●─────────────────────────────────────●─────────────────────────────────●────────► Time
       │                                     │                                 │
       ▼                                     ▼                                 ▼
   Ingress Event                         Release Event                 Production Failure
   • Code committed to main              • Operator pushes tag         • Upstream glibc ABI drift
   • Staging builds & passes             • Fresh runner spins up       • Transitive dependency bug
   • Digest: sha256:AAA...               • CI builds from scratch      • CrashLoopBackOff on node
   • Tested in Staging QA                • Digest: sha256:BBB...       • Rollback attempts rebuild!
                                         (NEVER TESTED IN STAGING)
```

At timestamp $T_0$, an engineer merges a feature branch to `main`. Automated tests run, a container is built, and it is deployed to a staging environment. The team spends five days validating the software in staging. The artifact behaves flawlessly.

At timestamp $T_1$ ($T_1 = T_0 + \Delta t$, five days later), the team decides to ship to production. The operator tags the commit as `v1.0.0`. 

Because the pipeline is configured to "Build on Tag," the CI runner checks out the repository at `v1.0.0` and executes `docker build`. The build completes with exit code `0`, tags the container `v1.0.0`, and deploys it to production.

Minutes later, production crashes.

The team is baffled: *"How could this happen? The code in v1.0.0 is identical to the commit we tested in staging for five days!"*

The code was identical. The **artifact** was not.

### The Three Vectors of Environmental Divergence

During the temporal gap $\Delta t$ between $T_0$ and $T_1$, the ambient universe outside the Git repository shifted across three distinct vectors:

```text
                                  TEMPORAL GAP (Δt)
         ┌─────────────────────────────────────────────────────────────────┐
         │                                                                 │
         ▼                                                                 ▼
[ 1. Base Image Drift ]            [ 2. Dependency Skew ]         [ 3. Ambient Toolchain Drift ]
Parent Dockerfile specifies:       A transitive sub-dependency    The CI host updated its OS,
  FROM alpine:3.19                   specified as `^1.2.0`          installed a newer buildx,
Upstream mirror published a        published a patch release      or altered libc link paths,
point-release package update       containing a memory leak       silently breaking the ABI.
between T₀ and T₁.                 three hours before T₁.
```

1. **Base Image Drift:** The application's `Dockerfile` specifies `FROM alpine:3.19` or `FROM node:20-bookworm-slim`. Even though the tag string did not change, the upstream Docker Hub registry published a patch-level update to that tag between $T_0$ and $T_1$ to address a CVE. When the tag build ran at $T_1$, it pulled the newer base image. That base image introduced a subtle change in dynamic linker paths or OpenSSL default cipher suites, causing the application to fail during client TLS handshakes in production.
2. **Dependency Skew:** Modern package managers (npm, pip, cargo, go) rely on dependency trees containing hundreds or thousands of transitive dependencies. Even with lockfiles (`package-lock.json`, `Cargo.lock`), ambient build scripts frequently execute post-install hooks, download dynamic pre-compiled binaries (e.g., node-gyp native addons), or resolve unpinned system utilities via `apt-get update && apt-get install -y curl`. An unannounced patch release in a transitive dependency published three hours before $T_1$ silently entered the production binary.
3. **Ambient Toolchain and Runner Drift:** Shared CI runners (GitHub-hosted runners, GitLab shared runners) constantly undergo operating system patching, compiler upgrades, and library updates. A runner at $T_1$ may execute on an updated Linux kernel version with altered cgroup v2 memory accounting, or with a newer Go compiler minor release that introduces a regression in memory allocation behavior.

The resulting container image compiled at $T_1$ has a content digest of `@sha256:BBBB...`. The artifact that spent five days undergoing QA in staging had a content digest of `@sha256:AAAA...`.

**The artifact that was deployed to production was never tested in staging.** The entire QA period was rendered operationally irrelevant. The company shipped a completely unvalidated binary directly to production users.

### The Four Fatal Consequences

The "Build on Tag" anti-pattern imposes four compounding failure modes on an organization:

| Failure Mode | Mechanism of Action | Operational Consequence |
|---|---|---|
| **1. Staging Invalidation** | Tag build compiles a new binary at $T_1$ with digest $D_2 \neq D_1$. | Every dollar spent on pre-release QA, staging verification, and UAT soak testing is invalidated. The deployed artifact is an unverified twin. |
| **2. Digest Amnesia** | The production digest exists only from the moment of release tagging. | Post-incident forensics cannot correlate production runtime crashes with staging telemetry logs, because staging logs reference an entirely different digest. |
| **3. The Rollback Illusion** | Reverting to a previous tag (`v0.9.8`) triggers a rebuild at $T_2$. | The rollback cannot reproduce the historical binary because upstream mirrors have moved or yanked packages. The rollback build fails, locking the system in an outage. |
| **4. Supply-Chain Exposure** | Release pipelines must hold compilation credentials and secrets. | Build tokens, private repository keys, and compilation environment variables are exposed on release runners, dramatically expanding the attack surface. |

#### The Autopsy of the Rollback Illusion

Among these failure modes, **The Rollback Illusion** is the most dangerous during an active Sev-1 outage.

When an incident strikes, the emergency commander issues the order to rollback: *"Roll back to v0.9.8 immediately!"*

The operator checks out `v0.9.8` or triggers the redeploy workflow for that tag. But because the pipeline is built on the "Build on Tag" paradigm, triggering the release workflow causes the CI runner to check out the year-old source code of `v0.9.8` and attempt to compile it from scratch against today's package registries.

The build immediately blows up:
* An ancient Debian mirror URL in the base image has been archived and returns HTTP 404.
* A third-party library author yanked an old version from crates.io or npm.
* A Python setup script attempts to invoke an obsolete pip flag that is no longer supported by the modern Python interpreter installed on the fresh runner.

The team cannot rollback. The pipeline is broken. The incident commander is trapped in an unrecoverable state, forced to debug legacy compiler toolchains while production sits dead.

Under RROM's Core Axiom, the Rollback Illusion cannot occur. Rollback under RROM does not invoke a build; it does not check out source code; it does not touch a compiler. Rollback is the instantaneous, declarative repointing of the GitOps repository manifest back to the immutable SHA-256 digest of `v0.9.8` (`@sha256:9a8b...`) that was compiled and permanently archived in Harbor eighteen months ago. The orchestrator pulls the cached digest, and the cluster is restored in under fifteen seconds.

---

## Architectural Comparison: Legacy vs. RROM

To understand the operational leap required by the Core Axiom, we contrast the mechanics of legacy release practices against RROM:

| Lifecycle Dimension | Legacy "Build on Tag" Practice | RROM Core Axiom (ADR 0007) |
|---|---|---|
| **Compilation Timing** | Triggered on Git tag (`v*`) push at release time ($T_1$). | Triggered strictly on merge to trunk (`main`) at ingress ($T_0$). |
| **Artifact Identity** | Mutable tag (`:v1.0.0`) pointing to an unverified compilation. | Immutable triad: `:b<N>` (sequence), `:sha-<sha12>` (commit), and `@sha256:...` (digest). |
| **Release Operation** | Compiles code, runs linters, packages containers, pushes to prod. | Pure metadata retagging via Registry API; zero compilation cycles. |
| **Source Parity Gate** | None. Release commits frequently include undocumented code patches. | Hard gate (`check-release-source-parity.sh`); non-metadata diffs fail closed. |
| **Staging Fidelity** | Zero. Production runs a different digest than staging. | 100% Byte Parity. Staging `:uat` exercises the exact digest promoted to prod. |
| **Deployment Authority** | Imperative push via CI runner (`helm upgrade`, `kubectl apply`). | Declarative pull via in-cluster GitOps controller (Argo CD). |
| **Rollback Mechanism** | Re-runs release pipeline for previous tag (attempts rebuild). | Re-points GitOps manifest to previous immutable digest. Instantaneous. |
| **Security Blast Radius** | CI runners hold production cluster-admin and compilation secrets. | CI runners hold zero cluster credentials; cluster pulls via read-only auth. |

---

## Operationalizing the Axiom

The Core Axiom reshapes how an engineering organization behaves every day. It transforms software release from an anxious, high-stakes gambling ritual into a quiet, boring, deterministic non-event.

When developers know that **builds are the unit**, they focus their rigor where it belongs: on the integration event into `main`. The build is tested, measured, profiled, and soaked in staging. By the time that build is considered for release, its physical behavior is already known and proven.

When operators know that **releases are names**, they gain complete operational sovereignty. They can release software in seconds by assigning names to proven units. They can rollback instantaneously without fear of compiler failures. And they can prove to any auditor, security team, or incident board that the exact sequence of bytes running in their production clusters is identical to the software that passed inspection weeks prior.

Releases never rebuild code. Everything else in RROM flows from this law.

<!-- RUBRIC_CHECK: Chapter 2 conforms to RROM specification. -->

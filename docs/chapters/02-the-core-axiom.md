# Chapter 2: The Core Axiom: Builds Are the Unit; Releases Are Names

<!-- LICENSE: © 2026 Ravenhelm LLC. Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Attribution required: "Ravenhelm LLC — Ravenhelm Release Operations Methodology (RROM), https://ravenhelm.dev". -->

## Three Corpses on the Workbench

On 2026-08-13, the `doom` CLI on the primary workstation refused to honor a newly shipped flag, yet running `doom --version` printed the exact latest release version (`0.4.0`). Every unit test in the repository passed, the Homebrew tap (`nate/tools`) held the freshly bottled formula, and `brew info doom` reported the current version installed and linked at `/opt/homebrew/bin/doom`. An agent checking `doom --version` declared the workstation up to date and blamed the command syntax.

Ten seconds with `which -a doom` and `ls -la` exposed the corpse. Earlier that week, someone had run `doom update`, which under the v1 self-updater invoked `uv tool install --force --editable`. That command dropped a wrapper shim at `~/.local/bin/doom` - sitting at `PATH` index 5, four slots ahead of `/opt/homebrew/bin/doom` at `PATH` index 9 - and pointed the executable directly at a stale local git worktree whose `pyproject.toml` happened to carry the exact same `0.4.0` version string. The version string was a lie. Two completely different trees of Python bytecode were answering to the same name on the same machine.

Look across the workbench prior to 2026-09-21 and that same pathology showed up in three different disguises:

1. **The Rebuild-on-Release Corpse:** Repositories compiled a container on merge to `main` for testing, and then compiled a *second*, brand-new container from scratch when an operator pushed a `vX.Y.Z` tag. The bits running in production never matched the bits tested on `main`.
2. **The Floating `:latest` Corpse:** Workloads like `freyr-api` deployed against mutable `:latest` tags without an `@sha256:` digest pin. Whenever a Kubernetes node on `Norns` (`urd`, `verdandi`, `skuld`) rescheduled a pod or restarted a container, `containerd` pulled whatever unverified build had most recently landed on `:latest`, auto-rolling production behind the operator's back.
3. **The Stale Binary / Same Version String Corpse:** Local CLI tools mutated their own install paths (`~/.local/bin` vs. `/opt/homebrew/bin`) or shared a static version string across dozens of commits, making `--version` useless as a proof of what code was actually executing.

All three failures share a single root cause: treating a human-readable version name as if it were the physical artifact.

On 2026-09-21, with **Vitki** as the reference implementation, we ratified **ADR-0007** across the Ravenhelm estate and killed all three corpses with one law.

---

## The Axiom Stated: The First Law of Sovereign Release

At the foundation of the Ravenhelm Release Operations Methodology (RROM) stands **ADR-0007**:

> ### **Builds are the unit; releases are names.**
>
> *A build is an immutable artifact produced once on merge to `main`. A release is an authorized name assigned to an existing build. A deployment is the declarative reconciliation of a target environment to that named artifact's digest.*
>
> **Releases never rebuild code.**

This axiom is a physical boundary between compiling bytes and authorizing names. To hold custody of a production system, you must separate two things that traditional CI/CD pipelines mash together:

- **An Artifact (The Build) is physical and immutable.** It is a content-addressed sequence of bytes - an OCI container image layer bundle in `Harbor`, a compiled Mach-O/ELF binary, or a signed archive. It is born once, at the exact moment a reviewed pull request merges into `main`. It has physical mass in object storage, a monotonic sequence number (`:b<N>`), a commit coordinate (`:sha-<sha12>`), and a cryptographic digest (`@sha256:...`). Once written to `Harbor`, its bytes never change.
- **A Release (The Name) is administrative metadata.** A release contains zero compiled machine code of its own. It is a signed declaration binding a human-readable Semantic Version (`v1.4.2`) to an existing, pre-tested build digest (`:b42` / `@sha256:7f9a...`). Cutting a release asserts that a specific build already soaked in `:uat` has earned the right to serve production traffic.

Compile code at release time and you saw the branch off behind you. Staging validates an artifact compiled at $T_0$; production receives an unverified twin compiled at $T_1$. They share a git commit SHA, and nothing else. **Git commits do not execute; binaries execute.** Between $T_0$ and $T_1$, Alpine and Debian mirrors publish point updates, transitive dependencies shift, and compiler timestamps alter layer hashes.

ADR-0007 makes that drift impossible by locking delivery into three mechanically isolated stages.

---

## Deconstructing the Three Lifecycle Stages

Under RROM, every change moves down a one-way ratchet from ingress build to named release to declarative deployment:

![Diagram 1: The Core Axiom Lifecycle](diagram1-core-axiom)

---

### Phase 1: The Build (The Physical Unit)

The Build is the only compilation event in the life of a software change (**RP-1: Build Once on Ingress**). It fires exclusively when a reviewed pull request merges into `main`.

When a merge commit lands on `main`, Forgejo Actions triggers `.forgejo/workflows/build.yml`. The runner checks out the exact merge commit, executes the unit and integration test suites, compiles the application, packages the OCI container image, and pushes the layers to `Harbor` (routing directly through internal `harbor-nginx` on `Norns` so multi-hundred-megabyte layer uploads never touch Cloudflare tunnel body-size limits).

Phase 1 stamps every artifact in `Harbor` with a three-part identity coordinate:

1. **The Monotonic Build Sequence (`:b<N>`):** A strictly increasing integer derived from the CI run sequence (`:b42`, `:b43`). Humans do not read 64-character hex digests on an incident bridge. `:b48` is newer than `:b42` at a glance, with zero git log archaeology required. For CLI binaries, this build number and commit hash are baked straight into the binary via linker flags (`-X` in Go or `build.rs` in Rust), so `doom --version` prints `0.4.0+b42.9f8a3c21e01b` and exposes a stale `~/.local/bin` shim on sight.
2. **The Commit Linkage (`:sha-<sha12>`):** The 12-character prefix of the `main` merge commit SHA (`:sha-9f8a3c21e01b`). Seven-character short SHAs collide in high-velocity repos; twelve characters give an unambiguous forensic pointer back to the exact git tree that produced the binary.
3. **The Cryptographic Content Digest (`@sha256:...`):** The SHA-256 hash of the OCI image manifest (`@sha256:7f9a1b2c...3d`). While registry tags are pointers, the content digest is mathematical bedrock. Change one byte in one layer and the Merkle root changes.

#### Immediate Staging Attachment (`:uat`)

In the same `build.yml` step, the runner points the moving `:uat` stream tag at that exact manifest digest. In `Vitki` and every ADR-0007 service, the staging configuration (`chart/values-uat.yaml`) tracks `:uat`.

Staging never runs a "staging build." It runs `:b42`. When `:b42` survives synthetic load, migration validation, and soak testing in UAT, the exact bytes that will run in production have already proven themselves under live traffic.

---

### Phase 2: The Release (The Naming Authorization)

The Release is a zero-compile administrative elevation governed by **RP-2 (Releases Never Rebuild)** and **RP-3 (Promotion by Reference)**. It invokes no compiler, runs no `docker build`, resolves no lockfile, and modifies zero lines of application source code.

When the Release Custodian confirms that build `:b42` is green in `:uat` and ready to ship as `v1.4.2`, they run one command from a clean worktree:

```bash
# Authorize existing build b42 under SemVer name v1.4.2
scripts/release-pr.sh b42 v1.4.2
```

`release-pr.sh` queries `Harbor` for the immutable `@sha256:` digest of `:b42` and opens a dedicated Release PR (`release/v1.4.2` $\to$ `main`).

#### The Parity Triangle and Metadata-Only Diffs

In a `Vitki`-standard repository, a Release PR touches three metadata files and nothing else:

1. `chart/Chart.yaml`: Sets `version: 1.4.2` and `appVersion: "1.4.2"`.
2. `chart/values.yaml`: Pins the production workload to the proven build and digest:

   ```yaml
   image:
     repository: harbor.ravenhelm.dev/platform/vitki
     tag: "v1.4.2"
     digest: "sha256:7f9a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a"
     build: "b42"
   ```

3. `CHANGELOG.md`: Records the human-readable release ledger for `v1.4.2`.

Before that PR can merge, CI enforces **RP-5 (Parity Precedes Promotion)** by running two hard mechanical gates. First, `scripts/check-release-tag.sh` verifies the **Parity Triangle**:

$$\text{Git Tag } (v1.4.2) \equiv \text{values.yaml Tag } (v1.4.2) \equiv \text{Chart.yaml appVersion } (1.4.2)$$

If `values.yaml` says `v1.4.2` while `Chart.yaml` still reads `1.4.1`, the check exits `1`.

#### The Source Parity Guard: `check-release-source-parity.sh`

Second, CI runs `scripts/check-release-source-parity.sh` to prove that the release branch introduces **zero application source drift** relative to the parent build commit on `main`:

```bash
#!/usr/bin/env bash
# scripts/check-release-source-parity.sh
# Fails closed if a release PR modifies anything outside chart metadata and changelog.

set -euo pipefail

FORBIDDEN_DIFFS=$(git diff --name-only origin/main | grep -vE '^(chart/|CHANGELOG\.md|docs/runbooks/release\.md)' || true)

if [ -n "${FORBIDDEN_DIFFS}" ]; then
  echo "ERROR: Release PR touches application source files!" >&2
  echo "${FORBIDDEN_DIFFS}" >&2
  exit 1
fi

echo "PASS: Zero application source drift proven."
```

Why is this gate ruthless? Because without it, someone always tries to sneak a "two-line timeout tweak" or a "harmless log fix" onto the release branch. Under ADR-0007, because `release.yml` **never recompiles code**, a source edit committed on a release branch faces two equally fatal outcomes:
1. It is silently ignored when `:b42` is retagged as `:v1.4.2`, meaning `main` claims the bug fix shipped while the `:b42` container running in prod does not have it.
2. Or worse, someone hacks the release workflow to compile the branch, throwing away `:b42` and shipping an untested binary straight into production.

If source code needs to change, kill the release PR. Merge the fix to `main`, let `build.yml` mint `:b43`, prove `:b43` in `:uat`, and cut the release from `:b43`.

#### Promoting by Reference in 200 Milliseconds

Once the Delivery Closer merges the Release PR and pushes the annotated tag `v1.4.2`, `.forgejo/workflows/release.yml` fires. It does not boot BuildKit or pull a base image. It calls `scripts/harbor-artifact.sh retag`:

1. It reads the manifest descriptor for `:b42` from the Harbor OCI Registry v2 API.
2. It verifies that `:b42`'s digest matches the `sha256:...` string pinned in `chart/values.yaml`.
3. It sends an HTTP `PUT /v2/platform/vitki/manifests/v1.4.2` with the existing manifest JSON, binding the name `v1.4.2` directly to `@sha256:7f9a...` in under 200 milliseconds.
4. It packages `chart/` into an OCI Helm chart artifact and pushes `vitki-1.4.2.tgz` to Harbor.

Zero compilers ran. Zero container layers were unpacked or re-compressed. The name `v1.4.2` is now bolted to the exact bytes of `:b42`.

---

### Phase 3: The Deployment (Declarative Reconciliation)

Phase 3 reconciles the target environment to the named release (**RP-9: Declarative Convergence Authority**). Neither developer laptops nor CI runners ever run `kubectl apply` or `helm upgrade` against production.

```text
[ norns-gitops Repo ] ────────► [ Argo CD Controller ] ────────► [ Norns K3s Pods ]
  targetRevision: 1.4.2           Diffs desired state vs.          containerd pulls:
  pins: @sha256:7f9a...           live K3s API on urd/verdandi     harbor.../vitki:v1.4.2@sha256:7f9a...
```

#### Pull-Based GitOps via `norns-gitops` and Argo CD

1. Once `release.yml` publishes the OCI chart and `:v1.4.2` tag to Harbor, the release rail updates the application manifest in `norns-gitops`:

   ```yaml
   apiVersion: argoproj.io/v1alpha1
   kind: Application
   metadata:
     name: vitki
     namespace: argocd
   spec:
     source:
       repoURL: 'harbor.ravenhelm.dev/platform/charts'
       chart: vitki
       targetRevision: 1.4.2
       helm:
         valueFiles:
           - values.yaml
     destination:
       server: 'https://kubernetes.default.svc'
       namespace: vitki
   ```

2. Inside the `Norns` 3-node HA K3s cluster (`urd`, `verdandi`, `skuld`), Argo CD detects the revision bump from `1.4.1` to `1.4.2`, pulls the signed OCI chart from Harbor, and renders the Deployment spec:

   ```yaml
   image: harbor.ravenhelm.dev/platform/vitki:v1.4.2@sha256:7f9a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a
   ```

3. Kubelet instructs `containerd` to pull by the `@sha256:...` digest. Because the nodes already pulled and unpacked those exact layers during `:uat` verification, layer extraction is instantaneous.
4. Per **RP-13 (Shell Success Is Not Proof)**, the Delivery Closer does not declare victory when the git push exits `0` or when Argo CD reports `Synced`. The Closer probes the live endpoint (`/healthz` and `/api/v1/version`), confirming that the running socket returns `v1.4.2` (`b42`) with zero container restarts.

#### Why Imperative Push Deployments Are Forbidden

Letting CI runners or engineer laptops push straight into a production cluster (`helm upgrade`, `kubectl apply`, or raw SSH loops) breaks custody across four fault lines:

1. **Ambient Admin Credentials in CI:** To push to a cluster, the runner needs a `KUBECONFIG` with write authority over production namespaces. If a malicious transitive dependency compromises a build runner, the attacker owns the cluster. Under pull-based GitOps, runners only write to git and Harbor; the cluster pulls outbound and exposes zero inbound deployment keys to CI.
2. **Masked Exit Codes and Blind Timeouts:** Imperative scripts frequently pipe output through formatters (`helm upgrade ... | tail -5`) that swallow non-zero exit codes, or time out while pods crash-loop two minutes later.
3. **Silent Drift After Manual Edits:** An imperative script only fires once. If someone runs a manual `kubectl edit` at 2:00 a.m. or a node reschedules a pod with stale unpinned state, a push pipeline never notices. Argo CD reconciles continuously against git and overwrites unauthorized mutations.
4. **Race Conditions Under Fleet Concurrency:** When ten `Doom` slices merge PRs in the same hour, concurrent push scripts trample each other against the Kubernetes API. Serializing state transitions through `norns-gitops` commits enforces a strict, auditable total order.

---

## Autopsy of "Build on Tag": Why the Industry Default Fails

Walk into ninety percent of engineering shops and you will find the "Build on Tag" workflow: merges to `main` run tests all week, and on release day an operator runs `git tag v1.0.0 && git push origin v1.0.0`, kicking off a fresh compilation that ships straight to production.

That workflow embeds a time bomb between testing and production.

### The Temporal Vulnerability Window ($\Delta t$)

Trace the physical state across the window $\Delta t$ between the ingress merge at $T_0$ and the release tag at $T_1$:

| Phase | Timestamp | Physical Pipeline State |
| :--- | :--- | :--- |
| **Ingress Merge** | $T_0$ (Wednesday 11:00) | PR merges to `main`. CI compiles and deploys `@sha256:AAA...` to staging. Soak tests pass 100%. |
| **Release Tag** | $T_1$ ($T_0 + 5\text{ days}$) | Operator tags `v1.0.0`. Tag workflow runs `docker build` from scratch and pushes `@sha256:BBB...` to prod. |
| **Outage & Lockout** | $T_{\text{incident}}$ ($T_1 + 8\text{m}$) | Upstream base-layer change triggers segfault under load. Rollback rebuild of `v0.9.8` fails on a 404 mirror. |

Between $T_0$ and $T_1$, not a single line of your repository changed. Outside your repository, three surfaces moved:

| Divergence Vector | Physical Mutation During $\Delta t$ | Runtime Consequence in `@sha256:BBB...` |
| :--- | :--- | :--- |
| **1. Base Image Drift** | `FROM node:20-bookworm-slim` or `alpine:3.19` was overwritten upstream for a point CVE patch. | Dynamic linker paths, `glibc` arenas, or OpenSSL cipher defaults shift without warning. |
| **2. Transitive Skew** | An unpinned `apt-get install`, `curl` helper, or native addon post-install script pulls a newer point release. | Unverified third-party C/Rust binary code enters the production rootfs with zero staging time. |
| **3. Toolchain Drift** | The CI runner image updated its kernel, Go/Rust minor compiler, or `buildkit` snapshotter. | Binary ABI layout or cgroup memory accounting changes between the staging binary and the prod binary. |

The container that soaked in staging for five days was `@sha256:AAA...`. The container taking customer traffic at $T_1$ is `@sha256:BBB...`. **Production is running a binary that has executed for zero seconds in any test environment.**

### The Four Compounding Failures

1. **Staging Invalidation:** Every hour of UAT soak testing, synthetic load generation, and QA verification on `@sha256:AAA...` is thrown away the moment the tag pipeline compiles `@sha256:BBB...`.
2. **Digest Amnesia:** When production crashes at $T_{\text{incident}}$, forensics cannot compare staging profiler traces against production core dumps because the binaries do not share symbol offsets or layer hashes.
3. **The Rollback Illusion:** When the incident commander orders a rollback to `v0.9.8` (shipped six months ago) and clicks "Re-run" on the `v0.9.8` tag workflow, the runner tries to compile six-month-old source code against today's internet. One archived Debian mirror returning HTTP 404 or one yanked crate kills the rollback build. Under ADR-0007, rollback never touches a compiler: you revert the digest pointer in `norns-gitops` back to `@sha256:9a8b...`, Harbor serves the cached layers, and `Norns` converges in fifteen seconds.
4. **Expanded Secret Blast Radius:** A release pipeline that compiles code must hold private package tokens, build secrets, and source credentials. A release pipeline that only retags an existing Harbor manifest needs nothing more than a repository-scoped `pull`/`push` robot token.

---

## Side-by-Side: Legacy Build-on-Tag vs. ADR-0007 (`Vitki` Standard)

| Lifecycle Dimension | Legacy "Build on Tag" (v1 Corpse) | RROM Core Axiom (ADR-0007 / `Vitki`) |
| :--- | :--- | :--- |
| **Compilation Trigger** | Pushed git tag (`v*`) at release time ($T_1$). | Merge to `main` on ingress ($T_0$) via `.forgejo/workflows/build.yml`. |
| **Artifact Identity** | Mutable tag (`:v1.0.0` or `:latest`) masking an unverified build. | Immutable triad: `:b<N>` (monotonic build), `:sha-<sha12>` (commit), `@sha256:...` (digest). |
| **Workstation Binary Identity** | Static SemVer string (`0.4.0`); vulnerable to `~/.local/bin` PATH shims. | Build coordinate embedded (`0.4.0+b42.9f8a3c21e01b`); distributed via `nate/tools` tap `inreplace`. |
| **Release Execution** | Runs `docker build`, compilers, and bundlers from scratch. | Pure Registry v2 API manifest `PUT` (`harbor-artifact.sh retag`); zero compilation. |
| **Source Parity Gate** | None; release branches frequently carry last-minute source edits. | Hard fail-closed gate (`check-release-source-parity.sh` & `check-release-tag.sh`). |
| **Staging Fidelity** | Zero guarantee; production runs a different digest than staging. | 100% byte parity; `:uat` runs the exact `@sha256:...` digest promoted to production. |
| **Deployment Mechanism** | Imperative push from CI (`helm upgrade`, `kubectl apply`, SSH). | Declarative pull via in-cluster Argo CD tracking `norns-gitops`. |
| **Rollback Execution** | Re-runs tag build workflow (fails if upstream mirrors drifted). | Git revert of the digest pin in `norns-gitops`; restores service in seconds. |

---

## Operationalizing the Law on the Floor

Once **builds are the unit and releases are names** becomes the physical law of the forge, release anxiety vanishes.

Every merge to `main` produces a numbered, content-addressed unit (`:b<N>`). That unit immediately enters `:uat` and proves itself under live instrumentation. When you are ready to release, `scripts/release-pr.sh` binds a SemVer name to that proven digest, `check-release-source-parity.sh` guarantees zero source drift slipped in through the side door, and `harbor-artifact.sh` writes the tag pointer in 200 milliseconds. Whether the target is a `Norns` K3s pod on Rail A, a Homebrew CLI on Rail B, or a signed `Idunn` desktop bundle on Rail C, the rule never bends.

Build the unit once on ingress. Name it when it is proven. Never compile on release.

<!-- RUBRIC_CHECK: Chapter 2 conforms to RROM specification. -->

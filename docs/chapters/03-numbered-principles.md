# Chapter 3: The Numbered Principles

<!-- LICENSE: © 2026 Ravenhelm LLC. Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Attribution required: "Ravenhelm LLC — Ravenhelm Release Operations Methodology (RROM), https://ravenhelm.dev". -->

## Why the Floor Needs Numbers

On 2026-09-09, an audit across the estate turned up ten merged features backed by 73 passing unit tests that had **zero callers** in the running system: a 46 KB `wire.py` protocol module imported nowhere, a `vodozemac-bridge` crate sitting unlinked, and an `ensure_receiver()` lifecycle hook bypassed entirely by `doom new --launch`. Every one had green tests. None of them ran. One month later, on 2026-10-09, `domainintelligenceschema` (`DIS`) shipped `v1.8.0` via PR #11, announcing seven new ontology constructs on the live documentation site while `grep` across `vocabulary/`, `shapes/`, `cue/`, and `tests/` returned zero matches.

Pleading with engineers - or autonomous `Doom` worker slices - to "be more careful during release review" fixes nothing. The social layer does not transfer to a fleet of thirty concurrent AI sessions, and it barely survives a tired human on-call rotation at 2:00 a.m. You do not govern a forge with reminders. You write down the physical invariants that bind source commits to running bytes, give each invariant a canonical number (`RP-1` through `RP-18`), and wire those numbers into fail-closed shell scripts that break the build the second a boundary is crossed.

If you adopt only one principle from this book, lock in **RP-1: Build Once on Ingress**. Eliminating release-time compilation kills the single largest source of unverified production binaries on day one.

---

## How to Cite the Principles on the Bench

A principle that never appears in a pull request block, a CI failure log, an Architectural Decision Record (ADR), or an incident timeline is shelfware. On the Ravenhelm floor, operators and automated reviewers (`Snotra` and the `Doomcourt` supervisor) cite principles by number to terminate ambiguity:

- **In Pull Request Blocks:** *"Holding merge per `RP-5`: `release/v1.4.2` modifies `src/core/parser.rs`, violating zero-drift source parity against parent build `:b42`."*
- **In Pipeline Failure Logs:** *"FATAL (`RP-4`): `chart/values.yaml` declares mutable tag `:v1.4.2` without an immutable `@sha256:` digest pin."*
- **In Incident Post-Mortems:** *"Outage traced to an un-gated datastore swap violating `RP-11` (`ADR-011`). The transport replacement shipped inside a minor version bump without an accepted ADR or migration gate."*
- **In Live Recovery Commands:** *"Reverting `norns-gitops` digest pointer to `:b88` per `RP-14`."*

> ### Augmentation Surface - Automated Principle Enforcement
>
> **Where Autonomous Agent Layers Excel:**  
> Static policy scripts and advisory review agents (`Snotra`) verify every PR and registry state transition against `RP-1` through `RP-18`. They run `check-release-source-parity.sh` (`RP-5`), verify `@sha256:` pins in Helm values (`RP-4`), grep release artifacts against advertised changelog claims (`RP-13`), and verify `.bare` worktree custody before running git commands (`RP-18`).
>
> **What the Human Operator Retains:**  
> The human operator holds non-delegable custody over architectural cutover gates (`RP-11`), hardware-signed **Action-Hash Elevation (Valkyrie MFAA)** tokens (`RP-12`, `RP-17`), and final release merge-and-deploy execution (`RP-10`). Agents assemble the cryptographic receipts; a human clicks the accept/reject button.

The principles divide into four operational categories:

1. **Category I: Artifact Custody & Immutability** (`RP-1` through `RP-5`)
2. **Category II: Multi-Surface Rails** (`RP-6` through `RP-8`)
3. **Category III: Deployment Authority & Cutover Governance** (`RP-9` through `RP-12`)
4. **Category IV: Verification, Rollback & Custody Hygiene** (`RP-13` through `RP-18`)

---

## Category I: Artifact Custody & Immutability

Category I governs how source commits become binary units in `Harbor`, how those units are addressed by the kernel, and how names are attached without ever invoking a compiler twice.

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

**Canonical Statement:** Compile, package, and push the artifact exactly once, triggered exclusively when an approved pull request merges into `main`.

**Bench Physics:** A build consumes a git source tree and resolves external state (Debian/Alpine package mirrors, crates.io, PyPI, npm, compiler timestamps). Wait five days after merging to `main` and compile again on a release tag, and you will not get the same bytes. On 2026-09-21, **ADR-0007** locked the `Vitki` reference pattern across the estate: `.forgejo/workflows/build.yml` fires on `push: branches: [main]`, compiles the artifact once, pushes the layers through internal `harbor-nginx` to `Harbor`, and stamps the manifest with a monotonic build sequence (`:b<N>`), the 12-char commit SHA (`:sha-<sha12>`), the moving staging pointer (`:uat`), and its immutable `@sha256:<digest>`.

**The v1 Corpse:** *The Build-on-Tag Pipeline.* Prior to ADR-0007, repositories ran tests on merge to `main` and ran `docker build` a second time when a `vX.Y.Z` tag was pushed. Upstream base layers and dynamic libraries shifted between the UAT soak and the tag build, shipping a binary to production that had executed for zero seconds in staging.

**Mechanical Gate:** `.forgejo/workflows/build.yml` triggers strictly on `main` ingress. `scripts/check-pipeline-purity.sh` scans `.forgejo/workflows/release.yml` and fails the build if any compiler or image builder (`docker build`, `buildctl`, `cargo build`, `go build`, `npm run build`) appears in the release workflow.

---

### RP-2: Releases Never Rebuild

**Canonical Statement:** A release is an administrative act of naming that binds a Semantic Version tag (`vX.Y.Z`) to an existing `:b<N>` digest in `Harbor`; release workflows never invoke a compiler, bundler, or image builder.

**Bench Physics:** In an OCI registry (`Harbor`), a tag is a 32-byte pointer to a manifest SHA-256 digest. When `:b42` has soaked in `:uat` and passed verification, its physical bytes are proven. Rebuilding code during the release step destroys that proof by minting a new hash. Under ADR-0007 (`Vitki` reference), cutting `v1.4.2` calls `scripts/harbor-artifact.sh retag`, which fetches the existing manifest JSON for `:b42` over the Docker Registry HTTP API v2 and `PUT`s that exact JSON to `/v2/<project>/<repo>/manifests/v1.4.2`. The operation completes in 200 milliseconds and transfers zero layer blobs.

**The v1 Corpse:** *Release-Time Compilation Lockout.* During an incident hotfix, a v1 tag-build workflow tried to recompile a full Rust/C++ workspace from scratch. Twelve minutes in, an external package CDN threw an HTTP 504, killing the release job when a pre-built ingress image from `main` was already sitting in `Harbor`.

**Mechanical Gate:** `release.yml` executes `scripts/harbor-artifact.sh retag` and asserts cryptographic digest equality between the source build and the new release tag before exiting:

```bash
BUILD_DIGEST=$(./scripts/harbor-artifact.sh digest "b${BUILD_NUM}")
RELEASE_DIGEST=$(./scripts/harbor-artifact.sh digest "${SEMVER_TAG}")
[[ "${BUILD_DIGEST}" == "${RELEASE_DIGEST}" ]] || exit 1
```

---

### RP-3: Promotion by Reference

**Canonical Statement:** Advance software from `:uat` to production exclusively by updating declarative digest pointers in git manifests, never by copying, re-uploading, or re-bundling image layers across separate registries.

**Bench Physics:** Content-Addressable Storage in `Harbor` deduplicates every layer blob by its SHA-256 hash. Both the `:uat` deployment and the production deployment on `Norns` pull from the same canonical `Harbor` repository. Promoting `:b42` from `:uat` to production moves zero binary files; `scripts/release-pr.sh` writes `:b42`'s `@sha256:...` digest into `chart/values.yaml` and publishes the signed OCI Helm chart version to `norns-gitops`.

**The v1 Corpse:** *Bastion Pull-Tag-Push Drift.* Pulling an image onto an intermediate runner to run `docker tag` and `docker push` into a second registry re-serializes the manifest through the runner's local container daemon, frequently altering compression headers and mutating the canonical manifest `sha256` digest.

**Mechanical Gate:** `scripts/check-release-tag.sh` queries `Harbor` directly during the release PR gate and verifies that the `image.digest` written in `chart/values.yaml` exists in `Harbor` and matches the manifest digest of `image.build` (`:b<N>`).

---

### RP-4: Tags for Humans, Digests for Runtime

**Canonical Statement:** Every production workload manifest must render container images in dual `repository:tag@sha256:<digest>` syntax; the tag is for human operators, and the SHA-256 digest is the scheduling truth for the kernel.

**Bench Physics:** OCI tags are mutable pointers. If a Kubernetes Deployment specifies `image: harbor.ravenhelm.dev/platform/freyr-api:latest` or `:v1.4.0` without a digest, `containerd` resolves the tag against its local node cache (`IfNotPresent`) or pulls whatever currently sits at that tag (`Always`). When `urd` caches Monday's `:v1.4.0` and `skuld` pulls Tuesday's overwritten `:v1.4.0`, the cluster runs split-brain binaries under one label. Pinning `vitki:v1.4.2@sha256:7f9a...` gives operators readable `kubectl get pods` output while forcing `containerd` to verify the exact Merkle root and `ChainID` of every unpacked layer.

**The v1 Corpse:** *The `freyr-api :latest` Auto-Roll (2026-09-16).* During the September 2026 audit, `freyr-api` was found running in production against a floating `:latest` tag without a digest pin. Every pod reschedule silently pulled the newest trunk build into production without a release PR or a human closer.

**Mechanical Gate:** `scripts/check-release-tag.sh` and pre-merge linters in `norns-gitops` reject any production manifest whose `image:` string lacks a 64-character hex `@sha256:` pin:

```bash
grep -E 'image:\s+.*:[a-zA-Z0-9_.-]+@sha256:[a-f0-9]{64}' rendered-manifest.yaml || {
    echo "FATAL: RP-4 Violation - Missing immutable @sha256 digest pin" >&2
    exit 1
}
```

---

### RP-5: Parity Precedes Promotion

**Canonical Statement:** A release pull request must prove zero application source code drift against its parent build commit on `main`; it may modify only `chart/Chart.yaml`, `chart/values.yaml`, and `CHANGELOG.md`.

**Bench Physics:** Because `release.yml` never compiles code (`RP-2`), any change to `src/`, `Cargo.toml`, `go.mod`, or application assets committed onto a `release/vX.Y.Z` branch will never be compiled into the released binary. Worse, it lies in git history by making `vX.Y.Z` look as if it contains source changes that do not exist inside the `:b<N>` container image. Furthermore, the three release metadata files must agree with each other - the **Parity Triangle**: Git tag `vX.Y.Z` $\equiv$ `chart/values.yaml` `image.tag` $\equiv$ `chart/Chart.yaml` `appVersion`.

**The v1 Corpse:** *The Drive-By Release Branch Patch.* An operator preparing a release branch commits a "two-line config fix" alongside the version bump. The release workflow retags the pre-existing `:b42` image, shipping the old unpatched binary while git `main` shows the bug fixed.

**Mechanical Gate:** Every release PR runs two mandatory scripts before merge: `scripts/check-release-tag.sh` (enforcing the Parity Triangle and Harbor digest existence) and `scripts/check-release-source-parity.sh`:

```bash
FORBIDDEN_DIFFS=$(git diff --name-only origin/main | grep -vE '^(chart/|CHANGELOG\.md|docs/runbooks/release\.md)' || true)
if [[ -n "${FORBIDDEN_DIFFS}" ]]; then
    echo "FATAL: RP-5 Violation - Release PR modifies application source files:" >&2
    echo "${FORBIDDEN_DIFFS}" >&2
    exit 1
fi
```

---

## Category II: Multi-Surface Rails

Category II governs repositories whose code ships across more than one physical surface: cluster pods on Rail A, workstation CLI/TUI tools on Rail B, and signed client applications on Rail C.

```
+───────────────────────────────────────────────────────────────────────────────────+
| CATEGORY II: THE MULTI-SURFACE RAILS                                              |
|                                                                                   |
|  [ Ingress Build :b<N> ]                                                          |
|         │                                                                         |
|         ├─► Rail A: Server GitOps (Norns K3s / OCI Helm / Harbor)                 |
|         │                                                                         |
|         ├─► Rail B: Workstation CLI/TUI (nate/tools Tap / Sandboxed Inreplace)    |
|         │                                                                         |
|         └─► Rail C: Sovereign Client Apps (Idunn / Minisign Ed25519 Manifests)    |
|                                                                                   |
|  RP-6: Multi-Surface Lockstep       --> All rails ship in the same release run    |
|  RP-7: Sandboxed Inreplace          --> Zero-drift Homebrew source compilation    |
|  RP-8: Sovereign Binary Distro      --> Detached Ed25519 signatures verified live |
+───────────────────────────────────────────────────────────────────────────────────+
```

### RP-6: Multi-Surface Lockstep

**Canonical Statement:** Dual-surface repositories (such as `Ullr`/`Yager`, which ship both a `Norns` K3s server workload and a workstation CLI) must execute Rail A (Harbor OCI + `norns-gitops`) and Rail B (`nate/tools` Homebrew tap bump + local reinstall proof) in lockstep on every release.

**Bench Physics:** A server daemon and its operator CLI are two halves of one wire protocol. When the cluster pod advances to `v1.4.0` on `Norns` while the operator's macOS workstation still runs `v1.3.2` (or runs a stale shim pretending to be current), the next CLI command fired from the bench sends an obsolete payload or misparses the server's response. Under ADR-0007, dual-surface repos execute both rails in a single release transaction.

**The v1 Corpse:** *The Stale `doom` Shim at `PATH` Index 5 (2026-08-13).* Running `doom update` under the old self-updater invoked `uv tool install --force --editable`, planting a binary shim at `~/.local/bin/doom` (`PATH` index 5) ahead of Homebrew's `/opt/homebrew/bin/doom` (`PATH` index 9) that pointed at an old worktree while printing the exact same `--version` string.

**Mechanical Gate:** For dual-surface repositories, `.forgejo/workflows/release.yml` runs both the Harbor OCI promotion job (Rail A) and the `nate/tools` tap formula commit job (Rail B). On the workstation, post-release verification asserts both `which -a <tool>` path hygiene and exact build-coordinate output (`<tool> --version` matching `vX.Y.Z+b<N>.<sha12>`).

---

### RP-7: Sandboxed Inreplace for Ecosystem Tooling

**Canonical Statement:** For source-compiled workstation formulas in the private Homebrew tap (`nate/tools`), keep the repository's language manifest (`Cargo.toml`, `pyproject.toml`) untouched on release PRs and inject the release version dynamically inside the Homebrew build sandbox via `inreplace`.

**Bench Physics:** If you edit `Cargo.toml` on a release branch to change `version = "0.0.0-dev"` to `version = "1.4.2"`, you modify a tracked source file and trip `check-release-source-parity.sh` (`RP-5`). Worse, bumping `Cargo.toml` dirties `Cargo.lock`, forcing a rebuild and breaking byte parity with the ingress commit. By leaving `Cargo.toml` fixed in git and running Homebrew's `inreplace` macro inside the isolated temporary build directory during `brew install`, the git tree keeps 100% source parity with `:b<N>` while the compiled `/opt/homebrew/bin/<tool>` binary reports the exact SemVer and build coordinate.

**The v1 Corpse:** *Version-Bump Lockfile Churn.* Committing version bumps to `Cargo.toml` on release branches triggered `check-release-source-parity.sh` failures and caused constant merge conflicts across concurrent `Doom` worker worktrees.

**Mechanical Gate:** `check-release-source-parity.sh` blocks any release PR that touches `Cargo.toml` or `Cargo.lock`. The tap formula (`Formula/yager.rb` in `nate/tools`) performs the substitution inside `def install`:

```ruby
def install
  inreplace "Cargo.toml", 'version = "0.0.0-dev"', "version = \"#{version}\""
  system "cargo", "install", *std_cargo_args
end
```

---

### RP-8: Sovereign Binary Distribution

**Canonical Statement:** Client desktop and edge bundles (`Idunn`) must ship as immutable archives paired with detached Ed25519 cryptographic signatures (`Minisign`) and verified against signed update manifests before installation.

**Bench Physics:** Client binaries run on endpoints outside the `Norns` cluster boundary. Relying on HTTPS transport alone means a compromised CDN token or a misconfigured object bucket can serve a trojan binary to every workstation on auto-update. Under `RP-8`, the release workflow signs the ingress-built client archive with an offline-rooted Ed25519 Minisign key (`minisign -S -m <bundle>.tar.zst`) and writes the detached `.minisig` signature and `sha256` hash into the update manifest (`latest.json`).

**The v1 Corpse:** *Unsigned Tarball Overwrites.* Serving raw client archives from an object store with only HTTP 200 status checks allowed truncated downloads and mismatched builds to overwrite working local installations without halting the updater.

**Mechanical Gate:** Before publishing `latest.json`, the release pipeline runs an out-of-band verification check against the uploaded archive and signature:

```bash
minisign -V -p "${MINISIGN_PUBKEY}" -m "${BUNDLE_ARCHIVE}" -x "${BUNDLE_ARCHIVE}.minisig" || {
    echo "FATAL: RP-8 Violation - Detached Ed25519 signature verification failed!" >&2
    exit 1
}
```

---

## Category III: Deployment Authority & Cutover Governance

Category III establishes who may mutate production state, connects PR merge authorization directly to live deployment, separates routine deploys from architectural cutovers, and strips ambient credentials from CI runners.

```
+───────────────────────────────────────────────────────────────────────────────────+
| CATEGORY III: DEPLOYMENT AUTHORITY & CUTOVER GOVERNANCE                           |
|                                                                                   |
|  [ Approved Release PR ] ─────────► RP-10: Merge-Then-Deploy + Expected-Fire Gate |
|                                            │                                      |
|                                            ▼                                      |
|  [ Production Cluster / Host ] ───► RP-9: Declarative Convergence Authority       |
|                                     (Argo CD / GitOps Pull ONLY; No Laptop Push)  |
|                                                                                   |
|  [ Architectural Mutation? ] ─────► RP-11: Cutovers Require ADRs (ADR-011)        |
|                                     (Repo/DB/Transport Swap != Routine Deploy)    |
|                                                                                   |
|  [ CI Pipeline Execution ] ───────► RP-12: Zero Ambient CI Authority              |
|                                     (OpenBao AppRoles + Action-Hash Elevation)    |
+───────────────────────────────────────────────────────────────────────────────────+
```

### RP-9: Declarative Convergence Authority

**Canonical Statement:** Production hosts (`odin`, `hrafngud`) and clusters (`Norns` K3s) never accept imperative push deployments from laptops or CI runners; an in-cluster declarative reconciler (Argo CD tracking `norns-gitops`) is the sole applying authority.

**Bench Physics:** Running `kubectl apply`, `helm upgrade`, or direct SSH edits on `odin` leaks uncommitted workstation state into production and leaves zero self-healing loop when a node restarts. Under `RP-9`, every production mutation lands as a reviewed git commit in the declarative control repository (`norns-gitops`). Argo CD inside `Norns` (`urd`, `verdandi`, `skuld`) polls the repository, computes the resource diff, and converges the cluster toward the pinned `@sha256:` digest.

**The v1 Corpse:** *Direct SSH Edits & Stale Checkouts on Host.* Editing files directly over SSH or pulling into detached checkouts (`~/var/apps/import-backup` sitting 2 commits behind in detached HEAD while PR #22 had already merged to `main`) left production running ghost configurations that vanished on the next container recreate.

**Mechanical Gate:** CI workflows possess zero production `KUBECONFIG` admin tokens; their authority ends at committing the digest bump to `norns-gitops`. Any manual drift applied to `Norns` namespaces is overwritten by Argo CD's automated self-heal sync loop and flagged in audit telemetry.

---

### RP-10: Merge-Then-Deploy

**Canonical Statement:** Approval to merge a release PR is explicit authorization to deploy that release to production immediately, verify that the post-merge workflow actually fired, and prove it running live.

**Bench Physics:** Letting merged commits sit undeployed on `main` turns trunk into a minefield: the next engineer who needs to ship an urgent fix is forced to deploy somebody else's unverified changes along with their own. Under `RP-10`, the moment Nate approves a PR (*"merge it"* / *"approved, ship"* / *"LGTM merge"*), the supervisor session squash-merges the PR and immediately rides the deployment rail to completion. Crucially, because a workflow that never triggers reports zero failures, the closer must verify **expected-fire presence**: confirming that the merge commit actually spawned a `build.yml` / `release.yml` run ID on the code host.

**The v1 Corpse:** *The Silent Non-Fire on `main` (2026-09-16) & Merged-Not-Running PRs (2026-09-13).* On 2026-09-13, three merged PRs were reported complete while `the-work` masthead was never redeployed. Three days later, on 2026-09-16, `deploy.yml` silently failed to fire on 1 of 24 pushes to `main`. Because 23 runs succeeded and 0 failed, commit statuses stayed green while production ran yesterday's binary.

**Mechanical Gate:** The Delivery Closer queries the Forgejo Actions API for the exact `merge_commit_sha` immediately after merging. If zero workflow runs exist for that SHA within 30 seconds, the pipeline fails closed on a missing-trigger alarm before ever checking job status.

---

### RP-11: Cutovers Require ADRs

**Canonical Statement:** Any change that swaps a deployed service's codebase, replaces a datastore engine, removes a transport protocol, or alters cluster RBAC boundaries is an architectural cutover, not a deploy; it requires a ratified ADR, a verified data-migration plan, a pre-flight permission proof (`kubectl auth can-i`), and explicit human cutover approval.

**Bench Physics:** A deployment updates an image digest inside an unchanged architectural contract. A cutover changes the contract itself. Treating a cutover as a routine version bump skips dual-write migration windows, strands live state, and breaks RBAC mid-rollout. Furthermore, any deploy that introduces new SQL migrations or new Kubernetes resource kinds must verify migration execution and deployer RBAC before merge.

**The v1 Corpse:** *The `Bifrost` Cutover Incident (`ADR-011`, 2026-07-18) & The `RAV-2086` Deployer RBAC Blindspot (2026-09-29).* On 2026-07-18, an autonomous session swapped the `Bifrost` MCP gateway's serving stack and backing store inside a routine PR without an ADR or migration plan, dropping live fleet traffic. On 2026-09-29 (`RAV-2086`), `bifrost` PR #37 added `PrometheusRule` resources and failed immediately on first deploy because nobody ran `kubectl auth can-i create prometheusrules --as=system:serviceaccount:bifrost:bifrost-deployer` during plan verification.

**Mechanical Gate:** CI diffs release PRs for cutover signatures (datasource scheme changes, new CRD kinds in `chart/templates/`, transport removals, or unapplied `migrations/*.sql`). Any match halts the pipeline unless an accepted ADR link is bound, `apply-migrations.sh` is wired into the rollout hook, and `kubectl auth can-i` passes against every rendered resource kind in `chart/templates/`.

---

### RP-12: Zero Ambient CI Authority

**Canonical Statement:** CI runners and automation workers hold zero permanent cluster-admin tokens, static cloud keys, or human personal access tokens (PATs); routine jobs authenticate via short-lived, service-scoped `OpenBao` AppRoles, and privileged mutations require single-use **Action-Hash Elevation (Valkyrie MFAA)** tokens.

**Bench Physics:** CI runners execute third-party dependencies and container build steps. Any permanent admin token injected into a runner environment is one compromised package away from exfiltration. Worse, storing raw secrets in Kubernetes manifests without neutralizing client-side annotations leaks the secret into plaintext metadata. Under **The Zero-Ambient Elevation Doctrine**, runners authenticate with their own narrow `OpenBao` AppRole (scoped strictly to their repository and Harbor project) and never borrow a human operator's PAT.

**The v1 Corpse:** *The `rig-ci` Annotation Leak (2026-09-29) & The `frs #88` Personal PAT Outage (2026-10-08).* On 2026-09-29, applying a Secret with `kubectl apply` stamped the plaintext `rig-ci` Harbor robot token straight into the `kubectl.kubernetes.io/last-applied-configuration` annotation, readable by any principal with metadata view rights. On 2026-10-08 (`frs #88`), `forgejo-runner-scheduler` control loops ran using an operator's personal PAT instead of the service's own credential, breaking KEDA autoscaling across the runner fleet the moment personal token scopes shifted.

**Mechanical Gate:** Workflows authenticate to `OpenBao` via short-lived AppRole/OIDC tokens (`ttl: 10m`) to fetch repository-scoped Harbor push credentials. Secret syncs in Kubernetes use server-side apply (`kubectl apply --server-side`) or ExternalSecrets from `OpenBao` so `last-applied-configuration` never touches a Secret resource.

---

## Category IV: Verification, Rollback & Custody Hygiene

Category IV enforces live runtime proof over shell exit codes, instantaneous pointer rollback, strict Semantic Versioning contracts, coverage-verified audit ledgers, blast-radius isolation, and `.bare` git worktree custody.

```
+───────────────────────────────────────────────────────────────────────────────────+
| CATEGORY IV: VERIFICATION, ROLLBACK & CUSTODY HYGIENE                             |
|                                                                                   |
|  [ Deployment Reconciled ] ─► RP-13: Shell Success Is Not Proof (Live + Grep Gate)|
|                                      │                                            |
|                                      ▼                                            |
|  [ Health Probe Failed? ] ──► RP-14: Fail-Closed Rollback (Instant Digest Revert) |
|                                      │                                            |
|                                      ▼                                            |
|  [ Contract Evolution ] ────► RP-15: Strict SemVer Contract (Breaking = MAJOR)    |
|                                      │                                            |
|                                      ▼                                            |
|  [ Forensic Audit Log ] ────► RP-16: Immutable Ledgers & Non-Empty Checksums      |
|                                      │                                            |
|                                      ▼                                            |
|  [ Security Isolation ] ────► RP-17: Separation of Blast Radii (Valkyrie MFAA)    |
|                                      │                                            |
|                                      ▼                                            |
|  [ Operator Environment ] ──► RP-18: Clean Worktree Custody (.bare + No Stash)    |
+───────────────────────────────────────────────────────────────────────────────────+
```

### RP-13: Shell Success Is Not Proof

**Canonical Statement:** Exit code `0`, HTTP `200 OK` on an auth probe, or a passing unit test suite is never proof that a feature shipped or works; every release must prove both **artifact presence** (every advertised construct exists in the shipped artifact) and **live reachability** (the production socket responds with the new build coordinate and exercises the live code path).

**Bench Physics:** Shell pipelines lie whenever exit codes are masked (`unittest | tail -5`), whenever endpoints return HTTP 200 with empty capability sets (`Harbor`'s `/service/token` returning `200 OK` with `"access": []` on bad credentials), or whenever unit tests exercise dead code that nothing in `main()` ever wires up. Proving a release requires two independent receipts: an **Artifact-Grep Gate** proving the shipped schema/binary actually contains what `CHANGELOG.md` claims, and a **Live Reachability Probe** hitting the production endpoint over the wire.

**The v1 Corpse:** *The Ten Ghosts of 2026-09-09 & The `DIS 1.8` Fiction Release (2026-10-09).* On 2026-09-09, ten merged features across the fleet sat with 73 green unit tests and zero callers in production (`wire.py`, `vodozemac-bridge`, `ensure_receiver()`). On 2026-10-09, `DIS` PR #11 deployed `v1.8.0` advertising seven new constructs on the live website that had zero matches in `vocabulary/`, `shapes/`, `cue/`, or `tests/`.

**Mechanical Gate:** `scripts/verify-release-claims.sh` extracts every backticked identifier declared in the new `CHANGELOG.md` section and greps the compiled artifact/schema tree (failing closed on `0` hits), followed by `scripts/verify-runtime-proof.sh` polling the live endpoint until `/api/v1/version` returns both `EXPECTED_SEMVER` and `EXPECTED_BUILD_NUM` (`:b<N>`).

---

### RP-14: Fail-Closed Rollback

**Canonical Statement:** Rollback is an instantaneous git revert of the `@sha256:` digest pointer in `norns-gitops`, never a re-compilation of an older tag; furthermore, neither Harbor registries nor Kubernetes job controllers may auto-delete failed artifacts or crashed pod logs (`failedJobsHistoryLimit` must be $\ge 3$).

**Bench Physics:** When a release degrades production, you have seconds to restore service and minutes to capture forensic evidence. Because `Harbor` retains the immutable `:b<N>` digests of previous releases, reverting the digest commit in `norns-gitops` instructs Argo CD and `containerd` to switch back to the cached layers of `:b<N-1>` in under fifteen seconds. At the same time, the failed pods and their logs must survive so the operator can read the stack trace.

**The v1 Corpse:** *Evidence Destruction by `failedJobsHistoryLimit: 0` (2026-09-17).* When the `bifrost` and `Norns` backup CronJobs crashed in September 2026, their manifests had `failedJobsHistoryLimit: 0` (or relied on default pod eviction without log retention), causing Kubernetes to delete the crashed pod and its stdout/stderr the instant it failed.

**Mechanical Gate:** Harbor retention policies forbid deleting any `v*` tag or its underlying `@sha256:` manifest. Helm chart linters reject any `Job` or `CronJob` manifest that sets `failedJobsHistoryLimit: 0` or omits `activeDeadlineSeconds` when `concurrencyPolicy: Forbid` is set.

---

### RP-15: Strict SemVer Contract

**Canonical Statement:** Any backward-incompatible change to an HTTP route, MCP tool schema (`Bifrost`), protobuf/gRPC contract, CLI flag (`Ullr`/`Yager`, `Doom`), or database column requires a MAJOR version increment under Semantic Versioning 2.0.0.

**Bench Physics:** Across a distributed estate where `Freyr`, `Bifrost`, `Heimdall`, `Mimir`, and workstation CLIs call each other continuously, a PATCH or MINOR release is a promise that existing callers will not break during a rolling update. Renaming a JSON key or dropping an MCP tool parameter in a minor bump breaks in-flight agent slices the moment the first pod rolls.

**The v1 Corpse:** *Silent Schema Skew Across Agent Slices.* Renaming a payload field inside a minor bump caused running `Doom` worker slices on older CLI versions to fail deserialization mid-wave while the server reported HTTP 200 health checks.

**Mechanical Gate:** CI runs contract diff gates against `origin/main` (`buf breaking`, `oasdiff -check-breaking`, or `cargo-semver-checks`). Any breaking interface delta without a MAJOR version bump in `chart/Chart.yaml` fails the PR check with exit code `1`.

---

### RP-16: Immutable Audit Ledgers

**Canonical Statement:** Every release, promotion, and backup attestation must write a tamper-evident receipt binding git commit SHA, `:b<N>`, `@sha256:` digest, and human approver identity - and every verification script must assert **non-empty input** before comparing hashes.

**Bench Physics:** An audit ledger or backup verification script that only checks whether two variables are equal is a trap: if both commands fail and return empty strings, `[[ "${ACTUAL_SHA}" == "${EXPECTED_SHA}" ]]` evaluates `"" == ""` as `true` and prints `PASS`. Every provenance and restore checker must first prove that the artifact exists, is non-empty, covers the full inventory of databases/targets, and matches a valid 64-character hex `sha256` regex before comparing values.

**The v1 Corpse:** *The `"" == ""` Empty Checksum Pass (`RAV-2079`) & The 1-of-8 Postgres Backup (`hrafngud`, 2026-09-17).* In `RAV-2079`, a broken restore verification script extracted an empty hash from a failed archive and an empty hash from the manifest, evaluated `"" == ""`, and certified a corrupted restore as valid (`matches backup ()`). On `hrafngud`, `/opt/ravenhelm/backup.sh` logged seven months of green exit-zero ledger entries while dumping only `-d ravenmaskos` (1 of 8 databases) and leaving `outline`, `harbor`, and `keycloak_dev` completely unbacked up.

**Mechanical Gate:** Provenance and checksum guards fail closed unless every hash matches `^[a-f0-9]{64}$` and the target count equals the live catalog count:

```bash
[[ "${ACTUAL_SHA}" =~ ^[a-f0-9]{64}$ && "${EXPECTED_SHA}" =~ ^[a-f0-9]{64}$ ]] || {
    echo "FATAL: RP-16 Violation - Empty or malformed sha256 digest!" >&2
    exit 1
}
[[ "${ACTUAL_SHA}" == "${EXPECTED_SHA}" ]] || exit 1
```

---

### RP-17: Separation of Blast Radii

**Canonical Statement:** Segregate routine application releases from control-plane, identity-plane (`Zitadel`, `Keycloak`), secret-engine (`OpenBao`), and registry RBAC (`Harbor`) mutations; control-plane mutations require **Action-Hash Elevation (Valkyrie MFAA)** bound to the exact execution plan digest.

**Bench Physics:** If a routine application PR and an `OpenBao` root policy mutation share the same pipeline authority, a prompt-injected agent or a compromised build script can escalate its own privileges and merge the change. Under **Action-Hash Elevation (Valkyrie MFAA)**, control-plane pipelines can only generate a deterministic read-only plan (`terraform plan -out=tfplan.bin`), hash the binary plan (`sha256sum tfplan.bin`), and halt. Applying the plan requires a hardware-signed FIDO2/Ed25519 Valkyrie token bound cryptographically to that exact `PLAN_HASH`.

**The v1 Corpse:** *Shared Deployer Scope Across Application and Monitoring Planes.* Giving a single pipeline token broad write authority across both application workloads and cluster-wide security/monitoring CRDs either over-privileges the routine build runner or causes silent mid-deploy permission crashes when boundaries change.

**Mechanical Gate:** Control-plane workflows halt after plan generation and invoke `valkyrie verify-approval`:

```bash
PLAN_HASH=$(sha256sum tfplan.bin | awk '{print $1}')
[[ "${PLAN_HASH}" =~ ^[a-f0-9]{64}$ ]] || exit 1
valkyrie verify-approval \
  --action "control-plane-apply" \
  --target "${TARGET_ENV}" \
  --hash "${PLAN_HASH}" \
  --token "${VALKYRIE_MFAA_TOKEN}" || exit 1
```

---

### RP-18: Clean Worktree Custody

**Canonical Statement:** Execute every feature branch, release PR (`release-pr.sh`), and emergency hotfix inside a dedicated, disposable git worktree rooted in a canonical `.bare/` repository per the Checkout Custody Standard; never run `git stash` to carry work across branch switches.

**Bench Physics:** When humans and concurrent `Doom` worker slices share a traditional single-worktree clone or use `git stash` to hop between branches, uncommitted edits, untracked files, and orphaned stashes bleed directly into release branches or vanish into unreachable reflog commits. Under the Checkout Custody Standard, history lives once in `<repo>/.bare/`, `remote.origin.fetch` is explicitly configured (`+refs/heads/*:refs/remotes/origin/*`), every PR gets its own isolated worktree directory, and deleting a worktree requires proving zero uncommitted lines and zero unpushed commits.

**The v1 Corpse:** *215 of 217 Non-Conformant Repos (2026-08-14), 277 Stranded Lines in `yager` (2026-08-31), and 81 Dangling Tips (2026-09-11).* On 2026-08-14, 215 of 217 estate checkouts violated custody layout, and 26 `.bare` units learned the hard way on 2026-08-24 that `git clone --bare` omits a fetch refspec by default (leaving 5 blind and 21 with a hollow origin). On 2026-08-31, 277 uncommitted lines of the `TurnPhase` state machine were nearly deleted inside the already-merged `yager/rav-1541-dashboard` worktree. Eleven days later, on 2026-09-11, a fleet sweep uncovered 81 dangling commit tips and 15 unpushed branches across five repos surviving only in reflog.

**Mechanical Gate:** `scripts/release-pr.sh` verifies clean worktree custody and an explicit fetch refspec before creating a release branch:

```bash
# 1. Refuse to run if working tree or index has any uncommitted changes
if [[ -n "$(git status --porcelain)" ]]; then
    echo "FATAL: RP-18 Violation - Dirty working tree. Commit WIP or use a fresh worktree." >&2
    exit 1
fi
# 2. Assert remote.origin.fetch is configured (no hollow .bare origin)
git config --get remote.origin.fetch >/dev/null || {
    echo "FATAL: RP-18 Violation - Missing remote.origin.fetch refspec in .bare repository!" >&2
    exit 1
}
```

---

## Summary Reference Matrix (`RP-1` through `RP-18`)

| ID | Principle | Core Invariant | Primary Estate Receipt / Gate |
| :--- | :--- | :--- | :--- |
| **RP-1** | **Build Once on Ingress** | Compile once on merge to `main` (`:b<N>`, `:sha-<sha12>`, `:uat`, `@sha256:...`). | `ADR-0007` (`Vitki` `build.yml`, 2026-09-21). |
| **RP-2** | **Releases Never Rebuild** | Releases retag existing Harbor manifests via Registry v2 API in 200ms. | `scripts/harbor-artifact.sh retag`. |
| **RP-3** | **Promotion by Reference** | Environments advance by updating digest pointers in git, never copying blobs. | `norns-gitops` OCI chart target bumps. |
| **RP-4** | **Tags for Humans, Digests for Runtime** | Render `repo:tag@sha256:<digest>` in every production pod spec. | 2026-09-16 `freyr-api :latest` drift fix. |
| **RP-5** | **Parity Precedes Promotion** | Release PRs touch zero application source code; Parity Triangle holds. | `check-release-source-parity.sh` & `check-release-tag.sh`. |
| **RP-6** | **Multi-Surface Lockstep** | Dual-surface repos (`Ullr`/`Yager`) ship Rail A (K3s) and Rail B (Tap) together. | 2026-08-13 `doom` `~/.local/bin` PATH shim fix. |
| **RP-7** | **Sandboxed Inreplace** | Keep `Cargo.toml` untouched in git; inject SemVer in Homebrew sandbox. | `Formula/yager.rb` in `nate/tools`. |
| **RP-8** | **Sovereign Binary Distribution** | Sign standalone client bundles (`Idunn`) with detached Ed25519 Minisign keys. | `minisign -V` gate prior to `latest.json` publish. |
| **RP-9** | **Declarative Convergence Authority** | In-cluster Argo CD pulls from `norns-gitops`; zero laptop/CI imperative pushes. | `Norns` K3s (`urd`, `verdandi`, `skuld`) GitOps loop. |
| **RP-10** | **Merge-Then-Deploy** | Merge approval is deploy approval; verify expected-fire workflow run ID. | 2026-09-16 `deploy.yml` silent non-fire on 1 of 24 pushes. |
| **RP-11** | **Cutovers Require ADRs** | Stack/DB/transport swaps require an ADR, migration plan, and `auth can-i` proof. | `ADR-011` (`Bifrost`, 2026-07-18) & `RAV-2086` (2026-09-29). |
| **RP-12** | **Zero Ambient CI Authority** | Service-scoped `OpenBao` AppRoles; zero personal PATs or plaintext annotations. | 2026-09-29 `rig-ci` leak & 2026-10-08 `frs #88` KEDA outage. |
| **RP-13** | **Shell Success Is Not Proof** | Prove artifact presence (`grep` claims) and live socket reachability. | 2026-09-09 Ten Ghosts & 2026-10-09 `DIS 1.8` PR #11. |
| **RP-14** | **Fail-Closed Rollback** | Revert digest in `norns-gitops`; keep `failedJobsHistoryLimit >= 3`. | 2026-09-17 CronJob corpse deletion fix. |
| **RP-15** | **Strict SemVer Contract** | Breaking API, MCP tool, or CLI changes require a MAJOR version bump. | `buf breaking` / `oasdiff` / `cargo-semver-checks`. |
| **RP-16** | **Immutable Audit Ledgers** | Sign provenance receipts; assert non-empty regex before hash comparison. | `RAV-2079` `"" == ""` bug & 1-of-8 Postgres dump fix. |
| **RP-17** | **Separation of Blast Radii** | Gate identity/secret/RBAC plans behind **Action-Hash Elevation (Valkyrie MFAA)**. | Hardware FIDO2 signature bound to `sha256(tfplan.bin)`. |
| **RP-18** | **Clean Worktree Custody** | Work in disposable `.bare` worktrees with fetch refspecs; never `git stash`. | 2026-08-31 `yager` rescue & 2026-09-11 81 dangling tips. |

<!-- RUBRIC_CHECK: Chapter 3 conforms to RROM specification. -->

# Chapter 8: The Tiered Adoption Ladder

<!-- LICENSE: © 2026 Ravenhelm LLC. Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Attribution required: "Ravenhelm LLC — Ravenhelm Release Operations Methodology (RROM), https://ravenhelm.dev". -->

## Four Maturity Tiers of Release Operations

When `jarvis.ravenhelm.dev` started throwing HTTP 502 Bad Gateway errors on `odin`, the first debugging session burned an hour restarting the wrong container stack because two separate `docker-compose.yml` files sat in sibling directories on the host (`jarvis-502-wrong-compose`). Around the same time, `freyr-api` was running in production pinned to a mutable `:latest` tag; every time a background image watcher polled the registry after an unverified merge, production silently rolled itself onto whatever bits had just finished compiling on `main`. There was no digest pin, no release PR, and no rollback target.

Every engineering estate starts in that mud. You stand up a single box (`odin` or `hrafngud`), run `docker compose up -d`, and ship by SSHing in or letting a webhook rebuild `:latest`. The mistake is either staying in Tier 0 until fifty services are colliding on unpinned tags, or swinging to the opposite extreme (the Hal Problem: rewiring the entire house to change a lightbulb by trying to stand up hardware-token MFAA elevation and three-node K3s GitOps before shipping a single service).

Just as the Ravenhelm Linear Operations Methodology (RLOM) scales work tracking from a solo workbench to a multi-contract enterprise, the Ravenhelm Release Operations Methodology (RROM) climbs a four-tier physical custody ladder. In the Ravenhelm estate, **Project Factory** encodes these tiers directly into repository scaffolding so new services inherit the right release machinery on day one.

| Maturity Tier | Organizational Scale | Core Capability & Milestone Invariant |
| :--- | :--- | :--- |
| **Tier 1: Artifact Discipline** | 1 to 3 Engineers | Build once on merge to `main`; monotonic build sequence (`:b<N>`); zero tag-time compilation. |
| **Tier 2: Registry & Digest Locking** | 4 to 12 Engineers | Triple-tagging in Harbor; mandatory `@sha256:...` digest pinning; automated source-parity checks. |
| **Tier 3: Multi-Rail Declarative GitOps** | 13 to 50 Engineers | Sole-authority GitOps (`norns-gitops` / Argo CD); Rail A + Rail B lockstep; sandboxed formula `inreplace`. |
| **Tier 4: Sovereign Zero-Trust Delivery** | 50+ Engineers | Hard blast-radius partitioning; Action-Hash Elevation (Valkyrie MFAA); signed Ed25519 desktop OTA. |

---

## Tier 1: Artifact Discipline (The Solo Developer / Free Tier)

**Core Focus:** Kill tag-time compilation and establish the `:b<N>` build as the immutable physical unit of delivery.

### 1. Target Organization Profile & Team Scale
- **Team Size:** 1 to 3 engineers.
- **Architecture:** Single service or small daemon pair running in containers or standalone binaries.
- **Infrastructure:** Single bare-metal host or VM (like early `odin` or `hrafngud`) running a single canonical Docker Compose project or systemd unit.
- **Release Cadence:** Daily or weekly releases driven by the primary builder.

### 2. Pain Points & Ceilings Hit

Tier 0 (the unmanaged baseline) dies from two self-inflicted wounds: **tag-time rebuilding** and **`:latest` auto-rolling**:
- **The "It Worked in Staging" Lie:** A PR merges to `main`, builds a staging container, and passes manual checks. Three days later, someone runs `git tag v1.0.4 && git push --tags`. The CI runner executes `docker build` all over again under the tag ref, pulls a newly published transitive package or Alpine base layer, and ships a binary that never ran a single minute in staging.
- **The `freyr-api :latest` Trap:** Pointing a production stack at `:latest` turns every trunk merge into an unannounced production deploy and leaves you with zero prior digest to revert to when the new build crashes on startup.
- **25-Minute Release Anxiety:** When cutting a release requires a full compile, a flaky npm or crates.io mirror mid-tag leaves the release half-shipped.

### 3. Complete Technical Stack & Tooling Requirements
- **Code Host & CI:** Forgejo Actions or GitHub Actions.
- **Container Registry:** Harbor (`harbor.ravenhelm.dev`), GHCR (`ghcr.io`), or Forgejo's built-in OCI registry.
- **Runtime Orchestration:** Docker Compose v2 (from a single canonical path enforced by repo deployment workflows, never edited via manual SSH).
- **CLI Tooling:** `bash`, `docker`, and `git`.

### 4. Implementation Playbook

Moving a repository from Tier 0 to Tier 1 takes four edits:

#### Step 1: Split Build from Release

Delete every `docker build`, `cargo build`, or `npm run build` step from tag-triggered workflows. Split CI into two separate files: `build.yml` (triggered exclusively on push to `main`) and `release.yml` (triggered on `v*` tag pushes).

#### Step 2: Establish Ingress Build Pipeline on `main`

Configure `build.yml` to compile the artifact once on merge to `main`, stamp the monotonic build ID `:b<N>`, and push to the registry:

```yaml
# .forgejo/workflows/build.yml
name: Ingress Build
on:
  push:
    branches: [main]

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Compute Sequential Build ID
        id: build_id
        run: echo "build_number=b${{ github.run_number }}" >> $GITHUB_OUTPUT

      - name: Build Container Image
        run: |
          docker build \
            --tag harbor.ravenhelm.dev/platform/service:${{ steps.build_id.outputs.build_number }} \
            --tag harbor.ravenhelm.dev/platform/service:uat \
            .

      - name: Publish to Registry
        run: |
          docker push harbor.ravenhelm.dev/platform/service:${{ steps.build_id.outputs.build_number }}
          docker push harbor.ravenhelm.dev/platform/service:uat
```

#### Step 3: Implement Zero-Compilation Release Retagging

Configure `release.yml` to trigger on `v*` tags. It never invokes a compiler; it simply retags the proven `:b<N>` image:

```yaml
# .forgejo/workflows/release.yml
name: Release Promotion
on:
  push:
    tags: ['v*']

jobs:
  promote-release:
    runs-on: ubuntu-latest
    steps:
      - name: Validate Release Name
        run: |
          TAG_NAME="${{ github.ref_name }}"
          if [[ ! "${TAG_NAME}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo "ERROR: Tag ${TAG_NAME} does not follow SemVer format vX.Y.Z"
            exit 1
          fi

      - name: Retag Existing Build Digest
        run: |
          # Pull existing verified build - zero compilation permitted
          docker pull harbor.ravenhelm.dev/platform/service:uat
          docker tag harbor.ravenhelm.dev/platform/service:uat harbor.ravenhelm.dev/platform/service:${{ github.ref_name }}
          docker push harbor.ravenhelm.dev/platform/service:${{ github.ref_name }}
```

#### Step 4: Verify Tag-Manifest Alignment

Add a pre-flight check (`scripts/check-release-tag.sh`) that verifies the pushed git tag matches the version pinned in the deployment manifest before retagging.

### 5. Governance & Verification Gates
- **Gate 1.1 (No Compiler in `release.yml`):** Release workflows contain zero build steps.
- **Gate 1.2 (No `:latest` in Prod):** Production compose files and manifests are forbidden from referencing `:latest` or `:uat`.
- **Gate 1.3 (Target Existence Proof):** Retagging fails closed if the target `:b<N>` image does not already exist in the registry.

### 6. Operational Guarantees Unlocked
- **Zero-Rebuild Guarantee:** The bits running under `v1.2.0` in production are the exact bits compiled on `main`.
- **Sub-30-Second Naming:** Promoting a release takes seconds of registry API calls instead of 20 minutes of compilation.
- **Numbered Build Ledger:** Every merge to `main` leaves an immutable `:b<N>` receipt in the registry.

---

## Tier 2: Registry & Digest Locking (The Growing Startup)

**Core Focus:** Eliminate mutable tag poisoning, enforce three-way version parity, and block source-code smuggling on release branches.

### 1. Target Organization Profile & Team Scale
- **Team Size:** 4 to 15 engineers (or a supervisor managing multiple concurrent AI coding slices).
- **Architecture:** Multi-service backend (5 to 20 services), shared PostgreSQL (`ravenmaskos`), ClickHouse (`vakr`), and NATS JetStream infrastructure.
- **Infrastructure:** Dedicated staging (UAT) and production namespaces with Harbor (`harbor.ravenhelm.dev`) serving as the central OCI registry.
- **Release Cadence:** Dozens of daily trunk merges across concurrent worktrees; multiple production promotions per day.

### 2. Pain Points & Ceilings Hit

Once multiple engineers or agent slices merge concurrently, Tier 1's tag-only promotion breaks down:
- **The Moving `:uat` Race:** While Operator A is preparing to promote build `b42`, Slice B merges a new PR to `main`, advancing `:uat` to `b43`. If `release.yml` blindly retags `:uat`, Operator A accidentally promotes `b43` under `v1.4.2` without testing it.
- **The Release-Branch Code Smuggle:** An engineer cutting a release branch edits a `.ts` or `.rs` file on the release PR "just to fix a small bug." Because compilation only runs at Ingress on `main`, that source edit is never compiled into the container image, leaving git history and the running container out of sync.
- **Mutable Tag Overwrites:** Without `@sha256:` digest locking in deployment manifests, force-pushing a tag in the registry silently alters what nodes pull on restart.

### 3. Complete Technical Stack & Tooling Requirements
- **Code Host & CI:** Forgejo (`git.ravenhelm.dev`) or GitHub with branch protection and required CI status checks.
- **OCI Registry:** Harbor (`harbor.ravenhelm.dev`) with Registry v2 API access and tag immutability rules.
- **Configuration Management:** Helm 3 charts (`chart/Chart.yaml`, `chart/values.yaml`) scaffolded via **Project Factory**.
- **Automation Tooling:** `yq` v4, `jq`, `curl`, and the four canonical RROM scripts (`scripts/release-pr.sh`, `scripts/check-release-source-parity.sh`, `scripts/check-release-tag.sh`, `scripts/harbor-artifact.sh`).

### 4. Implementation Playbook

Upgrading from Tier 1 to Tier 2 installs the **Triple-Tagging Scheme**, **Harbor API Digest Resolution**, and **The Source Parity Guard**:

```text
[ INGRESS MERGE ]
       │
       ▼
[ Registry v2 Push ] ───> Triple Tags: :b<N> (Sequence) + :sha-<commit12> (Trace) + :uat (Stream)
                               │
                               ▼
[ Release PR Opened ] ───> scripts/release-pr.sh b<N> vX.Y.Z
                               │  - Resolves @sha256:<digest> for :b<N> via Harbor API
                               │  - Pins values.yaml to exact digest + build + commit
                               │  - Asserts zero application source code drift
                               ▼
[ Release Merged ]   ───> scripts/harbor-artifact.sh retag sha256:<digest> vX.Y.Z
```

#### Step 1: Implement Triple-Tagging on Ingress

Update `.forgejo/workflows/build.yml` so every merge to `main` pushes three tags pointing to the identical `@sha256:` digest:
1. `:b<N>` - The monotonic build sequence number (for example, `:b42`).
2. `:sha-<commit12>` - The 12-character git commit SHA (for example, `:sha-9f8a3c21e01b`).
3. `:uat` - The rolling staging pointer.

```bash
COMMIT12=$(echo "${GITHUB_SHA}" | cut -c1-12)
BUILD_ID="b${BUILD_NUMBER}"

docker tag "${LOCAL_IMAGE}" "harbor.ravenhelm.dev/platform/core:${BUILD_ID}"
docker tag "${LOCAL_IMAGE}" "harbor.ravenhelm.dev/platform/core:sha-${COMMIT12}"
docker tag "${LOCAL_IMAGE}" "harbor.ravenhelm.dev/platform/core:uat"

docker push "harbor.ravenhelm.dev/platform/core:${BUILD_ID}"
docker push "harbor.ravenhelm.dev/platform/core:sha-${COMMIT12}"
docker push "harbor.ravenhelm.dev/platform/core:uat"
```

#### Step 2: Lock Production Manifests to `@sha256:` Digests

Every `chart/values.yaml` pins the explicit build number, commit revision, SemVer tag, and immutable SHA-256 digest:

```yaml
# chart/values.yaml (Production)
image:
  repository: harbor.ravenhelm.dev/platform/vitki
  tag: v1.4.2
  digest: sha256:7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a
  build: b42
  revision: 9f8a3c21e01b38f87029c2ea55bd51ef350c33a2
```

And the Kubernetes `Deployment` template binds both tag and digest:

```yaml
# chart/templates/deployment.yaml
containers:
  - name: app
    image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}@{{ .Values.image.digest }}"
```

#### Step 3: Automate Release Pinning (`scripts/release-pr.sh`)

Instead of retagging the moving `:uat` pointer, `scripts/release-pr.sh b42 v1.4.2` queries Harbor for the exact digest of `b42`, resolves its `sha-<commit12>` tag, writes the coordinates into `chart/Chart.yaml` and `chart/values.yaml`, and immediately runs the parity check:

```bash
#!/usr/bin/env bash
# scripts/release-pr.sh <build-id> <semver-tag>
set -euo pipefail

BUILD="$1"
TAG="$2"
SEMVER="${TAG#v}"

# 1. Resolve immutable digest for specific build ID via Harbor API
DIGEST=$(scripts/harbor-artifact.sh digest "${BUILD}")
if [[ -z "${DIGEST}" ]]; then
  echo "ERROR: Build ${BUILD} not found in Harbor." >&2
  exit 1
fi

# 2. Update Helm Chart and values metadata
yq -i ".version = \"${SEMVER}\"" chart/Chart.yaml
yq -i ".appVersion = \"${SEMVER}\"" chart/Chart.yaml
yq -i ".image.tag = \"${TAG}\"" chart/values.yaml
yq -i ".image.digest = \"${DIGEST}\"" chart/values.yaml
yq -i ".image.build = \"${BUILD}\"" chart/values.yaml

# 3. Verify zero source code drift against the build commit
scripts/check-release-source-parity.sh "${DIGEST}" HEAD
```

#### Step 4: Enforce Source Parity (`check-release-source-parity.sh`)

`scripts/check-release-source-parity.sh` compares the git tree of the commit that built `:b42` against the release branch `HEAD`, rejecting any diff outside `chart/` and `CHANGELOG.md`:

```bash
#!/usr/bin/env bash
# scripts/check-release-source-parity.sh <digest> <tag-commit>
set -euo pipefail

BUILD_COMMIT=$(scripts/harbor-artifact.sh build-commit "$1")
TAG_COMMIT="${2:-HEAD}"

if ! git diff --quiet "$BUILD_COMMIT" "$TAG_COMMIT" -- . ':(exclude)chart' ':(exclude)CHANGELOG.md'; then
  echo "REFUSING: release commit modifies application source files since build commit ${BUILD_COMMIT}:" >&2
  git diff --name-only "$BUILD_COMMIT" "$TAG_COMMIT" -- . ':(exclude)chart' ':(exclude)CHANGELOG.md' >&2
  exit 1
fi

echo "PASS: Source parity verified between ${BUILD_COMMIT} and ${TAG_COMMIT}."
```

### 5. Governance & Verification Gates
- **Gate 2.1 (The Source Parity Gate):** CI blocks any release PR that touches `.rs`, `.go`, `.ts`, `.py`, `.sql`, or dependency manifests (`Cargo.toml`, `package.json`).
- **Gate 2.2 (The Three-Way Tag Gate):** `scripts/check-release-tag.sh` verifies `git tag == values.yaml (.image.tag) == "v" + Chart.yaml (.version)`.
- **Gate 2.3 (Harbor Tag Immutability):** `scripts/harbor-artifact.sh retag` checks via `HEAD /v2/.../manifests/<tag>` before writing and refuses to overwrite an existing tag pointing to a different digest.

### 6. Operational Guarantees Unlocked
- **Race-Free Promotion:** Even if ten commits land on `main` while `b42` is soaking in UAT, `release-pr.sh b42 v1.4.2` promotes `b42` by its exact digest, never what happens to sit at `HEAD`.
- **Cryptographic Lineage:** Every running pod's `@sha256:` digest traces directly back to `:b<N>` and `:sha-<commit12>`.
- **Zero Uncompiled Code:** No source change can ever slip into a release tag without first passing through an ingress build.

---

## Tier 3: Multi-Rail Declarative GitOps (The Scaling Team)

**Core Focus:** Establish Argo CD (`norns-gitops`) as the sole applying cluster authority, synchronize Rail A (K3s cluster) and Rail B (Homebrew workstation tools), and eliminate dirty-laptop cluster applies.

### 1. Target Organization Profile & Team Scale
- **Team Size:** 15 to 75 engineers (or a full multi-slice autonomous fleet supervised across platforms and products).
- **Architecture:** Microservices running on the 3-node `Norns` HA K3s cluster (`urd`, `verdandi`, `skuld`) paired with native Rust and Go developer CLIs/TUIs (`Ullr`, `Yager`, `Doom`) on operator workstations.
- **Infrastructure:** `Norns` K3s cluster reconciled by Argo CD from `nate/norns-gitops`, Harbor storing both OCI container images and OCI Helm charts, and the private Homebrew tap (`nate/homebrew-tools`).
- **Release Cadence:** Continuous UAT rollouts on every merge; daily coordinated multi-rail releases.

### 2. Pain Points & Ceilings Hit

At Tier 3 scale, the failures shift from single-repo build drift to **cross-surface skew** and **imperative cluster drift**:
- **Dirty-Laptop `kubectl apply` Drift:** An operator applies a hot patch to `Norns` from a local worktree using `kubectl edit` or `helm upgrade`. Nothing is committed to `norns-gitops`, so the very next release PR silently wipes out the hot patch.
- **Dual-Surface Skew (`Ullr` / `Yager`):** Updating the `Norns` cluster pods on Rail A without updating the Homebrew formula on Rail B (or leaving a rogue `~/.local/bin` shim ahead of `/opt/homebrew/bin` on `$PATH`) leaves the operator CLI speaking yesterday's wire protocol against today's server.
- **The `Cargo.toml` vs. Parity Deadlock:** Homebrew compiles Rust tools from tagged git archives. Bumping `Cargo.toml` in git for Homebrew trips Tier 2's `check-release-source-parity.sh`; leaving `Cargo.toml` at `0.1.0` without formula intervention causes `yager --version` to print `0.1.0` forever.

### 3. Complete Technical Stack & Tooling Requirements
- **GitOps Engine:** Argo CD running inside `Norns` with `selfHeal: true` and `prune: true`.
- **Three-Repo Custody Topology:**
  1. Application Repository (`nate/vitki`, `nate/yager`): Houses code, `chart/`, and `scripts/release-pr.sh`.
  2. Cluster GitOps Repository (`nate/norns-gitops`): Houses Argo CD `Application` manifests and pinned environment values.
  3. Private Homebrew Tap (`nate/homebrew-tools`): Houses `Formula/<tool>.rb` definitions for workstation CLIs.
- **Local Process Management:** `process-compose` for any local multi-daemon development workflows (PM2 and raw background `&` are banned estate-wide).

### 4. Implementation Playbook

Migrating to Tier 3 enforces the **Strict GitOps Boundary**, **Sandboxed Formula Inreplace**, and **Dual-Rail Lockstep**:

```text
[ DUAL-SURFACE RELEASE PR ] (e.g., Ullr / Yager)
          │
          ├──> [ Rail A: Norns K3s Cluster GitOps ]
          │       │
          │       ▼
          │    1. Retag Harbor OCI digest + push OCI Helm chart vX.Y.Z
          │    2. Merge PR in nate/norns-gitops updating targetRevision & digest
          │    3. Argo CD reconciles urd/verdandi/skuld; live daemon socket verified
          │
          └──> [ Rail B: Workstation Developer CLI ]
                  │
                  ▼
               1. Compute SHA-256 of tagged vX.Y.Z source tarball
               2. Merge PR in private Homebrew tap (nate/homebrew-tools)
               3. Formula runs sandboxed inreplace on Cargo.toml in /private/tmp
               4. brew upgrade installs synced binary; which -a confirms 1 path
```

#### Step 1: Lock the GitOps Boundary on `Norns`

Strip direct imperative deployment steps from workstation scripts and app-repo CI jobs. Argo CD is the sole applying authority on `Norns`, reconciling declarative PRs merged into `nate/norns-gitops`.

#### Step 2: Configure Dual Argo CD Streams (UAT vs. Production)

Inside `norns-gitops`, separate the auto-syncing UAT stream from the digest-pinned Production stream:

```yaml
# norns-gitops/apps/vitki-prod.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: vitki-prod
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://git.ravenhelm.dev/nate/vitki.git
    targetRevision: v1.4.2
    path: chart
    helm:
      valueFiles:
        - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: platform
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

#### Step 3: Implement Sandboxed Formula Inreplace (Rail B)

Keep `Cargo.toml` pinned at `"0.1.0"` in git so `check-release-source-parity.sh` stays green, and inject `#{version}` inside the Homebrew build sandbox in `Formula/yager.rb`:

```ruby
# nate/homebrew-tools: Formula/yager.rb
class Yager < Formula
  desc "Terminal User Interface and agent harness"
  homepage "https://github.com/nwalker85/yager"
  url "https://github.com/nwalker85/yager/archive/refs/tags/v0.1.33.tar.gz"
  sha256 "a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5"
  license "Proprietary"

  depends_on "rust" => :build

  def install
    # Dynamically inject release version inside /private/tmp without touching git
    inreplace "Cargo.toml", /^version = .*/, "version = \"#{version}\""
    inreplace "Cargo.lock", /name = "yager"\nversion = "[0-9.]+"/, "name = \"yager\"\nversion = \"#{version}\""

    system "cargo", "install", *std_cargo_args
  end

  test do
    assert_match "yager #{version}", shell_output("#{bin}/yager --version")
  end
end
```

#### Step 4: Enforce Merge-Then-Deploy Across Both Rails (RP-6 & RP-10)

Under **RP-10 (Merge-Then-Deploy)**, approval to merge a PR is approval to drive the release through both rails and prove it running. A dual-surface release is not closed until Argo CD reports `Synced / Healthy` on `Norns`, the live daemon endpoint returns the new build ID, `brew upgrade` completes on the workstation, and `which -a <tool>` confirms no `~/.local/bin` shim is shadowing `/opt/homebrew/bin/<tool>`.

### 5. Governance & Verification Gates
- **Gate 3.1 (GitOps Exclusivity):** Out-of-band `kubectl edit` mutations on `Norns` are automatically overwritten by Argo CD `selfHeal`.
- **Gate 3.2 (Dual-Rail Lockstep Gate):** Dual-surface repos (`Ullr`, `Yager`) must ship Rail A and Rail B in the same release cycle.
- **Gate 3.3 (Live Daemon Proof Gate):** Closure requires querying the live daemon socket (never a UI that falls back to mock data) and recording the output in the Linear validation comment.

### 6. Operational Guarantees Unlocked
- **Zero Cluster Configuration Drift:** Every running pod and `ConfigMap` on `Norns` matches `norns-gitops` commit history.
- **Zero Workstation-to-Cluster Skew:** Operator CLIs and cluster backends advance in lockstep.
- **Sub-30-Second GitOps Rollback:** Reverting a single commit in `norns-gitops` restores the previous cached digest across `urd`, `verdandi`, and `skuld`.

---

## Tier 4: Sovereign Elevation & Zero-Trust Delivery (The Enterprise)

**Core Focus:** Partition blast radiuses, strip ambient root credentials from CI runners, enforce cryptographic **Action-Hash Elevation (Valkyrie MFAA)** for control-plane mutations, and ship signed Ed25519 desktop OTA bundles on Rail C.

### 1. Target Organization Profile & Team Scale
- **Team Size:** 50+ engineers, regulated enterprises (SOC 2 Type II, ISO 27001, FedRAMP), or sovereign high-autonomy AI fleets where autonomous coding agents execute continuous deployments alongside human operators.
- **Architecture:** Multi-node Kubernetes (`Norns`), identity and secrets control planes (`Zitadel`, `Keycloak`, `OpenBao`), dedicated container runner pools (`eikthyrnir` managed by `forgejo-runner-scheduler`), and native desktop GUI shells (`Idunn` on Tauri v2).
- **Infrastructure:** Zero-ambient-authority secrets architecture (`OpenBao` AppRoles + `Valkyrie` MFAA broker) with hardware security tokens (FIDO2 / WebAuthn / YubiKey).

### 2. Pain Points & Ceilings Hit

When autonomous AI agents and CI runners can merge PRs and trigger deployments around the clock, Tier 3 GitOps hits a hard security ceiling:
- **The Ambient Runner Credential Risk:** If a CI runner holds static, ambient admin tokens for `OpenBao`, `Harbor`, `Keycloak`, or `Norns` `cluster-admin`, a single compromised build dependency or hallucinating agent command can mutate RBAC policies, exfiltrate secrets, or wipe an identity realm.
- **The Unattended Issuance Fallacy:** On September 14, 2026, court card `dr-8` asked how Draupnir could allow *"unattended issuance with no human signer."* The ruling (seq 859) laid down the law: *"the entire point is accountability being attributed to the human actor. this shouldnt have even been a question."* Tools and agents prepare evidence and plans; a human clicks the accept/reject button on control-plane mutations.
- **Desktop Client OTA Tampering (Rail C):** Shipping pre-compiled desktop `.app.tar.gz` bundles to operator machines without asymmetric Ed25519 signature verification exposes every workstation to supply-chain replacement.

### 3. Complete Technical Stack & Tooling Requirements
- **Secrets & Identity Plane:** `OpenBao` on `Norns` with short-lived AppRole leases, paired with `Zitadel` / `Keycloak` OIDC.
- **Cryptographic Elevation Broker:** **Valkyrie** Multi-Factor Action Approval (MFAA) service binding hardware FIDO2/WebAuthn challenges to exact SHA-256 action hashes.
- **Desktop Packaging & Signing (Rail C):** Tauri v2 (`Idunn`), Minisign Ed25519 (`TAURI_SIGNING_PRIVATE_KEY` stored in 1Password `ravenmask` vault), and `latest.json` OTA manifests.
- **Admission & Registry Security:** Harbor Trivy scanning and Kubernetes admission policies blocking unsigned or quarantined digests.

### 4. Implementation Playbook

Tier 4 installs **Blast Radius Partitioning**, **Action-Hash Elevation (Valkyrie MFAA)**, and **Rail C Signed Desktop OTA**:

```text
                                 [ OPERATIONAL CHANGE ]
                                           │
                   ┌───────────────────────┴───────────────────────┐
                   ▼                                               ▼
    [ SURFACE 1: ROUTINE APP ]                      [ SURFACE 2: CONTROL PLANE ]
    Scope: App container images, Helm values        Scope: OpenBao, Keycloak, Harbor RBAC, CRDs
    Authority: Autonomous GitOps                    Authority: Action-Hash Elevation (Valkyrie MFAA)
    Tokens: Scoped service AppRole                  Tokens: Ephemeral, action-hash bound, single-use
                   │                                               │
                   ▼                                               ▼
         Argo CD Syncs Pod                                1. Runner generates read-only plan
                                                          2. Computes SHA-256 of exact plan payload
                                                          3. Human signs challenge via Valkyrie MFA
                                                          4. Single-use token executes & burns
```

#### Step 1: Partition the Blast Radius (Surface 1 vs. Surface 2)

Divide every mutation in the estate into two strict surfaces (**RP-12: Zero-Ambient Elevation**):
- **Surface 1: Routine Application Delivery (Autonomous / Low Blast Radius).** Container image digest bumps, application Helm values, and Homebrew tap updates flow automatically through GitOps using narrowly scoped service credentials (`control-runs-with-the-services-own-credential` - never an operator's personal PAT).
- **Surface 2: Control Plane, Identity & RBAC Mutations (Gated Elevation / High Blast Radius).** Changes to `OpenBao` policies, `Keycloak`/`Zitadel` realms, Harbor project permissions, cluster-wide CRDs/`PrometheusRules`, or production database roles cannot execute on ambient runner credentials.

#### Step 2: Strip Ambient Authority with OpenBao AppRoles

Remove static long-lived admin tokens from CI runner environments. Runners authenticate to `OpenBao` on `Norns` via scoped AppRoles that mint short-lived leases (15-minute TTL) restricted to the exact repository's Harbor path or read-only plan execution.

#### Step 3: Implement Action-Hash Elevation (Valkyrie MFAA)

For any Surface 2 control-plane mutation, enforce **Action-Hash Elevation (Valkyrie MFAA)**:

> *"Trust no agent or runner with ambient control-plane authority; elevate via Valkyrie, bound to the exact SHA-256 action hash, for a single execution."*

1. **Generate the Deterministic Plan:** The runner executes a read-only plan (for example, `terraform plan -out=tfplan.binary` or a canonical JSON mutation spec).
2. **Compute the Action Hash:** The runner hashes the exact plan bytes:

   ```bash
   ACTION_HASH=$(sha256sum tfplan.binary | awk '{print $1}')
   ```

3. **Request Valkyrie MFAA Challenge:** The runner posts `ACTION_HASH` and the human-readable diff summary to `Valkyrie`.
4. **Human Cryptographic Sign-Off:** The human Sovereign Gatekeeper inspects the diff and signs the challenge with a hardware FIDO2/WebAuthn token. Accountability chains directly to the human actor.
5. **Verify-Apply-Burn:** `Valkyrie` issues a single-use capability lease bound to `ACTION_HASH`. The apply step verifies that the plan on disk still hashes to `ACTION_HASH`, executes the mutation, and burns the lease immediately:

```json
{
  "elevation_challenge": {
    "target_plane": "openbao_norns_production_policies",
    "action_sha256": "4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a",
    "authorized_by": "nate@ravenhelm.dev",
    "mfa_method": "fido2_webauthn_hardware_token",
    "issued_at": "2026-11-04T10:15:30Z",
    "expires_at": "2026-11-04T10:20:30Z",
    "single_use_consumed": true
  }
}
```

If an agent or attacker alters a single byte of the plan after approval, the SHA-256 hash mismatches and `Valkyrie` rejects the execution cold.

#### Step 4: Implement Rail C Signed Desktop OTA (`Idunn` Reference)

For Tauri v2 desktop apps (`Idunn`), wire Ed25519 Minisign verification into the release promotion flow:
1. **Ingress Build (`:b<N>`):** Compiles the native `.app.tar.gz` and `.dmg` bundles once on merge to `main`.
2. **Promotion-Time Minisign:** On tag `vX.Y.Z`, the release workflow pulls the pre-built `:b<N>` bundle, retrieves `TAURI_SIGNING_PRIVATE_KEY` from 1Password (`ravenmask` vault), and signs the archive:

   ```bash
   minisign -Sm "Idunn_${VERSION}_aarch64.app.tar.gz" -s "$EPHEMERAL_KEY"
   ```

3. **Publish `latest.json`:** Uploads the detached signature and archive URL to `https://releases.ravenhelm.dev/idunn/latest.json`.
4. **Client Fail-Closed Verification:** `Idunn` verifies the Ed25519 signature against its compiled-in public key before unpacking or swapping `/Applications/Idunn.app`.

### 5. Governance & Verification Gates
- **Gate 4.1 (Action-Hash Binding):** A `Valkyrie` elevation token is mathematically invalid for any payload whose SHA-256 differs by a single bit from the signed plan.
- **Gate 4.2 (Service-Owned Credentials):** Daemons and schedulers (like `forgejo-runner-scheduler`) run solely with their own scoped robot/AppRole credentials, never a human operator's personal PAT (`frs #88`).
- **Gate 4.3 (Fail-Closed Client Signature Gate):** Unsigned or corrupted Rail C desktop bundles are unlinked before extraction.

### 6. Operational Guarantees Unlocked
- **Blast-Radius Containment:** A compromised build runner or rogue agent slice cannot escalate privileges into `OpenBao`, `Keycloak`, or cluster RBAC.
- **Non-Repudiable Human Accountability:** Every high-blast mutation carries a cryptographic receipt naming the human gatekeeper and the exact `action_sha256` approved.
- **Three-Rail Sovereign Custody:** Server pods on `Norns` (Rail A), Homebrew CLIs on MacBooks (Rail B), and desktop GUI apps on Rail C all ship from immutable `:b<N>` builds with cryptographic verification.

---

## The Migration Decision Matrix

| Capability Dimension | Tier 1: Artifact Discipline | Tier 2: Registry & Digest Locking | Tier 3: Multi-Rail Declarative GitOps | Tier 4: Sovereign Zero-Trust Delivery |
| :--- | :--- | :--- | :--- | :--- |
| **Target Scale** | 1-3 Engineers | 4-15 Engineers / Multi-Slice | 15-75 Engineers / Multi-Surface | 50+ Engineers / Sovereign Fleet |
| **Compilation Trigger** | On merge to `main` only | On merge to `main` only | On merge to `main` only | On merge to `main` only |
| **Release Mechanism** | Retagging existing `:b<N>` | `release-pr.sh` + API retag | `release-pr.sh` + Rail A/B lockstep | GitOps + Action-Hash Elevation |
| **Artifact Identity** | `:b<N>` sequential number | `:b<N>`, `:sha-<commit12>`, `:uat` | Triple tags + OCI Helm chart | Signed digest + Minisign OTA |
| **Manifest Pinning** | SemVer tag (`vX.Y.Z`) | Immutable `@sha256:` digest | Immutable `@sha256:` digest | Signed digest + Admission gate |
| **Deployment Authority** | Canonical Compose workflow | Canonical Compose / Helm | Argo CD (`norns-gitops` only) | Argo CD + Valkyrie MFAA |
| **Workstation Tooling** | Manual install | Manual tap update | Sandboxed Formula `inreplace` | Rail B Tap + Rail C Signed OTA |
| **Source Parity Gate** | Manual diff review | `check-release-source-parity.sh` | Source Parity + Artifact-Grep | Cryptographic commit + plan hash |
| **Runner Credentials** | Scoped repo secrets | Scoped Harbor robot tokens | Service-owned robot credentials | Ephemeral `OpenBao` AppRoles |
| **Rollback Capability** | Redeploy prior `:b<N>` (3 min) | Repoint `@sha256:` digest (1 min) | `git revert` in `norns-gitops` (<30s) | Instant GitOps revert + Quarantine |

---

## The Monday Morning Action Plan

Do not pause feature delivery for six months to build Tier 4 from scratch. Find your current tier on the bench and execute one concrete upgrade on Monday morning:

### If You Inhabit Tier 0 (Rebuilding on Tags or Auto-Rolling `:latest`)
- **Your Crime Scene:** Pushing `git tag v1.0.0` runs `docker build`, or a production container tracks `:latest` like `freyr-api` used to.
- **Your Monday Morning Step:** **Kill the tag compiler and ban `:latest` in prod.**
  1. Move `docker build` into `.forgejo/workflows/build.yml` triggered solely on `push: branches: [main]`.
  2. Stamp every trunk build with `:b${{ github.run_number }}`.
  3. Replace `docker build` in `release.yml` with a pure registry retag of the proven `:b<N>` image.

### If You Inhabit Tier 1 (Building Once, Deploying Mutable Tags)
- **Your Crime Scene:** You build once on `main`, but `values.yaml` or `docker-compose.yml` only specifies `image: service:v1.2.0` without an `@sha256:` pin, and nothing stops an engineer from editing `.rs` or `.ts` files on a release branch.
- **Your Monday Morning Step:** **Install Digest Locking and `check-release-source-parity.sh`.**
  1. Drop `scripts/harbor-artifact.sh`, `scripts/release-pr.sh`, `scripts/check-release-source-parity.sh`, and `scripts/check-release-tag.sh` into `scripts/` (or scaffold via **Project Factory**).
  2. Update `chart/templates/deployment.yaml` to render `{{ .Values.image.repository }}:{{ .Values.image.tag }}@{{ .Values.image.digest }}`.
  3. Require `check-release-source-parity.sh` to pass on every `release/*` PR.

### If You Inhabit Tier 2 (Digests Locked, Laptops Still Running `kubectl apply`)
- **Your Crime Scene:** Your digests are pinned, but engineers still run `helm upgrade` from local worktrees or leave `~/.local/bin` CLI shims out of sync with cluster pods.
- **Your Monday Morning Step:** **Hand the Gavel to `norns-gitops` and `nate/tools`.**
  1. Register the service as an Argo CD `Application` in `norns-gitops` with `selfHeal: true`.
  2. Stop running `kubectl apply` from workstations.
  3. For any repo with a Rust or Go CLI, add its formula to `nate/homebrew-tools` using sandboxed `inreplace` so `Cargo.toml` never has to be bumped in git.

### If You Inhabit Tier 3 (Multi-Rail GitOps Live, Ambient Credentials in CI)
- **Your Crime Scene:** Application releases flow cleanly through Argo CD, but CI runners or automation scripts hold long-lived admin tokens or personal PATs.
- **Your Monday Morning Step:** **Partition Blast Radiuses and Gate Surface 2 on Valkyrie MFAA.**
  1. Replace every personal PAT in automation with a dedicated service credential or `OpenBao` AppRole.
  2. Put Surface 2 mutations (`OpenBao` policies, `Keycloak`/`Zitadel` realms, cluster RBAC) behind **Action-Hash Elevation (Valkyrie MFAA)** so no plan applies without a human FIDO2 signature bound to its `sha256` digest.
  3. Wire Ed25519 Minisign verification into any Rail C desktop release workflow.

---

## Summary of Guarantees Across the Ladder

- **Tier 1** guarantees that **releases never rebuild code**.
- **Tier 2** guarantees that **deployed digests cannot be mutated and release PRs cannot smuggle source edits**.
- **Tier 3** guarantees that **Argo CD is the sole cluster authority and workstation CLIs stay locked to cluster backends**.
- **Tier 4** guarantees that **no runner holds ambient root authority and every control-plane mutation is bound to a human-signed action hash**.

Climb one rung at a time. Lock each ratchet behind you.

<!-- RUBRIC_CHECK: Chapter 8 conforms to RROM specification. -->

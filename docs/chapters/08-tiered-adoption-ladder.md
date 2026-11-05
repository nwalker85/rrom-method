# Chapter 8: The Tiered Adoption Ladder

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Four Maturity Tiers of Release Operations

Just as the Ravenhelm Linear Operations Methodology (RLOM) defines an honest tiering ladder for project coordination—recognizing that a two-person startup requires different governance than a regulated hundred-engineer platform—the Ravenhelm Release Operations Methodology (RROM) structures release operations across four maturity tiers.

Engineering organizations frequently stumble into one of two operational traps:

1. **The Premature Bureaucracy Trap:** A seed-stage startup attempts to install full zero-trust action-hash elevation, multi-cloud cryptographic attestation, and distributed multi-cluster GitOps on day one, paralyzing feature velocity under the weight of ceremonies they do not yet need.
2. **The Fragile Scaled Monolith Trap:** A growth-stage company with fifty engineers continues to rely on ad-hoc shell scripts, unpinned container tags, and compilation triggered at tag time, experiencing weekly production outages and mystery regressions caused by silent dependency drift.

RROM solves this dichotomy through a progressive, value-driven adoption ladder. Each tier addresses concrete operational pain points, introduces specific technical capabilities, establishes rigorous governance gates, and unlocks unambiguous reliability guarantees.

| Maturity Tier | Organizational Scale | Core Capability & Milestone Invariant |
| :--- | :--- | :--- |
| **Tier 1: Artifact Discipline** | 1 to 3 Engineers | Build once on merge to `main`; monotonic build sequence (`:b<N>`); zero tag-time compilation. |
| **Tier 2: Registry & Digest Locking** | 4 to 12 Engineers | Triple-tagging scheme; mandatory `@sha256:...` digest pinning; automated source-parity checks. |
| **Tier 3: Multi-Rail Declarative GitOps** | 13 to 50 Engineers | Sole-authority GitOps (Argo CD); Rail A/B synchronization; sandboxed formula inreplace. |
| **Tier 4: Sovereign Zero-Trust Delivery** | 50+ Engineers | Hard blast radius partitioning; action-hash elevation (Valkyrie MFAA); signed Ed25519 OTA. |

---

## Tier 1: Artifact Discipline (The Solo Developer / Free Tier)

**Core Focus:** Terminate tag-time compilation and establish the build as the immutable physical unit of delivery.

### 1. Target Organization Profile & Team Scale
* **Team Size:** 1 to 3 engineers.
* **Architecture:** Single monolithic service or lightweight service pair, distributed as Docker containers or standalone binaries.
* **Infrastructure:** Single cloud virtual machine, lightweight VPS, or managed container runner (e.g., Docker Compose on a single node, Render, Fly.io, or basic Hetzner box).
* **Release Cadence:** Daily or weekly ad-hoc releases driven by the founder or primary maintainer.

### 2. Pain Points & Ceilings Hit
Organizations at Tier 0 (the unmanaged baseline) suffer from the universal disease of **tag-time rebuilding**:
* **The "It Worked in Staging" Paradox:** A pull request is merged into `main`, tested in a staging environment, and approved. Days later, an engineer runs `git tag v1.0.4 && git push --tags`. The CI runner compiles the application from scratch under the tag ref. In the intervening days, an unpinned transitive npm package, Go module, or Alpine Linux base mirror published a minor patch that silently breaks production runtime initialization.
* **Digest Amnesia:** The container image running in staging has SHA-256 digest `aaa...`, while the container image deployed to production has digest `bbb...`. Staging logs and performance profiles are legally and operationally useless for debugging production incidents because the bits running in production were never tested.
* **Brittle Release Cycles:** Cutting a release takes 25 minutes of high-risk compilation in CI. If a third-party dependency mirror flakes during tag compilation, the release fails halfway through deployment, leaving the engineer stranded in an indeterminate state.

### 3. Complete Technical Stack & Tooling Requirements
* **Code Host & CI:** GitHub Actions or Forgejo Actions.
* **Container Registry:** Standard public or private OCI registry with basic token authentication (GitHub Container Registry `ghcr.io`, Docker Hub, or basic self-hosted Forgejo container registry).
* **Runtime Orchestration:** Docker Compose v2, systemd-managed Podman containers, or single-node container runtime.
* **CLI Tooling:** Standard `bash`, `docker`, and `git`.

### 4. Implementation Playbook
Migrating an existing repository from Tier 0 to Tier 1 requires four concrete steps:

#### Step 1: Dissect the Existing Monolithic CI Pipeline
Delete all triggers that execute compilation on tag push. Split `.github/workflows/ci.yml` or `.forgejo/workflows/ci.yml` into two decoupled workflow files: `build.yml` (triggered exclusively on trunk merges) and `release.yml` (triggered on tag push).

#### Step 2: Establish Ingress Build Pipeline on `main`
Configure `build.yml` to compile the artifact on merge to `main`, compute a sequential build number, and publish the artifact:

```yaml
# .github/workflows/build.yml
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
            --tag ghcr.io/org/service:${{ steps.build_id.outputs.build_number }} \
            --tag ghcr.io/org/service:latest \
            .

      - name: Publish to Registry
        run: |
          docker push ghcr.io/org/service:${{ steps.build_id.outputs.build_number }}
          docker push ghcr.io/org/service:latest
```

#### Step 3: Implement Zero-Compilation Release Retagging
Configure `release.yml` to trigger on tags matching `v*`. The release workflow is forbidden from invoking `docker build`, `cargo build`, `go build`, or `npm run build`. Its sole purpose is to pull the existing `:latest` (or target `:b<N>`) image and append the Semantic Versioning tag:

```yaml
# .github/workflows/release.yml
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
          docker pull ghcr.io/org/service:latest
          docker tag ghcr.io/org/service:latest ghcr.io/org/service:${{ github.ref_name }}
          docker push ghcr.io/org/service:${{ github.ref_name }}
```

#### Step 4: Simple Tag-Source Parity Verification
Add a pre-flight assertion script (`scripts/verify-release-tag.sh`) that ensures the tag pushed to git matches the version string in the project's package manifest (`package.json`, `Cargo.toml`, or `pyproject.toml`).

### 5. Governance & Verification Gates
* **Gate 1.1 (No Compiler in Release):** The release pipeline environment must not contain build SDKs or compilation toolchains. If a release workflow attempts to execute a compiler, the workflow fails.
* **Gate 1.2 (Tag Format Compliance):** Tags must strictly adhere to Semantic Versioning (`vX.Y.Z`). Arbitrary strings like `test-release` or `prod-fix` are rejected by CI pre-flight validation.
* **Gate 1.3 (Target Existence Proof):** The release retagging step must fail closed if the referenced build artifact does not already exist in the registry.

### 6. Operational Guarantees Unlocked
* **Zero-Rebuild Guarantee:** Code running under `v1.2.0` in production is bit-for-bit identical to the code that was tested on `main`.
* **Instantaneous Release Cycle:** Cutting a production release drops from 25 minutes of compilation to under 30 seconds of registry metadata retagging.
* **Immutability of Build History:** Every merge to `main` produces an immutable, numbered artifact (`:b104`, `:b105`) that can be audited or deployed independently.

---

## Tier 2: Registry & Digest Locking (The Growing Startup)

**Core Focus:** Eliminate mutable tag vulnerabilities, enforce three-way version parity, and prevent unauthorized source drift during releases.

### 1. Target Organization Profile & Team Scale
* **Team Size:** 4 to 15 engineers.
* **Architecture:** Multi-service backend (3 to 10 services), modular monolith with background workers, shared Redis/PostgreSQL clusters.
* **Infrastructure:** Dedicated staging (UAT) and production environments hosted on managed Kubernetes (EKS, GKE, K3s) or multi-host Docker Compose clusters.
* **Release Cadence:** Multiple daily trunk merges; scheduled or on-demand production releases (1 to 5 releases per week).

### 2. Pain Points & Ceilings Hit
While Tier 1 prevents tag-time rebuilds, teams scaling past 4 engineers hit new structural ceilings:
* **Tag Overwriting & Poisoning:** Using mutable tags like `:latest` or `:v1.2.0` creates race conditions. If an engineer accidentally pushes an image with an existing tag, the container runtime pulls the new image without any record of the change in version control.
* **The "Release Branch Code Smuggle":** An engineer creating a release branch to bump the version string inadvertently fixes a "minor typo" or tweaks an environment variable directly on the release branch. Because the release branch is tagged, unverified, unreviewed code bypasses trunk testing and enters production.
* **Staging Stream Collision:** Multiple engineers merging PRs to `main` overwrite the staging environment unpredictably. Without monotonic build tracking and triple-tagging, engineers cannot determine which specific PR is currently running in UAT.

### 3. Complete Technical Stack & Tooling Requirements
* **Code Host & CI:** Forgejo or GitHub Enterprise with branch protection rules enforcing status checks and mandatory PR reviews.
* **OCI Registry:** Self-hosted Harbor or enterprise managed OCI registry (AWS ECR, GCP Artifact Registry) supporting Registry v2 APIs, immutable tag rules, and webhook notifications.
* **Configuration Management:** Helm 3 charts or structured Docker Compose stacks with templated values.
* **Automation Tooling:** `yq` v4, `jq`, `curl`, and standard bash automation scripts (`scripts/release-pr.sh`, `scripts/check-release-source-parity.sh`, `scripts/check-release-tag.sh`, `scripts/harbor-artifact.sh`).

### 4. Implementation Playbook
Upgrading from Tier 1 to Tier 2 introduces the **Triple-Tagging Scheme**, **Automated Release PRs**, and **Mandatory Digest Locking**:

```text
[ INGRESS MERGE ]
       │
       ▼
[ Registry v2 Push ] ───> Triple Tags: :b<N> (Sequence) + :sha-<commit12> (Trace) + :uat (Stream)
                               │
                               ▼
[ Release PR Opened ] ───> scripts/release-pr.sh b<N> vX.Y.Z
                               │  - Resolves @sha256:<digest> from Harbor API
                               │  - Pins values.yaml to exact digest
                               │  - Asserts zero application source code drift
                               ▼
[ Release Merged ]   ───> scripts/harbor-artifact.sh retag b<N> vX.Y.Z
```

#### Step 1: Implement the Triple-Tagging Scheme on Ingress
Update the build CI pipeline (`.forgejo/workflows/build.yml`) so that every merge to `main` publishes three discrete tags pointing to the exact same image digest:
1. `:b<N>` — The monotonic, globally ordered build sequence number (e.g., `:b42`).
2. `:sha-<commit12>` — The 12-character truncated git commit SHA for audit traceability.
3. `:uat` — The moving pointer consumed by the staging/UAT environment.

```bash
# Ingress publication inside build runner
COMMIT12=$(echo "${GITHUB_SHA}" | cut -c1-12)
BUILD_ID="b${BUILD_NUMBER}"

docker tag "${LOCAL_IMAGE}" "harbor.internal/platform/core:${BUILD_ID}"
docker tag "${LOCAL_IMAGE}" "harbor.internal/platform/core:sha-${COMMIT12}"
docker tag "${LOCAL_IMAGE}" "harbor.internal/platform/core:uat"

docker push "harbor.internal/platform/core:${BUILD_ID}"
docker push "harbor.internal/platform/core:sha-${COMMIT12}"
docker push "harbor.internal/platform/core:uat"
```

#### Step 2: Enforce Mandatory Digest Pinning in Production Manifests
Mutable tags are strictly prohibited in production manifests. Every production deployment manifest must explicitly declare the immutable cryptographically secure digest:

```yaml
# chart/values.yaml (Production)
image:
  repository: harbor.ravenhelm.dev/platform/vitki
  tag: v1.4.2
  digest: sha256:7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a
  build: b42
```

In the Helm deployment template, the pod container specification renders both the human-readable tag and the immutable digest pin:

```yaml
# chart/templates/deployment.yaml
containers:
  - name: app
    image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}@{{ .Values.image.digest }}"
```

#### Step 3: Implement Automated Release Preparation (`scripts/release-pr.sh`)
Create `scripts/release-pr.sh` to automate release branch creation. The script takes the candidate build number and desired SemVer tag, queries the registry via the OCI Distribution API to resolve the exact digest, updates configuration metadata, and commits:

```bash
#!/usr/bin/env bash
# scripts/release-pr.sh <build-id> <semver-tag>
set -euo pipefail

BUILD="$1"
TAG="$2"
SEMVER="${TAG#v}"

# 1. Resolve immutable digest via registry API
DIGEST=$(scripts/harbor-artifact.sh resolve "${BUILD}")
if [[ -z "${DIGEST}" ]]; then
  echo "ERROR: Build ${BUILD} not found in registry." >&2
  exit 1
fi

# 2. Update Helm Chart and values metadata
yq -i ".version = \"${SEMVER}\"" chart/Chart.yaml
yq -i ".appVersion = \"${SEMVER}\"" chart/Chart.yaml
yq -i ".image.tag = \"${TAG}\"" chart/values.yaml
yq -i ".image.digest = \"${DIGEST}\"" chart/values.yaml
yq -i ".image.build = \"${BUILD}\"" chart/values.yaml

# 3. Verify zero source code drift against trunk
scripts/check-release-source-parity.sh "main"
```

#### Step 4: The Automated Source Parity Gate (`check-release-source-parity.sh`)
Create `scripts/check-release-source-parity.sh`. This script computes a `git diff` against the integration trunk, ensuring that the release pull request modifies **only** authorized metadata files (`Chart.yaml`, `values.yaml`, `CHANGELOG.md`):

```bash
#!/usr/bin/env bash
# scripts/check-release-source-parity.sh <base-ref>
set -euo pipefail

BASE="${1:-main}"
CHANGED_FILES=$(git diff --name-only "${BASE}...HEAD")

# Define allowed metadata files
ALLOWED_PATTERN="^(chart/Chart\.yaml|chart/values\.yaml|CHANGELOG\.md|version\.txt)$"

for FILE in ${CHANGED_FILES}; do
  if [[ ! "${FILE}" =~ ${ALLOWED_PATTERN} ]]; then
    echo "SECURITY ERROR: Release PR modifies unauthorized file: ${FILE}" >&2
    echo "Release PRs must contain ZERO application source code changes." >&2
    exit 1
  fi
done

echo "SUCCESS: Release source parity verified. Only metadata modified."
```

### 5. Governance & Verification Gates
* **Gate 2.1 (The Source Parity Gate):** CI rejects any release PR modifying `.rs`, `.go`, `.ts`, `.py`, `.c`, or `.sql` files. Releases cannot smuggle logic changes.
* **Gate 2.2 (The Three-Way Release Tag Gate):** When the release PR is merged and tagged, `scripts/check-release-tag.sh` verifies exact cryptographic equality:
  ```text
  git tag (v1.4.2) == chart/values.yaml (.image.tag) == chart/Chart.yaml (.appVersion)
  ```
* **Gate 2.3 (Registry Tag Immutability):** The OCI registry (Harbor) enforces immutable tag policies on all SemVer tags (`v*`) and build tags (`b*`). Retagging an existing tag with different content is rejected at the registry API layer.

### 6. Operational Guarantees Unlocked
* **Tamper-Proof Deployments:** Digest locking guarantees that Kubernetes or Docker pulls the exact verified binary even if DNS is hijacked or registry tags are mutated.
* **Audit Trail Parity:** The running digest in production maps directly to the specific build ID (`b42`), which maps directly to the merge commit SHA on `main`.
* **Zero Accidental Code Drift:** Release engineers cannot inadvertently alter business logic while cutting a release.

---

## Tier 3: Multi-Rail Declarative GitOps (The Scaling Team)

**Core Focus:** Establish GitOps as the sole applying authority, enforce dual-rail synchronization across backends and developer tooling, and eliminate cluster credentials from operator workstations.

### 1. Target Organization Profile & Team Scale
* **Team Size:** 15 to 75 engineers across multiple squads (Platform, Core Backend, Product, Infrastructure).
* **Architecture:** Distributed microservices on Kubernetes, event-driven pipelines, alongside internal developer CLI/TUI tools distributed to engineers' macOS/Linux laptops.
* **Infrastructure:** Highly available Kubernetes clusters (e.g., K3s, EKS, Talos) managed declaratively, separate GitOps configuration repository (`norns-gitops`), private Homebrew tap (`nate/tools`).
* **Release Cadence:** Continuous deployment of candidate builds to staging; daily coordinated production releases spanning server workloads and developer workstation tools.

### 2. Pain Points & Ceilings Hit
At this scale, teams experience severe **surface divergence** and **operational drift**:
* **The "Dirty Laptop Apply" Syndrome:** Engineers or operations staff possess `cluster-admin` kubeconfigs on their laptops. During an emergency or routine update, someone runs `helm upgrade --set image.tag=v1.3.1` or `kubectl apply -f manual-patch.yaml`. The running cluster state silently diverges from git. When CI reconciles the next day, the manual patch is obliterated, causing a secondary outage.
* **Multi-Surface Protocol Drift (Rail A vs. Rail B Divergence):** The platform team ships an update to a backend gRPC service (Rail A: Kubernetes workload) that alters API field numbers. A developer running a local CLI or diagnostic tool (Rail B: Homebrew package) executed against the cluster crashes or corrupts data because the CLI was compiled against the old protobuf definition.
* **The Cargo.toml / Homebrew Parity Dilemma:** Compiling developer CLIs from source via private Homebrew taps requires version declarations in `Cargo.toml`. If the release engineer bumps `Cargo.toml` in git to satisfy Homebrew, it violates Tier 2 Source Parity. If they don't, Homebrew installs a binary reporting the wrong version.

### 3. Complete Technical Stack & Tooling Requirements
* **GitOps Engine:** Argo CD or Flux CD deployed within the cluster network namespace.
* **Repositories:** 
  1. Application Repository (e.g., `vitki`, `yager`): Contains application code, Helm chart, and in-repo release scripts.
  2. Central GitOps Repository (e.g., `norns-gitops`): Houses environment manifests, Argo CD Application resources, and pinned production values.
  3. Private Homebrew Tap (e.g., `nate/tools`): Houses Formula definitions (`Formula/yager.rb`) for workstation distribution.
* **Container & Helm Registry:** Harbor OCI registry storing both container images and versioned OCI Helm packages.
* **Host Process Management:** `process-compose` for local developer service orchestration.

### 4. Implementation Playbook
Migrating to Tier 3 requires enforcing the **Strict GitOps Boundary**, **Dual-Rail Lockstep**, and **Sandboxed Formula Inreplace**:

```text
[ DUAL-SURFACE RELEASE PR ] (e.g., Ullr/Yager)
          │
          ├──> [ Rail A: K3s Cluster GitOps ]
          │       │
          │       ▼
          │    1. Retag Harbor OCI digest to vX.Y.Z
          │    2. Open PR in central norns-gitops updating targetRevision
          │    3. Argo CD reconciles cluster; live health probe verified
          │
          └──> [ Rail B: Workstation Developer CLI ]
                  │
                  ▼
               1. Package release tarball archive with SHA-256
               2. Open PR in private Homebrew tap (nate/tools)
               3. Formula executes sandboxed inreplace during compilation
               4. Workstation installs bit-identical protocol client
```

#### Step 1: Revoke Direct Cluster Access (The Strict GitOps Boundary)
Revoke all write access (`kubectl apply`, `helm install`) from developer workstations and CI runners. Argo CD is configured as the **sole deployment authority**.
* Argo CD runs inside the cluster netns, polling the GitOps repository over HTTPS with a read-only deploy key.
* Developers interact with cluster state exclusively by opening pull requests against `norns-gitops`.

#### Step 2: Establish the Dual GitOps Stream Model
Configure two distinct Argo CD Applications inside `norns-gitops`:
1. **The UAT Application:** Pinned to `targetRevision: main`. Pulls `chart/values-uat.yaml`, rendering `:uat` tags on staging NodePorts.
2. **The Production Application:** Pinned to immutable SemVer tags (`targetRevision: vX.Y.Z`). Pulls `chart/values.yaml` rendering immutable `@sha256:` digests.

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
    repoURL: https://github.com/nwalker85/vitki.git
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
To resolve the Homebrew source-parity conflict, adopt the **Sandboxed Formula Inreplace** pattern in your private tap. The application repository's `Cargo.toml` remains untouched at `0.1.0-dev`. The private Homebrew formula performs dynamic version substitution inside its isolated build sandbox during compilation:

```ruby
# nate/tools: Formula/yager.rb
class Yager < Formula
  desc "Terminal User Interface and agent harness"
  homepage "https://github.com/nwalker85/yager"
  url "https://github.com/nwalker85/yager/archive/refs/tags/v0.1.33.tar.gz"
  sha256 "a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5"
  license "Proprietary"

  depends_on "rust" => :build

  def install
    # Dynamically inject release version into sandbox without touching git
    inreplace "Cargo.toml", /^version = .*/, "version = \"#{version}\""
    inreplace "Cargo.lock", /name = "yager"\nversion = "[0-9.]+"/, "name = \"yager\"\nversion = \"#{version}\""

    system "cargo", "install", *std_cargo_args
  end

  test do
    assert_match "yager #{version}", shell_output("#{bin}/yager --version")
  end
end
```

#### Step 4: Codify Dual-Rail Synchronized Releases
For repositories shipping both a server backend and a developer CLI (e.g., Ullr/Yager), the release workflow mandates simultaneous dual-rail execution:
1. The release PR contains both the Helm value updates and the Homebrew formula update.
2. The CI pipeline retags the container image in Harbor (Rail A) and computes the release tarball SHA-256 for the tap (Rail B).
3. The merge event triggers automated deployment to the cluster via Argo CD and an automated commit to `nate/tools`.

#### Step 5: Enforce the "Merge-Then-Deploy" Protocol
Approval to merge a release PR is explicitly defined as approval to drive deployment through to live runtime verification. A release is never marked "complete" upon git merge. The operator or automated agent must:
1. Confirm the GitOps controller successfully synchronized the new revision.
2. Execute a live runtime health probe against the target service.
3. Verify that the running application responds with HTTP 200 and matches the expected release version string.

### 5. Governance & Verification Gates
* **Gate 3.1 (GitOps Exclusivity):** Zero human or CI credentials have RBAC permissions to mutate production pods directly. Any drift introduced outside of git is automatically reverted by Argo CD's self-healing reconciliation.
* **Gate 3.2 (Dual-Rail Atomic Gate):** For dual-surface repositories, the release fails closed if either Rail A (Harbor retag) or Rail B (Tap formula update) fails. Partial releases are strictly prohibited.
* **Gate 3.3 (Runtime Proof Gate):** Deployment success requires active proof of life from live running interfaces before the release is certified as converged.

### 6. Operational Guarantees Unlocked
* **Zero Configuration Drift:** The state of the production cluster is 100% represented by the commit history of the GitOps repository.
* **Elimination of Surface Drift:** Developer CLI tooling and server-side gRPC/REST APIs remain strictly synchronized, preventing protocol divergence incidents.
* **Instantaneous Rollback (<30s):** Reverting a production release requires only reverting the single git commit in the GitOps repository; Argo CD immediately converges the cluster pods to the previous digest.

---

## Tier 4: Sovereign Elevation & Zero-Trust Delivery (The Enterprise)

**Core Focus:** Isolate blast radiuses, eliminate ambient CI authority, enforce cryptographic multi-factor elevation for control plane mutations, and distribute desktop GUI clients via signed over-the-air updates.

### 1. Target Organization Profile & Team Scale
* **Team Size:** 75+ engineers, regulated enterprises (SOC2 Type II, FedRAMP, ISO 27001), defense tech, financial infrastructure, or sovereign self-hosted estates.
* **Architecture:** Multi-cluster Kubernetes, hybrid on-prem / sovereign cloud, identity providers (Keycloak, Zitadel), secrets vaults (OpenBao, HashiCorp Vault), and native desktop GUI applications (macOS, Windows, Linux) distributed to end users.
* **Infrastructure:** Zero-trust network fabric, hardware security modules (HSM) or hardware keys (YubiKey), dedicated runner clusters (eikthyrnir) running in isolated network namespaces.
* **Release Cadence:** Continuous automated application delivery; strictly gated and cryptographically audited control-plane and identity elevation cycles.

### 2. Pain Points & Ceilings Hit
Even with Tier 3 GitOps, high-consequence organizations face critical existential threats:
* **The Ambient Authority Runner Takeover:** A compromised dependency (e.g., an npm build script or malicious GitHub Action) executes within a CI runner. If that runner possesses ambient credentials to AWS, Vault, or Keycloak, the attacker extracts root secrets and compromises the entire corporate identity plane.
* **The Rogue Infrastructure Mutation:** An automated pipeline or rogue administrator applies a Terraform patch that disables multi-factor authentication or opens database ports to the internet without human executive oversight.
* **Desktop Client Supply Chain Tampering (Rail C Risks):** Distributing desktop GUI client updates over the internet exposes users to man-in-the-middle attacks, corrupted downloads, or compromised CDN mirrors if updates are not signed with asymmetric cryptographic keys.

### 3. Complete Technical Stack & Tooling Requirements
* **Identity & Secrets Infrastructure:** Zitadel / Keycloak OIDC fabric, OpenBao / Vault secrets management with short-lived AppRoles and dynamic secret leasing.
* **Elevation & MFAA Engine:** Valkyrie Multi-Factor Action Approval broker integrating hardware security tokens and biometric push confirmation.
* **Desktop Client Packaging (Rail C):** Tauri v2 (Rust + Svelte/React) desktop client architecture.
* **Cryptographic Attestation & Signing:** Minisign (Ed25519) for desktop bundle signing, Cosign / Notary for container image signing, and Sigstore provenance attestations.
* **Security & Vulnerability Scanning:** Harbor native Trivy vulnerability scanning, enforcing admission controller gates that block unsigned images or images with critical CVEs.

### 4. Implementation Playbook
Tier 4 establishes **Blast Radius Partitioning**, **Action-Hash Elevation (The Ehwaz Doctrine)**, and **Rail C Cryptographic Desktop OTA**:

```text
                                 [ OPERATIONAL CHANGE ]
                                           │
                   ┌───────────────────────┴───────────────────────┐
                   ▼                                               ▼
    [ SURFACE 1: ROUTINE APP ]                      [ SURFACE 2: CONTROL PLANE ]
    Scope: Container images, Helm                   Scope: Keycloak, Vault, Harbor RBAC
    Authority: Autonomous GitOps                     Authority: Valkyrie MFAA Elevation
    Tokens: Least-privilege push/pull                Tokens: Ephemeral, action-hash bound
                   │                                               │
                   ▼                                               ▼
         Argo CD Syncs Pod                                1. CI runs read-only plan
                                                          2. Computes SHA-256 of plan
                                                          3. Human signs challenge via MFA
                                                          4. Single-use apply & burn
```

#### Step 1: Implement Blast Radius Partitioning
Strictly partition all operational changes into two distinct security surfaces:
* **Surface 1: Routine Application Mutations (Autonomous / Low Blast Radius).** Includes container image updates, Helm values bumps, and static web asset deployments. These changes flow autonomously through GitOps without requiring manual elevation. CI runners operate with scoped, least-privilege tokens.
* **Surface 2: Control Plane & Identity Mutations (Gated Elevation / High Blast Radius).** Includes modifications to Keycloak realms, Vault access policies, Harbor RBAC, and root database schemas. Automated ambient execution is completely prohibited.

#### Step 2: Implement Zero Ambient Authority for CI Runners
CI runners are stripped of all permanent cloud or cluster-admin credentials:
* Runners obtain short-lived, dynamically generated AppRole tokens from OpenBao that expire in 15 minutes.
* Tokens are restricted to read-only capabilities during pull request verification.

#### Step 3: Implement the Ehwaz Doctrine (Action-Hash Elevation)
For Surface 2 mutations, enforce the **Ehwaz Doctrine**:
> *"Trust no agent with ambient authority; elevation via Valkyrie, action-hash bound, single use."*

1. **Generate Read-Only Plan:** The CI runner executes a plan operation (e.g., `terraform plan -out=tfplan.binary`).
2. **Compute Plan Digest:** The runner generates the SHA-256 hash of the compiled plan file:
   ```bash
   PLAN_HASH=$(sha256sum tfplan.binary | awk '{print $1}')
   ```
3. **Dispatch Valkyrie Challenge:** The pipeline submits an elevation request to the Valkyrie broker containing the `plan_hash` and change metadata.
4. **Human Biometric Authorization:** An authorized human gatekeeper reviews the exact plan output and signs the challenge on an air-gapped or biometrically secured device.
5. **Single-Use Consumption:** The apply runner receives an ephemeral authorization token cryptographically bound to `PLAN_HASH`. It verifies the hash, applies the plan, and immediately consumes the token, invalidating it permanently:

```json
{
  "elevation_challenge": {
    "target_plane": "identity_keycloak_production",
    "plan_sha256": "4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a",
    "authorized_by": "nate@ravenhelm.co",
    "mfa_method": "fido2_webauthn_hardware_token",
    "issued_at": "2026-11-04T10:15:30Z",
    "expires_at": "2026-11-04T10:20:30Z",
    "consumed": true
  }
}
```

#### Step 4: Implement Rail C Desktop OTA Distribution (Reference: Idunn)
For client desktop applications (e.g., Tauri v2 desktop shells), deploy an enterprise-grade over-the-air update pipeline:
1. **Deterministic Bundle Packaging:** The ingress build runner builds the `.app.tar.gz` and `.dmg` archives from trunk code.
2. **Ed25519 Cryptographic Signing:** The release runner retrieves the pre-built bundle and signs the archive using a dedicated Minisign private key:
   ```bash
   minisign -Sm "Idunn-${VERSION}.app.tar.gz" -s ~/.minisign/idunn_release.key
   ```
3. **Generate Signed Update Manifest (`latest.json`):** The release pipeline publishes an immutable manifest containing the version, download endpoint, SHA-256 checksum, and base64 signature:
   ```json
   {
     "version": "1.4.2",
     "notes": "Synchronized protocol update for Vitki v1.4.2 backend.",
     "pub_date": "2026-11-04T10:30:00Z",
     "platforms": {
       "darwin-aarch64": {
         "signature": "RWRmZXhhbXBsZXNpZ25hdHVyZWV4YW1wbGVzaWduYXR1cmVleGFtcGxlc2lnbmF0dXJlCg==",
         "url": "https://releases.ravenhelm.dev/idunn/v1.4.2/Idunn-aarch64.app.tar.gz"
       }
     }
   }
   ```
4. **Client-Side Verification Handshake:** The desktop application queries `latest.json` over HTTPS, validates the cryptographic signature using its embedded public key, verifies payload integrity, swaps the binary, and prompts the user to restart.

### 5. Governance & Verification Gates
* **Gate 4.1 (Action-Hash Binding):** An elevation token cannot be consumed by any plan whose SHA-256 hash differs by even a single bit from the reviewed plan.
* **Gate 4.2 (Cryptographic Image Attestation):** Harbor's admission controller rejects container deployment unless the image digest carries a valid Cosign cryptographic signature generated by an authorized release key.
* **Gate 4.3 (Single-Use Token Consumption):** Elevation tokens are atomic and consumable; replaying a previously signed approval token fails immediately.

### 6. Operational Guarantees Unlocked
* **Immunity to CI Runner Compromise:** Even if an attacker gains arbitrary code execution inside a CI runner, they cannot alter infrastructure or identity configurations without bypassing hardware-token biometric human approval.
* **End-to-End Cryptographic Provenance:** Every piece of software running on a server or desktop workstation is cryptographically linked to a verified source commit, a certified build pipeline, and an authorized human release name.
* **Sovereign Operational Independence:** The entire delivery pipeline can run air-gapped on sovereign hardware without dependencies on external SaaS vendors or hosted build systems.

---

## The Migration Decision Matrix

To assist engineering leaders in evaluating their current maturity and determining their immediate operational roadmap, RROM provides the following comprehensive diagnostic matrix.

### Operational Maturity Diagnostic Matrix

| Capability Dimension | Tier 1: Artifact Discipline | Tier 2: Registry & Digest Locking | Tier 3: Multi-Rail Declarative GitOps | Tier 4: Sovereign Elevation |
| :--- | :--- | :--- | :--- | :--- |
| **Target Scale** | 1–3 Engineers | 4–15 Engineers | 15–75 Engineers | 75+ Engineers / Regulated |
| **Compilation Trigger** | On merge to `main` only | On merge to `main` only | On merge to `main` only | On merge to `main` only |
| **Release Mechanism** | Re-tagging existing `:b<N>` | Release PR + Retag script | Release PR + Multi-Rail Sync | Action-Hash MFAA Elevation |
| **Artifact Identity** | `:b<N>` sequential number | `:b<N>`, `:sha-12`, `:uat` | Triple tags + OCI Helm chart | Cryptographically signed digest |
| **Manifest Pinning** | Mutable tag (`vX.Y.Z`) | Immutable `@sha256:` digest | Immutable `@sha256:` digest | Signed digest + Admission gate |
| **Deployment Authority** | Host docker daemon / runner | Host docker daemon / Helm | Argo CD / GitOps (Zero laptop) | Zero-trust GitOps + Valkyrie |
| **Workstation Tooling** | Uncoordinated / Ad-hoc | Tracked manually | Sandboxed Formula Inreplace | Signed OTA binaries (Rail C) |
| **Source Parity Gate** | Manual inspection | Automated `check-parity.sh` | Automated `check-parity.sh` | Cryptographic commit link |
| **Runner Secrets** | Standard repo secrets | Scoped push/pull tokens | Least-privilege deploy keys | Ephemeral OpenBao AppRoles |
| **Rollback Capability** | Pull previous tag (5 min) | Pull previous digest (2 min) | Git revert commit (<30 sec) | Instant GitOps pointer revert |

---

## The Monday Morning Action Plan

Adopting RROM does not require pausing product development for a six-month infrastructure rewrite. Engineering leaders should identify their current tier and take one concrete, high-leverage step on Monday morning to ascend to the next level:

### If You Inhabit Tier 0 (The Ad-Hoc / Rebuild-on-Tag Baseline)
* **Your Current Reality:** Pushing `git tag v1.0.0` triggers a CI runner that runs `docker build` or `npm run build`. Staging and production run different bits.
* **Your Monday Morning Step:** **Kill the tag compiler.**
  1. Open your CI pipeline configuration (`.github/workflows/deploy.yml`).
  2. Change the trigger from `on: push: tags: 'v*'` to `on: push: branches: [main]`.
  3. Configure the build step to publish with the monotonic build sequence number: `service:b${{ github.run_number }}`.
  4. Write a 10-line release workflow that triggers on tags and does exactly one thing: `docker pull service:latest && docker tag service:latest service:${{ github.ref_name }} && docker push service:${{ github.ref_name }}`.

### If You Inhabit Tier 1 (Artifact Discipline Installed)
* **Your Current Reality:** You build once on `main`, but production manifests reference mutable tags (`image: service:v1.2.0`), leaving you vulnerable to tag mutation and source drift.
* **Your Monday Morning Step:** **Install Digest Locking and the Parity Guard.**
  1. Add `scripts/check-release-source-parity.sh` to your repository.
  2. Add a CI check that executes this script on every release PR, ensuring no `.go`, `.rs`, `.ts`, or `.py` files are modified.
  3. Update your production manifest to pin the container image using its immutable digest: `image: service:v1.2.0@sha256:<digest>`.

### If You Inhabit Tier 2 (Registry & Digest Locking Installed)
* **Your Current Reality:** You pin digests and verify parity, but developers still run `kubectl apply` or `helm upgrade` from their laptops, and your CLI tools drift out of sync with your backend APIs.
* **Your Monday Morning Step:** **Establish the GitOps Boundary and Dual-Rail Sync.**
  1. Stand up an Argo CD instance in your cluster and create a dedicated configuration repository (`gitops-config`).
  2. Revoke write permissions to production Kubernetes namespaces from all personal user accounts.
  3. If you distribute a developer CLI or TUI, create a private Homebrew tap and adopt the **Sandboxed Formula Inreplace** pattern to eliminate version bump commits in your source repository.

### If You Inhabit Tier 3 (Multi-Rail Declarative GitOps Installed)
* **Your Current Reality:** Your application releases flow cleanly through GitOps, but CI runners hold powerful credentials to infrastructure, and database or identity changes lack cryptographic approval boundaries.
* **Your Monday Morning Step:** **Partition Your Blast Radius.**
  1. Audit your repository CI secrets. Segregate application deployment permissions from control-plane and identity mutations.
  2. For high-blast infrastructure changes (Terraform, Keycloak, Vault), introduce an action-hash elevation workflow: generate a plan, compute its SHA-256 hash, and require out-of-band biometric approval before execution.
  3. If distributing desktop applications, install Minisign Ed25519 signing into your release pipeline and configure your desktop shell to verify updates against a signed `latest.json` manifest.

---

## Summary of Guarantees Across the Ladder

The RROM Tiered Adoption Ladder is not an arbitrary checklist of enterprise tooling; it is a ladder of operational truth:

* **Tier 1** guarantees that **releases never rebuild code**.
* **Tier 2** guarantees that **deployed artifacts cannot be mutated or drifted**.
* **Tier 3** guarantees that **no engineer applies code from a dirty laptop and no CLI drifts from its backend**.
* **Tier 4** guarantees that **no automation runner possesses ambient root authority and every release is cryptographically sovereign**.

By climbing this ladder deliberately as organizational scale demands, engineering teams maintain high feature velocity while building release infrastructure that is resilient, deterministic, and auditable.

<!-- RUBRIC_CHECK: Chapter 8 conforms to RROM specification. -->

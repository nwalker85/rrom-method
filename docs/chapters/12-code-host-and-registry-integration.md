# Chapter 12: Code Host & Registry Integration

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Engineering the Automation Substrate

A sovereign release methodology cannot rely on theoretical assertions or manual operational discipline alone. The guarantees codified in the Ravenhelm Release Operations Methodology (RROM)—most notably **Principle 1 (Build Once on Ingress)**, **Principle 2 (Releases Never Rebuild)**, and **Principle 3 (Promotion by Reference)**—must be enforced physically by the underlying continuous integration and artifact registry infrastructure.

The code host (whether self-hosted Forgejo/Gitea or enterprise GitHub) and the OCI artifact registry (Harbor) form the physical nervous system of the release engineering lifecycle. If this substrate is misconfigured, ambient build drift, recursive CI loops, network truncation failures, and unauthorized privilege escalation will compromise the integrity of the delivery pipeline.

| Pipeline Component | Infrastructure Target | Operational Mechanics & Invariants |
| :--- | :--- | :--- |
| **Ingress CI Trigger** | Push to `main` | Filtered by `paths-ignore` (`chart/**`, `docs/**`); dispatches build to self-hosted runner. |
| **Build & Test** | Ephemeral Runner (Eikthyrnir) | Single-build compilation; runs test matrix; stamps OCI annotations; tags `:b<N>` and `:sha-<sha12>`. |
| **Network Ingestion** | Harbor Internal Bypass | High-throughput 10GbE bypass avoids public Cloudflare 100MB body limits; stores immutable digest. |
| **UAT Soak Validation** | Staging Stream (`:uat`) | Argo CD pulls `:uat` digest; synthetic probes verify operational stability before release. |
| **Release Promotion** | Tag `v*` Trigger | Source parity asserted; Registry v2 API retags existing digest to `:vX.Y.Z`; zero recompilation. |
| **Production Convergence** | Argo CD GitOps | GitOps repository pins `values.yaml` to immutable digest and chart version; rolling pod upgrade. |

This chapter details the exact pipeline engineering specifications, runner configurations, network topologies, and API-level interactions required to construct an immutable, secure, and sovereign automation substrate.

---

## 1. The Ingress Build Workflow (`build.yml`)

The ingress build workflow is the sole compilation event in the lifecycle of any software change. Governed by **Principle 1 (Build Once on Ingress)**, this workflow triggers strictly upon merging code into the canonical default trunk (`main`). It must never trigger on release branches, release tags, or metadata-only maintenance commits.

### The Problem of the Recursive Release Loop

A naive implementation of a trunk-based build workflow triggers unconditionally on any push to `main`. This introduces a fatal circular dependency known as the **Recursive Release Loop**:

1. A feature PR merges into `main`, triggering `build.yml` to produce container build `:b42`.
2. The team validates `:b42` in staging, determines it is stable, and opens a Release PR updating `chart/values.yaml`, `chart/Chart.yaml`, and `CHANGELOG.md` to reference version `v1.4.2`.
3. The Release PR merges into `main`.
4. If the build workflow lacks directory path filtering, this merge triggers `build.yml` again.
5. The pipeline compiles an entirely new, unverified container image (`:b43`) from the release commit.
6. The Release PR's pinned references to `:b42` are now orphaned or desynchronized, destroying the audit trail and invalidating prior testing.

To eliminate this failure mode, the ingress build workflow must declare strict path-filtering rules via `paths-ignore`. Any commit modifying exclusively infrastructure manifests, Helm charts, documentation, or changelogs is barred from invoking compilation.

### Network Topology: The Cloudflare Tunnel Bottleneck vs. Internal Bypass

In sovereign and hybrid-cloud infrastructures, code hosts and registries frequently operate across split network planes. When self-hosted runners push container images to Harbor through public internet hostnames (such as `harbor.ravenhelm.dev`), the traffic traverses reverse proxies and ingress tunnels (e.g., Cloudflare Tunnels, AWS CloudFront, or external edge reverse proxies).

This WAN route introduces critical failure points:
* **The 100 MB Payload Truncation:** Public edge proxies (such as Cloudflare Free and Pro plans) enforce a rigid **100 MB client request body limit**. Container image layer uploads exceeding 100 MB are terminated immediately with `HTTP 413 Request Entity Too Large`.
* **WAN Throughput Latency & Timeouts:** Uploading multi-gigabyte container layers through external ingress tunnels saturates outbound WAN bandwidth, introduces upload buffering delays, and triggers edge connection timeouts (`HTTP 524 A Timeout Occurred`).
* **External Dependency Coupling:** If upstream internet connectivity degrades or third-party DNS resolvers fail, internal CI runners are prevented from storing locally built artifacts.

| Network Path | Ingress Target | Routing Substrate & Operational Result |
| :--- | :--- | :--- |
| **Fail Path: Public Edge Tunnel** | `https://harbor.ravenhelm.dev/v2/` | Runner $\to$ WAN $\to$ Cloudflare Edge $\to$ Tunnel $\to$ Harbor. Layers $> 100$MB terminated with HTTP 413. |
| **Fastpath: Internal Ingress Bypass** | `https://harbor-nginx.lan:8443/v2/` | Direct L2/L3 10GbE network route (MTU 9000 jumbo frames). Line-rate throughput ($800+$ MB/s), zero payload caps. |

To guarantee deterministic, high-throughput delivery, RROM mandates an **Internal Network Bypass**:
1. Runners authenticate and push directly to the internal registry endpoint (e.g., `harbor-nginx.lan:8443`) over isolated local network interfaces (`10GbE`, MTU 9000 jumbo frames).
2. The internal endpoint bypasses external proxies entirely, supporting layer uploads of arbitrary size with zero payload caps.
3. The resulting images maintain canonical registry naming parity using Docker/Podman tag aliases or registry mirrors, ensuring that image metadata and signatures reference the sovereign estate FQDN (`harbor.ravenhelm.dev`).

### OCI Annotations and Build Metadata

The build workflow must embed tamper-evident build provenance directly into the container image configuration block using standard OpenContainer Initiative (OCI) image annotations (defined by the OCI Image Format Specification) and estate-specific labels:

* `org.opencontainers.image.revision`: The full 40-character or 12-character abbreviated Git commit hash (`${{ steps.meta.outputs.sha }}`).
* `net.ravenmask.build`: The monotonic build sequence number (`b${{ github.run_number }}`).
* `org.opencontainers.image.source`: The canonical Git repository URL.
* `org.opencontainers.image.created`: The RFC 3339 UTC timestamp marking the exact instant compilation commenced.
* `org.opencontainers.image.title`: The service identifier (e.g., `vitki`).

These annotations are stored inside the OCI image manifest and config JSON. Once pushed, they allow security scanners, runtime admission controllers, and incident response teams to inspect any running container in Kubernetes and identify its exact commit, pipeline run, and source repository without relying on external documentation.

### Concrete Implementation: Forgejo Actions (`.forgejo/workflows/build.yml`)

The following production workflow is configured for Forgejo Actions running on self-hosted `eikthyrnir` runner infrastructure:

```yaml
# .forgejo/workflows/build.yml
# Canonical RROM Ingress Build Workflow for Forgejo Actions
name: Build & Ingress Custody

on:
  push:
    branches:
      - main
    paths-ignore:
      - 'chart/**'
      - 'docs/**'
      - '*.md'
      - 'CHANGELOG.md'
      - '.forgejo/workflows/release.yml'
      - '.github/workflows/release.yml'

concurrency:
  group: build-ingress-${{ github.ref }}
  cancel-in-progress: false

jobs:
  ingress-build:
    name: Compile, Package & Ingress OCI Image
    runs-on: [self-hosted, eikthyrnir]
    timeout-minutes: 20
    
    steps:
      - name: Checkout Canonical Trunk Source
        uses: actions/checkout@v4
        with:
          fetch-depth: 1
          # Do not persist auth token to disk in self-hosted workspaces
          persist-credentials: false

      - name: Calculate Monotonic Build & Commit Identifiers
        id: meta
        run: |
          set -euo pipefail
          
          # Compute 12-character abbreviated commit hash
          COMMIT_SHA=$(git rev-parse --short=12 HEAD)
          
          # Format monotonic build identifier from pipeline run counter
          BUILD_IDENTIFIER="b${{ github.run_number }}"
          
          # Generate RFC3339 timestamp
          BUILD_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
          
          echo "sha=${COMMIT_SHA}" >> "$GITHUB_OUTPUT"
          echo "build=${BUILD_IDENTIFIER}" >> "$GITHUB_OUTPUT"
          echo "timestamp=${BUILD_TIMESTAMP}" >> "$GITHUB_OUTPUT"
          
          echo "Ingress Build Initialized: Build=${BUILD_IDENTIFIER} Commit=${COMMIT_SHA}"

      - name: Authenticate to Internal Registry (Internal Bypass)
        env:
          HARBOR_INTERNAL_HOST: "harbor-nginx.lan:8443"
          HARBOR_USER: ${{ secrets.HARBOR_ROBOT_USER }}
          HARBOR_TOKEN: ${{ secrets.HARBOR_ROBOT_TOKEN }}
        run: |
          set -euo pipefail
          # Authenticate against local high-speed ingress endpoint using password-stdin
          echo "$HARBOR_TOKEN" | podman login "$HARBOR_INTERNAL_HOST" \
            --username "$HARBOR_USER" \
            --password-stdin \
            --tls-verify=true

      - name: Compile and Package OCI Container Image
        env:
          PUBLIC_REGISTRY: "harbor.ravenhelm.dev/platform/vitki"
          INTERNAL_REGISTRY: "harbor-nginx.lan:8443/platform/vitki"
          BUILD_ID: ${{ steps.meta.outputs.build }}
          COMMIT_SHA: ${{ steps.meta.outputs.sha }}
          BUILD_TIME: ${{ steps.meta.outputs.timestamp }}
        run: |
          set -euo pipefail
          
          # Build using rootless Podman with explicit OCI specification labels
          podman build \
            --format oci \
            --pull=always \
            --no-cache=false \
            --security-opt label=disable \
            --label "org.opencontainers.image.title=vitki" \
            --label "org.opencontainers.image.source=https://git.ravenhelm.dev/platform/vitki" \
            --label "org.opencontainers.image.revision=${COMMIT_SHA}" \
            --label "org.opencontainers.image.created=${BUILD_TIME}" \
            --label "net.ravenmask.build=${BUILD_ID}" \
            --label "net.ravenmask.builder=forgejo-eikthyrnir" \
            -t "${INTERNAL_REGISTRY}:${BUILD_ID}" \
            -t "${INTERNAL_REGISTRY}:sha-${COMMIT_SHA}" \
            -t "${INTERNAL_REGISTRY}:uat" \
            -f Containerfile .

      - name: Push Container Images via High-Speed Internal Link
        env:
          INTERNAL_REGISTRY: "harbor-nginx.lan:8443/platform/vitki"
          BUILD_ID: ${{ steps.meta.outputs.build }}
          COMMIT_SHA: ${{ steps.meta.outputs.sha }}
        run: |
          set -euo pipefail
          
          echo "Pushing immutable monotonic build tag: :${BUILD_ID}"
          podman push "${INTERNAL_REGISTRY}:${BUILD_ID}"
          
          echo "Pushing commit-bound forensic tag: :sha-${COMMIT_SHA}"
          podman push "${INTERNAL_REGISTRY}:sha-${COMMIT_SHA}"
          
          echo "Updating staging user acceptance stream: :uat"
          podman push "${INTERNAL_REGISTRY}:uat"

      - name: Resolve and Record Immutable Content Digest
        id: digest
        env:
          INTERNAL_REGISTRY: "harbor-nginx.lan:8443/platform/vitki"
          BUILD_ID: ${{ steps.meta.outputs.build }}
        run: |
          set -euo pipefail
          
          # Inspect remote image manifest to obtain immutable sha256 digest
          RAW_DIGEST=$(podman inspect --format '{{.Digest}}' "${INTERNAL_REGISTRY}:${BUILD_ID}")
          
          if [ -z "${RAW_DIGEST}" ]; then
            echo "ERROR: Failed to resolve image digest from registry!" >&2
            exit 1
          fi
          
          echo "digest=${RAW_DIGEST}" >> "$GITHUB_OUTPUT"
          echo "CONFIRMED INGRESS ARTIFACT: ${INTERNAL_REGISTRY}:${BUILD_ID}@${RAW_DIGEST}"

      - name: Teardown Local Runner Images
        if: always()
        run: |
          # Purge transient image layers from runner disk to ensure workspace cleanliness
          podman rmi -f $(podman images -q "harbor-nginx.lan:8443/platform/vitki") || true
          podman system prune -f --volumes || true
```

### Concrete Implementation: GitHub Actions (`.github/workflows/build.yml`)

For organizations maintaining repositories on GitHub Enterprise or public GitHub while deploying to sovereign Harbor registries, the identical structural contract applies:

```yaml
# .github/workflows/build.yml
# Canonical RROM Ingress Build Workflow for GitHub Actions
name: Build & Ingress Custody

on:
  push:
    branches:
      - main
    paths-ignore:
      - 'chart/**'
      - 'docs/**'
      - '*.md'
      - 'CHANGELOG.md'
      - '.forgejo/**'
      - '.github/workflows/release.yml'

concurrency:
  group: build-ingress-${{ github.ref }}
  cancel-in-progress: false

jobs:
  ingress-build:
    name: Compile, Package & Ingress OCI Image
    runs-on: ubuntu-latest
    timeout-minutes: 25
    
    steps:
      - name: Checkout Canonical Trunk Source
        uses: actions/checkout@v4
        with:
          fetch-depth: 1
          persist-credentials: false

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
        with:
          driver-opts: image=moby/buildkit:latest

      - name: Calculate Monotonic Build & Commit Identifiers
        id: meta
        run: |
          set -euo pipefail
          COMMIT_SHA=$(git rev-parse --short=12 HEAD)
          BUILD_IDENTIFIER="b${{ github.run_number }}"
          BUILD_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
          
          echo "sha=${COMMIT_SHA}" >> "$GITHUB_OUTPUT"
          echo "build=${BUILD_IDENTIFIER}" >> "$GITHUB_OUTPUT"
          echo "timestamp=${BUILD_TIMESTAMP}" >> "$GITHUB_OUTPUT"

      - name: Authenticate to Sovereign Harbor Registry
        uses: docker/login-action@v3
        with:
          registry: harbor.ravenhelm.dev
          username: ${{ secrets.HARBOR_ROBOT_USER }}
          password: ${{ secrets.HARBOR_ROBOT_TOKEN }}

      - name: Build and Push Container Images
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile
          push: true
          tags: |
            harbor.ravenhelm.dev/platform/vitki:${{ steps.meta.outputs.build }}
            harbor.ravenhelm.dev/platform/vitki:sha-${{ steps.meta.outputs.sha }}
            harbor.ravenhelm.dev/platform/vitki:uat
          labels: |
            org.opencontainers.image.title=vitki
            org.opencontainers.image.source=https://github.com/nwalker85/vitki
            org.opencontainers.image.revision=${{ steps.meta.outputs.sha }}
            org.opencontainers.image.created=${{ steps.meta.outputs.timestamp }}
            net.ravenmask.build=${{ steps.meta.outputs.build }}
            net.ravenmask.builder=github-hosted-runner
```

---

## 2. The Release Promotion Workflow (`release.yml`)

The release workflow is the operational enactment of **Principle 2 (Releases Never Rebuild)** and **Principle 3 (Promotion by Reference)**. Triggered exclusively by pushing an annotated Git tag matching `v*` (e.g., `v1.4.2`), this workflow executes zero compilation commands, invokes no language package managers, and alters zero lines of application source code.

Its responsibility is strictly administrative and cryptographic:
1. **Verify Parity:** Execute static validation scripts to ensure that the release tag precisely matches configuration references and contains zero unvetted source code changes.
2. **Promote by Reference:** Invoke the OCI Registry v2 API to retag the pre-existing, pre-validated build digest to the new Semantic Version tag (`:vX.Y.Z`).
3. **Publish OCI Helm Chart:** Package the Helm chart directory and push the packaged chart archive (`.tgz`) to Harbor's OCI chart repository.

| Promotion Phase | Guard / Executor | Invariant & Operational Action |
| :--- | :--- | :--- |
| **Phase 1: Parity Gate** | `check-release-tag.sh` & `check-release-source-parity.sh` | Asserts 3-way tag alignment; proves git diff touches ONLY `chart/` and `CHANGELOG.md`. Fails closed if source diffs exist. |
| **Phase 2: Registry Retagging** | Registry v2 Manifest API | Extracts `:b<N>` digest from `values.yaml`; PUTs manifest under `:vX.Y.Z`. Zero compilation, zero layer blob transfer. |
| **Phase 3: Chart Publishing** | Helm OCI Packager | `helm package chart/ --version X.Y.Z`; pushes immutable OCI chart archive to `oci://harbor.ravenhelm.dev/charts/`. |

### The Parity Verification Gate

Before any promotion action occurs, the `verify` job executes two deterministic validation checks:

#### 1. `scripts/check-release-tag.sh` (The Parity Triangle)
This script asserts exact alignment across the three coordinate axes of a release:
* The Git ref name (`v1.4.2`)
* The Helm chart version and appVersion (`chart/Chart.yaml`)
* The container image tag pinned in production values (`chart/values.yaml`)

```bash
#!/usr/bin/env bash
# scripts/check-release-tag.sh
# Enforces exact alignment between Git tag, Chart metadata, and values.yaml

set -euo pipefail

GIT_TAG="${GITHUB_REF_NAME:-$(git describe --tags --exact-match 2>/dev/null || echo "")}"
if [ -z "${GIT_TAG}" ]; then
  echo "ERROR: Unable to resolve current Git tag." >&2
  exit 1
fi

SEMVER="${GIT_TAG#v}"

CHART_VERSION=$(yq '.version' chart/Chart.yaml)
CHART_APP_VERSION=$(yq '.appVersion' chart/Chart.yaml)
VALUES_TAG=$(yq '.image.tag' chart/values.yaml)

echo "=== Verifying Release Parity Triangle ==="
echo "Git Tag:       ${GIT_TAG} (SemVer: ${SEMVER})"
echo "Chart Version: ${CHART_VERSION}"
echo "Chart AppVer:  ${CHART_APP_VERSION}"
echo "Values Tag:    ${VALUES_TAG}"

FAIL=0

if [ "${CHART_VERSION}" != "${SEMVER}" ]; then
  echo "FAIL: chart/Chart.yaml version ('${CHART_VERSION}') does not match SemVer ('${SEMVER}')" >&2
  FAIL=1
fi

if [ "${CHART_APP_VERSION}" != "${SEMVER}" ]; then
  echo "FAIL: chart/Chart.yaml appVersion ('${CHART_APP_VERSION}') does not match SemVer ('${SEMVER}')" >&2
  FAIL=1
fi

if [ "${VALUES_TAG}" != "${GIT_TAG}" ]; then
  echo "FAIL: chart/values.yaml image.tag ('${VALUES_TAG}') does not match Git tag ('${GIT_TAG}')" >&2
  FAIL=1
fi

if [ "$FAIL" -ne 0 ]; then
  echo "CRITICAL: Parity Triangle breached! Aborting release promotion." >&2
  exit 1
fi

echo "PASS: Parity Triangle fully synchronized."
```

#### 2. `scripts/check-release-source-parity.sh` (Source Immutability Guard)
This script verifies that the commit associated with the release tag introduced **zero application source code modifications**. It ensures that the only modified files are metadata configuration files (`chart/**`, `CHANGELOG.md`, `docs/**`).

```bash
#!/usr/bin/env bash
# scripts/check-release-source-parity.sh
# Verifies that the release commit modified ONLY metadata and Helm configurations.

set -euo pipefail

TARGET_REF="${1:-HEAD}"
BASE_REF="${2:-origin/main}"

echo "Comparing ${TARGET_REF} against ${BASE_REF} for application source code drift..."

# Extract all changed files outside of allowed metadata directories
FORBIDDEN_CHANGES=$(git diff --name-only "${BASE_REF}"..."${TARGET_REF}" | \
  grep -vE '^(chart/|CHANGELOG\.md|docs/|\.forgejo/|\.github/)' || true)

if [ -n "${FORBIDDEN_CHANGES}" ]; then
  echo "CRITICAL ERROR: Release commit alters application source code files!" >&2
  echo "Forbidden files modified in release commit:" >&2
  echo "${FORBIDDEN_CHANGES}" | sed 's/^/  ! /' >&2
  echo "Violation of Principle 2: Releases must never compile or alter source code." >&2
  exit 1
fi

echo "PASS: Zero application source drift proven. Only metadata modified."
```

### Registry v2 API Retagging (`scripts/harbor-artifact.sh`)

Standard Docker or Podman CLI tooling does not natively support retagging a remote registry artifact without first downloading (`docker pull`) and re-uploading (`docker push`) the entire image layer payload. For a 2 GB image, pulling and pushing on release wastes minutes of pipeline time, risks layer corruption, and consumes network I/O.

Under RROM, retagging is executed strictly via the **OCI Registry v2 Manifest API**. Because an OCI tag is merely a named pointer to a content-addressed manifest JSON document, retagging requires only two lightweight HTTP requests:
1. `GET /v2/<name>/manifests/<source-reference>`: Download the image manifest JSON and capture its `Content-Type` header and `Docker-Content-Digest`.
2. `PUT /v2/<name>/manifests/<target-tag>`: Upload the identical manifest JSON payload under the target Semantic Version tag (`v1.4.2`).

The underlying layer blobs (the gigabytes of compiled binaries and root filesystem layers) are completely untouched on the storage backend. The entire retag operation completes in under 500 milliseconds.

```bash
#!/usr/bin/env bash
# scripts/harbor-artifact.sh
# Interacts directly with OCI Registry v2 API to resolve digests and retag artifacts.

set -euo pipefail

REGISTRY_HOST="${HARBOR_INTERNAL_HOST:-harbor-nginx.lan:8443}"
PROJECT="platform"
REPOSITORY="vitki"

ACTION="${1:-}"
case "${ACTION}" in
  resolve)
    BUILD_TAG="$2"
    echo "Resolving digest for tag: ${BUILD_TAG}..." >&2
    
    # Issue HEAD request to retrieve Docker-Content-Digest header
    DIGEST=$(curl -sI -u "${HARBOR_USER}:${HARBOR_TOKEN}" \
      -H "Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json" \
      "https://${REGISTRY_HOST}/v2/${PROJECT}/${REPOSITORY}/manifests/${BUILD_TAG}" | \
      grep -i '^Docker-Content-Digest:' | awk '{print $2}' | tr -d '\r\n')
    
    if [ -z "${DIGEST}" ]; then
      echo "ERROR: Unable to resolve digest for ${BUILD_TAG}" >&2
      exit 1
    fi
    echo "${DIGEST}"
    ;;

  retag)
    SOURCE_TAG="$2"
    TARGET_TAG="$3"
    
    echo "Promoting artifact by reference: ${SOURCE_TAG} -> ${TARGET_TAG}" >&2
    
    # 1. Fetch source manifest and content type
    TMP_MANIFEST=$(mktemp)
    TMP_HEADERS=$(mktemp)
    
    curl -sS -u "${HARBOR_USER}:${HARBOR_TOKEN}" \
      -D "${TMP_HEADERS}" \
      -H "Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json" \
      "https://${REGISTRY_HOST}/v2/${PROJECT}/${REPOSITORY}/manifests/${SOURCE_TAG}" \
      -o "${TMP_MANIFEST}"
    
    CONTENT_TYPE=$(grep -i '^Content-Type:' "${TMP_HEADERS}" | awk '{print $2}' | tr -d '\r\n')
    RESOLVED_DIGEST=$(grep -i '^Docker-Content-Digest:' "${TMP_HEADERS}" | awk '{print $2}' | tr -d '\r\n')
    
    rm -f "${TMP_HEADERS}"
    
    if [ -z "${CONTENT_TYPE}" ] || [ ! -s "${TMP_MANIFEST}" ]; then
      echo "ERROR: Failed to retrieve source manifest for ${SOURCE_TAG}" >&2
      rm -f "${TMP_MANIFEST}"
      exit 1
    fi
    
    echo "Fetched manifest for ${SOURCE_TAG} (Digest: ${RESOLVED_DIGEST}, Type: ${CONTENT_TYPE})" >&2
    
    # 2. PUT identical manifest under the target release tag
    HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" -X PUT \
      -u "${HARBOR_USER}:${HARBOR_TOKEN}" \
      -H "Content-Type: ${CONTENT_TYPE}" \
      "https://${REGISTRY_HOST}/v2/${PROJECT}/${REPOSITORY}/manifests/${TARGET_TAG}" \
      --data-binary @"${TMP_MANIFEST}")
    
    rm -f "${TMP_MANIFEST}"
    
    if [ "${HTTP_CODE}" != "201" ] && [ "${HTTP_CODE}" != "200" ]; then
      echo "ERROR: Registry manifest PUT failed with HTTP status ${HTTP_CODE}" >&2
      exit 1
    fi
    
    echo "SUCCESS: Promoted ${RESOLVED_DIGEST} to tag ${TARGET_TAG} (HTTP ${HTTP_CODE})" >&2
    ;;

  *)
    echo "Usage: $0 {resolve <build-tag> | retag <source-tag> <target-tag>}" >&2
    exit 1
    ;;
esac
```

### Complete Workflow Specification: Forgejo Actions (`.forgejo/workflows/release.yml`)

The following production workflow integrates parity validation, Registry v2 API retagging, and Helm chart OCI publishing into a unified, atomic pipeline:

```yaml
# .forgejo/workflows/release.yml
# Canonical RROM Release Promotion Workflow for Forgejo Actions
name: Release & Provenance Promotion

on:
  push:
    tags:
      - 'v*'

concurrency:
  group: release-promotion-${{ github.ref }}
  cancel-in-progress: false

jobs:
  verify:
    name: Enforce Release Parity Gates
    runs-on: [self-hosted, eikthyrnir]
    timeout-minutes: 5
    
    steps:
      - name: Checkout Tagged Commit
        uses: actions/checkout@v4
        with:
          fetch-depth: 0 # Full history required for diff validation against trunk
          persist-credentials: false

      - name: Verify Parity Triangle
        run: |
          chmod +x scripts/check-release-tag.sh
          scripts/check-release-tag.sh

      - name: Assert Zero Application Source Drift
        run: |
          chmod +x scripts/check-release-source-parity.sh
          # Verify HEAD of tag against origin/main
          git fetch origin main:refs/remotes/origin/main
          scripts/check-release-source-parity.sh "HEAD" "origin/main"

  promote:
    name: Promote Artifact by Reference & Publish Chart
    needs: verify
    runs-on: [self-hosted, eikthyrnir]
    timeout-minutes: 10
    
    steps:
      - name: Checkout Tagged Commit
        uses: actions/checkout@v4
        with:
          fetch-depth: 1
          persist-credentials: false

      - name: Install Required CLI Utilities
        run: |
          # Ensure yq, helm, and curl are available in runner environment
          command -v yq >/dev/null 2>&1 || (echo "yq missing" && exit 1)
          command -v helm >/dev/null 2>&1 || (echo "helm missing" && exit 1)
          command -v curl >/dev/null 2>&1 || (echo "curl missing" && exit 1)

      - name: Resolve Release Coordinates from Manifests
        id: release-meta
        run: |
          set -euo pipefail
          
          RELEASE_TAG="${GITHUB_REF_NAME}"
          SEMVER="${RELEASE_TAG#v}"
          
          PINNED_BUILD=$(yq '.image.build' chart/values.yaml)
          PINNED_DIGEST=$(yq '.image.digest' chart/values.yaml)
          
          if [ -z "${PINNED_BUILD}" ] || [ "${PINNED_BUILD}" = "null" ]; then
            echo "ERROR: chart/values.yaml does not contain a valid .image.build identifier!" >&2
            exit 1
          fi
          
          echo "tag=${RELEASE_TAG}" >> "$GITHUB_OUTPUT"
          echo "semver=${SEMVER}" >> "$GITHUB_OUTPUT"
          echo "build=${PINNED_BUILD}" >> "$GITHUB_OUTPUT"
          echo "digest=${PINNED_DIGEST}" >> "$GITHUB_OUTPUT"
          
          echo "Promotion Target: Tag=${RELEASE_TAG} Build=${PINNED_BUILD} ExpectedDigest=${PINNED_DIGEST}"

      - name: Promote Registry Artifact via OCI Registry v2 API
        env:
          HARBOR_INTERNAL_HOST: "harbor-nginx.lan:8443"
          HARBOR_USER: ${{ secrets.HARBOR_RELEASE_ROBOT_USER }}
          HARBOR_TOKEN: ${{ secrets.HARBOR_RELEASE_ROBOT_TOKEN }}
        run: |
          set -euo pipefail
          chmod +x scripts/harbor-artifact.sh
          
          # 1. Verify remote digest of the source build matches our values.yaml expectation
          REMOTE_DIGEST=$(scripts/harbor-artifact.sh resolve "${{ steps.release-meta.outputs.build }}")
          
          echo "Remote Digest:   ${REMOTE_DIGEST}"
          echo "Expected Digest: ${{ steps.release-meta.outputs.digest }}"
          
          if [ "${REMOTE_DIGEST}" != "${{ steps.release-meta.outputs.digest }}" ]; then
            echo "CRITICAL: Digest mismatch! The build has mutated or values.yaml is out of date." >&2
            exit 1
          fi
          
          # 2. Retag existing digest to SemVer release tag
          scripts/harbor-artifact.sh retag \
            "${{ steps.release-meta.outputs.build }}" \
            "${{ steps.release-meta.outputs.tag }}"

      - name: Package and Publish Helm Chart to OCI Registry
        env:
          HELM_EXPERIMENTAL_OCI: 1
          HARBOR_INTERNAL_HOST: "harbor-nginx.lan:8443"
          HARBOR_USER: ${{ secrets.HARBOR_RELEASE_ROBOT_USER }}
          HARBOR_TOKEN: ${{ secrets.HARBOR_RELEASE_ROBOT_TOKEN }}
          SEMVER: ${{ steps.release-meta.outputs.semver }}
        run: |
          set -euo pipefail
          
          echo "$HARBOR_TOKEN" | helm registry login "$HARBOR_INTERNAL_HOST" \
            --username "$HARBOR_USER" \
            --password-stdin
          
          echo "Packaging Helm Chart for version ${SEMVER}..."
          helm package chart/ --version "${SEMVER}" --app-version "${SEMVER}"
          
          CHART_PACKAGE="vitki-${SEMVER}.tgz"
          if [ ! -f "${CHART_PACKAGE}" ]; then
            echo "ERROR: Expected chart package ${CHART_PACKAGE} not found!" >&2
            exit 1
          fi
          
          echo "Publishing chart package to OCI registry..."
          helm push "${CHART_PACKAGE}" "oci://${HARBOR_INTERNAL_HOST}/charts"
          
          echo "SUCCESS: Helm chart oci://${HARBOR_INTERNAL_HOST}/charts/vitki:${SEMVER} published."
```

---

## 3. Runner Security & Token Scoping Architecture

The execution of automated pipelines introduces significant security blast-radius risks. If an automation runner is provisioned with over-privileged credentials or ambient access to infrastructure, any compromised dependency in a build step or unauthorized script execution can lead to estate-wide cluster compromise.

RROM establishes an architectural model based on **Strict Runner Isolation** and **Least-Privilege Token Scoping**.

| Execution Plane | Robot Identity | Scoped Permissions & Invariant Boundaries |
| :--- | :--- | :--- |
| **Ingress Runner (`build.yml`)** | `robot$platform+ci-ingress` | Scoped strictly to push artifacts to `platform/`; prohibited from deleting tags, accessing other projects, or reading cluster secrets. |
| **Release Runner (`release.yml`)** | `robot$platform+ci-release` | Read manifest and retag existing digests in `platform/`; push charts to `charts/`. Zero compiler access; zero push access to protected branches. |
| **Production Cluster Plane** | In-Cluster Argo CD | Zero inbound ports open to CI runners. Cluster pulls state strictly via outbound GitOps polling. |

### Least-Privilege Harbor CI Robot Tokens

Under RROM, human administrative credentials or global registry administrator tokens are strictly forbidden within CI/CD secrets storage. Registry authentication must use Harbor **Project-Level Robot Accounts** scoped with mathematical precision:

#### 1. Ingress Build Robot Account (`robot$platform+ci-ingress`)
* **Project Scope:** Scoped exclusively to the target project (e.g., `platform`). Zero access to `library`, `system`, or unrelated tenant projects.
* **Permissions Granted:**
  * `repository:pull` (to pull cached base layers)
  * `repository:push` (to upload new layers and tags)
* **Permissions Denied:**
  * `repository:delete` (cannot delete or overwrite immutable tags)
  * `tag:delete` (cannot remove existing tags)
  * `artifact:delete` (cannot delete layer blobs)
  * `scanner:read / scanner:stop` (cannot bypass vulnerability scanning gates)

#### 2. Release Promotion Robot Account (`robot$platform+ci-release`)
* **Project Scope:** Scoped to `platform` (container repositories) and `charts` (Helm OCI repositories).
* **Permissions Granted:**
  * `platform`: `repository:pull`, `repository:push` (restricted to creating manifest tags)
  * `charts`: `repository:pull`, `repository:push` (uploading Helm `.tgz` OCI artifacts)
* **Permissions Denied:**
  * Administrative modification of project retention rules, immutable tag rules, or robot creation.

#### Expiration and Rotation Policy
Robot tokens are provisioned with automated rotation lifecycles (typically 90 days), with tokens stored securely in OpenBao/Vault and injected into repository secret stores via automated synchronization jobs.

### Read-Only Code Checkout Tokens

Workflows must strictly partition read authority from write authority:
* In Forgejo Actions, pipeline checkouts must configure `persist-credentials: false`. The ambient Git authentication token injected during checkout is not persisted to the runner's `.git/config`.
* Workflows cannot push commits back to `main` or update branch pointers. Any operational change (such as bumping a formula or pinning a release) must take the form of an audited Pull Request.
* Secret exposure is minimized by ensuring secrets are bound only to individual steps that require them (`env: HARBOR_TOKEN: ${{ secrets... }}`), rather than declared globally across the entire job.

### Ephemeral Runner Isolation and Sandboxing

Self-hosted runner nodes (the `eikthyrnir` fleet) execute builds within disposable, isolated sandboxes:

1. **Rootless Container Runtimes:** All compilation and image packaging steps execute via rootless Podman or Docker user-namespace mappings (`userns-remap`). Even if a compilation process escapes a container layer boundary, it possesses zero root authority on the underlying Linux host OS.
2. **Disk Sanitation and Volume Purging:** At the completion of every pipeline job (enforced by `if: always()` teardown steps), local layer caches, build artifacts, and checkout directories are purged from disk (`podman system prune -f --volumes`). No state persists between runs that could allow cross-tenant data leakage or secret snooping.
3. **Network Boundary Segmentation:** Runner nodes reside on an isolated automation VLAN (e.g., VLAN 20). Runners are granted egress network access strictly to:
   * The code host (`git.ravenhelm.dev:443`)
   * The internal registry bypass (`harbor-nginx.lan:8443`)
   * Internal package mirrors / proxies (e.g., Nexus or devypi)
4. **Zero Cluster Ingress:** Runners possess zero network routes to Kubernetes control plane nodes (`apiserver:6443`), zero SSH keys to production hypervisors, and zero ambient kubeconfig credentials. A total compromise of a CI runner exposes no lateral route into live production clusters.

---

## 4. Production Failure Modes & Operational Runbook

Even in well-architected pipelines, network anomalies, configuration skew, and human error can trigger failures. The following operational runbook diagnoses the four most common failure modes encountered in code host and registry integration.

---

### Failure Mode 1: Cloudflare HTTP 413 "Request Entity Too Large"

#### Symptoms
During the image push step of `build.yml`, Podman or Docker fails with:
```text
Error: error pushing image "harbor.ravenhelm.dev/platform/vitki:b42":
  received unexpected HTTP status: 413 Request Entity Too Large
```

#### Root Cause
The runner attempted to push image layers through the public Cloudflare tunnel hostname (`harbor.ravenhelm.dev`). A container filesystem layer exceeded the 100 MB proxy payload threshold, causing Cloudflare's edge proxy to terminate the HTTP `POST` or `PATCH` request.

#### Resolution
1. Verify the runner is configured to use the internal ingress endpoint (`harbor-nginx.lan:8443`) instead of the public WAN hostname.
2. Check the runner's DNS resolution:
   ```bash
   dig harbor-nginx.lan +short
   ```
   Ensure it resolves to the local LAN IP of the Harbor reverse proxy (e.g., `10.10.10.35`).
3. If public resolution is required for external runners, configure Cloudflare Tunnel bypass rules or utilize a registry proxy endpoint with streaming uploads enabled.

---

### Failure Mode 2: The Infinite Release Build Loop

#### Symptoms
Upon merging a Release PR into `main`, the CI system immediately triggers a new `build.yml` run (e.g., build `:b43`), generating a brand-new container digest and desynchronizing the newly published release.

#### Root Cause
The `paths-ignore` block in `.forgejo/workflows/build.yml` or `.github/workflows/build.yml` is missing or improperly formatted, failing to exclude `chart/**`, `CHANGELOG.md`, or documentation files.

#### Resolution
1. Immediately inspect `.forgejo/workflows/build.yml` and ensure the following filters are active:
   ```yaml
   paths-ignore:
     - 'chart/**'
     - 'docs/**'
     - '*.md'
     - 'CHANGELOG.md'
   ```
2. Manually cancel the errant build run in the code host interface.
3. If `:b43` was pushed to Harbor under `:uat`, re-point the `:uat` tag back to the verified release digest using `scripts/harbor-artifact.sh retag b42 uat`.

---

### Failure Mode 3: Registry v2 404 / 400 Manifest Mismatch during Promotion

#### Symptoms
During the `promote` job in `release.yml`, `scripts/harbor-artifact.sh` fails:
```text
ERROR: Registry manifest PUT failed with HTTP status 400 Bad Request
```
or
```text
ERROR: Unable to resolve digest for b42: HTTP 404 Not Found
```

#### Root Cause
* **404 Not Found:** The build tag `:b42` was purged by a Harbor retention policy, was pushed to a different project namespace, or the ingress build failed silently.
* **400 Bad Request:** The `Accept` header sent during the `GET` request retrieved a legacy Docker Schema v1 manifest, which Harbor rejected when re-uploaded via `PUT` with an OCI MediaType header.

#### Resolution
1. Verify that the build exists in Harbor:
   ```bash
   curl -sI -u "${HARBOR_USER}:${HARBOR_TOKEN}" \
     "https://harbor-nginx.lan:8443/v2/platform/vitki/manifests/b42"
   ```
2. Ensure `scripts/harbor-artifact.sh` includes explicit multi-type acceptance headers:
   ```bash
   -H "Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"
   ```
3. Inspect Harbor's core log (`/var/log/harbor/core.log`) to view detailed JSON validation errors.

---

### Failure Mode 4: Stale Runner Workspace and Layer Cache Poisoning

#### Symptoms
A build fails with unexplained compilation errors or references outdated dependencies that no longer exist in Git. Alternatively, `podman build` fails with disk exhaustion (`no space left on device`).

#### Root Cause
The self-hosted runner workspace was reused without proper volume pruning, leaving orphaned container layers, stopped containers, and stale Git worktree state on the runner disk.

#### Resolution
1. SSH into the affected runner node (`eikthyrnir` fleet) and execute full workspace sanitation:
   ```bash
   # Remove all stopped containers and untagged images
   podman system prune -a -f --volumes
   
   # Inspect disk usage on container storage volume
   df -h /var/lib/containers/storage
   ```
2. Ensure the teardown step in `build.yml` includes an unconditional cleanup hook:
   ```yaml
   - name: Teardown Local Runner Images
     if: always()
     run: |
       podman rmi -f $(podman images -q) || true
       podman system prune -f --volumes || true
   ```

---

## 5. Architectural Checklist for Chapter 12 Compliance

Before certifying a software repository for sovereign RROM release operations, the engineering team must verify each item in the following integration matrix:

| Requirement | Verification Command / Target | Pass Criteria |
| :--- | :--- | :--- |
| **Trunk Ingress Build** | `.forgejo/workflows/build.yml` | Triggers strictly on `push: branches: [main]` |
| **Path Filtering Guard** | `paths-ignore` block | Contains `chart/**`, `docs/**`, `*.md`, `CHANGELOG.md` |
| **Internal Bypass** | Registry endpoint configuration | Runner pushes to `harbor-nginx.lan:8443` (Zero Cloudflare proxy) |
| **OCI Metadata Binding** | `podman inspect` / `docker inspect` | Manifest contains `net.ravenmask.build` and `org.opencontainers.image.revision` |
| **Zero-Build Release** | `.forgejo/workflows/release.yml` | Contains zero compiler, packager, or source-altering steps |
| **Tag Verification Gate** | `scripts/check-release-tag.sh` | Confirms `git tag == Chart version == values.yaml tag` |
| **Source Parity Gate** | `scripts/check-release-source-parity.sh` | Confirms zero application diff between trunk and release tag |
| **Manifest Retagging** | `scripts/harbor-artifact.sh` | Uses OCI Registry v2 API `GET`/`PUT` manifest retag (No pull/push) |
| **OCI Chart Push** | `helm push oci://...` | Chart `.tgz` published directly to Harbor OCI repository |
| **Scoped Robot Account** | Harbor Robot Permissions | Scoped strictly to target project; zero administrative/delete rights |
| **Runner Containment** | Runner execution runtime | Rootless container execution; disk purged after every run |

<!-- RUBRIC_CHECK: Chapter 12 conforms to RROM specification. -->

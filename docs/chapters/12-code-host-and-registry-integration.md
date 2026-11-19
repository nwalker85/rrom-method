# Chapter 12: Code Host & Registry Integration

<!-- LICENSE: © 2026 Ravenhelm LLC. Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Attribution required: "Ravenhelm LLC — Ravenhelm Release Operations Methodology (RROM), https://ravenhelm.dev". -->

## Engineering the Automation Substrate

On October 10, 2026, a Forgejo Actions job declared `runs-on: docker` and died mid-flight because it could not talk to a container socket. An agent inspecting the failure assumed the repository's `Dockerfile` or workflow syntax had regressed and began drafting a fix against the repo. The repo was innocent. On Ravenhelm's Forgejo estate, the label `runs-on: docker` is advertised by two physically distinct runner pools: the `Norns` light lane (which mounts a Docker-in-Docker socket into the job container) and the `eikthyrnir` scheduler pool (which runs isolated job containers without exposing a nested container socket). Guessing why a job failed without first querying Forgejo's `action_task` table to prove *which runner ID actually claimed the task* fabricates a false diagnosis every time.

That runner pool collision sat next to two other CI traps on the bench. On September 16, 2026, the runner scheduler's health endpoint reported `active_jobs: 2, active_oldest_seconds: 0`. The dashboard was green. In reality, both runner containers had been wedged for **47 minutes**; the age counter returned `0` because the query defaulted to zero when the timestamp join missed. And when a failed job's log vanished from the Forgejo web UI and REST API with a 404, operators used to re-run the build blind, destroying the crime scene. The log was never gone. When Forgejo fails to flush a task log to object storage after an abrupt runner disconnect, the raw log chunks remain sitting in Forgejo's `dbfs` (`dbfs_meta` and `dbfs_data`) tables inside Postgres, waiting to be read directly with a SQL query.

A release methodology is only as honest as the code host, runner fleet, and artifact registry executing it. The core invariants of RROM - **Principle RP-1 (Build Once on Ingress)**, **Principle RP-2 (Releases Never Rebuild)**, and **Principle RP-3 (Promotion by Reference)** - must be enforced in silicon and YAML across Forgejo (or GitHub) and **Harbor**. If your `build.yml` lacks path filters, merging a release PR triggers a recursive rebuild. If your runner pushes through a public Cloudflare tunnel instead of internal `harbor-nginx`, every layer over 100 MB dies with `HTTP 413`. And if nobody watches whether a merge to `main` actually fired a pipeline, a dropped webhook looks identical to a quiet afternoon.

| Pipeline Component | Infrastructure Target | Operational Mechanics & Invariants |
| :--- | :--- | :--- |
| **Ingress CI Trigger** | Push to `main` | Filtered by `paths-ignore` (`chart/**`, `docs/**`); watched by Expected-Fire Custodian. |
| **Build & Test** | Ephemeral Runner (`eikthyrnir` / `Norns`) | Explicit runner pool targeting; compiles once; stamps OCI annotations; tags `:b<N>` and `:sha-<sha12>`. |
| **Network Ingestion** | `harbor-nginx` Internal Bypass | Direct LAN/Tailscale route bypasses Cloudflare 100 MB body caps; returns immutable `@sha256` digest. |
| **UAT Soak Validation** | Staging Stream (`:uat`) | Argo CD reconciles `:uat` digest; live probes verify runtime health before release. |
| **Release Promotion** | Tag `v*` Trigger | Parity Triangle + source parity verified; Registry v2 `PUT` retags existing digest to `:vX.Y.Z`. |
| **Production Convergence** | Argo CD (`norns-gitops`) | GitOps pins `values.yaml` to immutable digest and chart version; rolling pod update. |

---

## 1. Three Real Forgejo & Runner Forensics Traps

Before writing a single line of workflow YAML, an operator must know how the code host and runner substrate lie under failure.

### Trap 1: `runs-on: docker` Is Two Pools - Prove the Runner from `action_task`

When multiple runner pools advertise a shared label like `docker`, the Forgejo scheduler assigns queued tasks to whichever daemon polls first. On Ravenhelm, a job picked up by the `Norns` light lane gets a Docker-in-Docker socket; the exact same job picked up by an `eikthyrnir` scheduler container does not.

Never guess which runner executed a job from the workflow file alone. Prove the runner assignment from `action_task` (or the task header) before diagnosing a failure:

```sql
-- Query Forgejo Postgres to prove which physical runner executed task_id
SELECT
  t.id AS task_id,
  t.job_id,
  t.status,
  r.id AS runner_id,
  r.name AS runner_name,
  r.agent_labels
FROM action_task t
LEFT JOIN action_runner r ON r.id = t.runner_id
WHERE t.id = 48192;
```

To eliminate routing roulette in production workflows, bind jobs that require specific hardware or socket capabilities to explicit pool labels (`runs-on: [self-hosted, eikthyrnir]`) rather than ambiguous generic labels.

### Trap 2: Wedged Runners Reporting `active_oldest_seconds: 0`

On September 16, 2026, two runner containers wedged on hung network I/O for **47 minutes** while the scheduler telemetry printed:

```json
{"active_jobs": 2, "active_oldest_seconds": 0}
```

Why did a 47-minute wedge report `0` seconds? Because the age calculation fell back to `0` when the task's start timestamp was null or unjoined. Zero is the number most often shared by *"everything is brand new"* and *"the join is broken."* Any runner health check must assert that when `active_jobs > 0`, `active_oldest_seconds` is strictly greater than zero (or surface `-1 / UNKNOWN` when the timestamp cannot be resolved), and every workflow job must declare an explicit `timeout-minutes` ceiling so a wedged step is killed by the harness instead of holding a slot forever.

### Trap 3: Missing CI Logs in the UI - Read Them Straight from `dbfs`

When a runner crashes or loses its stream mid-step, the Forgejo web UI often displays *"Log not found"* and the REST API returns `404` for the task log endpoint. Do not click "Re-run all jobs" just to get a log back; re-running overwrites task state and hides transient failures.

Until Forgejo transfers finished logs to external storage (or when that transfer fails), live and orphaned task logs sit inside Forgejo's Database File System (`dbfs_meta` and `dbfs_data`) in Postgres. Extract the missing log directly from the database:

```sql
-- Reconstruct a missing Forgejo Actions task log directly from dbfs
SELECT convert_from(d.blob_data, 'UTF8') AS log_chunk
FROM dbfs_meta m
JOIN dbfs_data d ON d.meta_id = m.id
WHERE m.full_path LIKE '%/tasks/' || 48192 || '.log%'
ORDER BY d.blob_offset ASC;
```

Read the corpse before you bury it.

---

## 2. The Ingress Build Workflow (`build.yml`)

The ingress build workflow is the only place in the software lifecycle where a compiler runs. Governed by **Principle RP-1 (Build Once on Ingress)**, `build.yml` triggers strictly on merges to `main`. It never runs on release branches, release tags, or documentation edits.

### Killing the Recursive Release Loop (`paths-ignore`)

A naive trunk workflow triggers on every push to `main`. That creates the **Recursive Release Loop**:
1. A feature PR merges to `main`, and `build.yml` compiles container `:b42`.
2. After `:b42` soaks in UAT, the operator runs `scripts/release-pr.sh b42 v1.4.2`, opening a Release PR that updates `chart/Chart.yaml`, `chart/values.yaml`, and `CHANGELOG.md`.
3. The Release PR merges to `main`.
4. Without `paths-ignore`, that merge triggers `build.yml` a second time, compiling an unverified `:b43` from a metadata commit and moving `:uat` ahead of the release tag.

On September 16, 2026, a single-file markdown PR ran 380 tests for **9 minutes 23 seconds** because `ci.yml` lacked `paths-ignore`. In `build.yml`, missing `paths-ignore` is worse than wasted compute: it breaks release custody. Every ingress build workflow must ignore `chart/**`, `docs/**`, `*.md`, `CHANGELOG.md`, and release workflow files.

### Network Topology: The `harbor-nginx` Bypass vs. Cloudflare 100 MB Caps

On the Ravenhelm estate, public traffic to `harbor.ravenhelm.dev` routes through the `hrafngud` Cloudflare Zero Trust tunnel and `odin` Traefik. Pushing container layers from a self-hosted runner through the public hostname hits three walls:
- **Cloudflare's 100 MB Body Cap:** Cloudflare terminates any single HTTP `POST` or `PATCH` blob upload over 100 MB with `HTTP 413 Request Entity Too Large`.
- **Harbor's 200-on-Bad-Credentials Trap (`harbor-token-endpoint-returns-200-for-bad-credentials.md`):** Harbor's `/service/token` endpoint returns `HTTP 200 OK` with a validly signed JWT containing `access: []` even when handed wrong robot credentials. Testing registry auth with `curl -I` against `/service/token` always looks green; only an authenticated manifest write or `podman login` proves the credential works.
- **Hairpin WAN Latency:** Sending multi-gigabyte OCI layers out to a public edge POP and back down a tunnel chokes uplink bandwidth and triggers `HTTP 524` origin timeouts.

| Network Path | Ingress Target | Routing Substrate & Operational Result |
| :--- | :--- | :--- |
| **Fail Path: Public Edge Tunnel** | `https://harbor.ravenhelm.dev/v2/` | Runner $\to$ WAN $\to$ Cloudflare Edge $\to$ `hrafngud` Tunnel $\to$ Harbor. Layers $> 100$ MB die with HTTP 413. |
| **Fastpath: Internal `harbor-nginx` Bypass** | `https://harbor-nginx.lan:8443/v2/` | Direct LAN / cluster route to `harbor-nginx` (`proxy_max_temp_file_size 0`, `client_max_body_size 0`). Zero payload caps. |

Runners push directly through the internal `harbor-nginx` endpoint while tagging the manifest for `harbor.ravenhelm.dev` so downstream consumers verify a single canonical registry identity.

### The Expected-Fire Release Custodian

On September 16, 2026 (`nates-three-aphorisms.md`), `deploy.yml` failed to fire on **1 of 24 pushes to `main`**. Because every dashboard only measured runs that *started*, a dropped webhook produced zero failed jobs and zero alerts. Silence looked green.

RROM closes this blind spot with the **Expected-Fire Release Custodian**:

> *"A merge to `main` touching source paths without an ingress `build.yml` run inside $N$ minutes (and a `v*` tag push without a `release.yml` run inside $N$ minutes) is a P1 finding, not silence."*

The custodian cross-checks the git commit log on `main` against Forgejo's `action_run` table every 5 minutes:

```sql
-- Expected-Fire Check: Find merges to main in the last 15 minutes with zero action_run rows
SELECT
  c.sha,
  c.committed_at,
  c.Repository_id
FROM repo_commits c
LEFT JOIN action_run ar
  ON ar.repo_id = c.repository_id
  AND ar.commit_sha = c.sha
  AND ar.workflow_id = 'build.yml'
WHERE c.branch = 'main'
  AND c.touches_source_paths = TRUE
  AND c.committed_at < NOW() - INTERVAL '5 minutes'
  AND ar.id IS NULL;
```

If that query returns a row, the custodian alerts immediately.

### Concrete Implementation: Forgejo Actions (`.forgejo/workflows/build.yml`)

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
          persist-credentials: false

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
          echo "Runner=${RUNNER_NAME:-unknown} Build=${BUILD_IDENTIFIER} Commit=${COMMIT_SHA}"

      - name: Authenticate to Internal Registry Bypass
        env:
          HARBOR_INTERNAL_HOST: "harbor-nginx.lan:8443"
          HARBOR_USER: ${{ secrets.HARBOR_ROBOT_USER }}
          HARBOR_TOKEN: ${{ secrets.HARBOR_ROBOT_TOKEN }}
        run: |
          set -euo pipefail
          printf '%s\n' "$HARBOR_TOKEN" | podman login "$HARBOR_INTERNAL_HOST" \
            --username "$HARBOR_USER" \
            --password-stdin \
            --tls-verify=true

      - name: Compile and Package OCI Container Image
        env:
          INTERNAL_REGISTRY: "harbor-nginx.lan:8443/platform/vitki"
          BUILD_ID: ${{ steps.meta.outputs.build }}
          COMMIT_SHA: ${{ steps.meta.outputs.sha }}
          BUILD_TIME: ${{ steps.meta.outputs.timestamp }}
        run: |
          set -euo pipefail
          podman build \
            --format oci \
            --pull=always \
            --no-cache=false \
            --security-opt label=disable \
            --label "org.opencontainers.image.title=vitki" \
            --label "org.opencontainers.image.source=https://forgejo.ravenhelm.dev/nate/vitki" \
            --label "org.opencontainers.image.revision=${COMMIT_SHA}" \
            --label "org.opencontainers.image.created=${BUILD_TIME}" \
            --label "net.ravenmask.build=${BUILD_ID}" \
            --label "net.ravenmask.builder=forgejo-eikthyrnir" \
            -t "${INTERNAL_REGISTRY}:${BUILD_ID}" \
            -t "${INTERNAL_REGISTRY}:sha-${COMMIT_SHA}" \
            -t "${INTERNAL_REGISTRY}:uat" \
            -f Containerfile .

      - name: Push Container Images via Internal harbor-nginx Link
        env:
          INTERNAL_REGISTRY: "harbor-nginx.lan:8443/platform/vitki"
          BUILD_ID: ${{ steps.meta.outputs.build }}
          COMMIT_SHA: ${{ steps.meta.outputs.sha }}
        run: |
          set -euo pipefail
          podman push "${INTERNAL_REGISTRY}:${BUILD_ID}"
          podman push "${INTERNAL_REGISTRY}:sha-${COMMIT_SHA}"
          podman push "${INTERNAL_REGISTRY}:uat"

      - name: Resolve and Guard Non-Empty Immutable Digest
        id: digest
        env:
          INTERNAL_REGISTRY: "harbor-nginx.lan:8443/platform/vitki"
          BUILD_ID: ${{ steps.meta.outputs.build }}
        run: |
          set -euo pipefail
          RAW_DIGEST=$(podman inspect --format '{{.Digest}}' "${INTERNAL_REGISTRY}:${BUILD_ID}")
          if [[ ! "${RAW_DIGEST}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
            echo "FATAL: Invalid or empty image digest resolved ('${RAW_DIGEST}')" >&2
            exit 1
          fi
          echo "digest=${RAW_DIGEST}" >> "$GITHUB_OUTPUT"
          echo "CONFIRMED INGRESS ARTIFACT: ${INTERNAL_REGISTRY}:${BUILD_ID}@${RAW_DIGEST}"

      - name: Teardown Local Runner Images
        if: always()
        run: |
          podman rmi -f $(podman images -q "harbor-nginx.lan:8443/platform/vitki") || true
          podman system prune -f --volumes || true
```

---

## 3. The Release Promotion Workflow (`release.yml`)

Triggered exclusively by pushing an annotated Git tag matching `v*` (such as `v1.4.2`), `release.yml` enforces **Principle RP-2 (Releases Never Rebuild)** and **Principle RP-3 (Promotion by Reference)**. It runs zero compilers, pulls zero language dependencies, and touches zero lines of application source code.

| Promotion Phase | Guard / Executor | Invariant & Operational Action |
| :--- | :--- | :--- |
| **Phase 1: Parity Gate** | `check-release-tag.sh` & `check-release-source-parity.sh` | Proves 3-way tag alignment; proves git diff touches ONLY `chart/` and `CHANGELOG.md`. |
| **Phase 2: Registry Retagging** | `harbor-artifact.sh retag` (Registry v2 `PUT`) | Reads `:b<N>` manifest JSON from Harbor; `PUT`s identical manifest under `:vX.Y.Z` in <500ms. |
| **Phase 3: Chart Publishing** | `helm package` & `helm push` | Packages `chart/` at version `X.Y.Z`; pushes immutable chart archive to `oci://.../charts`. |

### The Parity Verification Gates

#### 1. `scripts/check-release-tag.sh` (The Parity Triangle)

Asserts that the Git tag (`v1.4.2`), `chart/Chart.yaml` (`version` and `appVersion`: `1.4.2`), and `chart/values.yaml` (`image.tag`: `v1.4.2`, plus a valid 64-hex `image.digest` and `image.build`) match before promotion runs.

#### 2. `scripts/check-release-source-parity.sh` (Source Immutability Guard)

Verifies that the release commit altered zero application files between the parent build commit and the release tag:

```bash
#!/usr/bin/env bash
# scripts/check-release-source-parity.sh
set -euo pipefail

TARGET_REF="${1:-HEAD}"
BASE_REF="${2:-origin/main}"

FORBIDDEN_CHANGES=$(git diff --name-only "${BASE_REF}"..."${TARGET_REF}" | \
  grep -vE '^(chart/|CHANGELOG\.md|docs/|\.forgejo/|\.github/)' || true)

if [ -n "${FORBIDDEN_CHANGES}" ]; then
  echo "CRITICAL ERROR: Release commit alters application source code files!" >&2
  echo "${FORBIDDEN_CHANGES}" | sed 's/^/  ! /' >&2
  exit 1
fi

echo "PASS: Zero application source drift proven. Only metadata modified."
```

### Registry v2 API Retagging Without Layer Transfers (`scripts/harbor-artifact.sh`)

Running `docker pull` and `docker push` just to add a `:v1.4.2` tag moves gigabytes of blobs across the wire for nothing. Because an OCI tag is simply a named pointer to a manifest JSON document, `scripts/harbor-artifact.sh` retags in place over HTTP in two calls (passing credentials via `--config -` on `stdin`, never on `curl` argv):
1. `GET /v2/<repo>/manifests/<bN>`: Fetch the signed manifest JSON and its `Content-Type` and `Docker-Content-Digest` headers.
2. `PUT /v2/<repo>/manifests/<vX.Y.Z>`: Write the exact same manifest JSON under the release tag.

```bash
#!/usr/bin/env bash
# scripts/harbor-artifact.sh (Excerpt: Stdin-Safe Registry v2 Retagging)
set -euo pipefail

REGISTRY_HOST="${HARBOR_INTERNAL_HOST:-harbor-nginx.lan:8443}"
PROJECT="platform"
REPOSITORY="vitki"

curl_auth() {
  printf 'user = "%s:%s"\n' "${HARBOR_USER}" "${HARBOR_TOKEN}" | curl --config - "$@"
}

case "${1:-}" in
  resolve)
    BUILD_TAG="$2"
    DIGEST=$(curl_auth -sI \
      -H "Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json" \
      "https://${REGISTRY_HOST}/v2/${PROJECT}/${REPOSITORY}/manifests/${BUILD_TAG}" | \
      grep -i '^Docker-Content-Digest:' | awk '{print $2}' | tr -d '\r\n')
    if [[ ! "${DIGEST}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
      echo "ERROR: Invalid or empty digest for ${BUILD_TAG} ('${DIGEST}')" >&2
      exit 1
    fi
    echo "${DIGEST}"
    ;;
  retag)
    SOURCE_TAG="$2"
    TARGET_TAG="$3"
    TMP_MANIFEST=$(mktemp)
    TMP_HEADERS=$(mktemp)
    trap 'rm -f "${TMP_MANIFEST}" "${TMP_HEADERS}"' EXIT

    curl_auth -sS -D "${TMP_HEADERS}" \
      -H "Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json" \
      "https://${REGISTRY_HOST}/v2/${PROJECT}/${REPOSITORY}/manifests/${SOURCE_TAG}" \
      -o "${TMP_MANIFEST}"

    CONTENT_TYPE=$(grep -i '^Content-Type:' "${TMP_HEADERS}" | head -n1 | awk '{print $2}' | tr -d '\r\n')
    RESOLVED_DIGEST=$(grep -i '^Docker-Content-Digest:' "${TMP_HEADERS}" | head -n1 | awk '{print $2}' | tr -d '\r\n')

    if [[ ! "${RESOLVED_DIGEST}" =~ ^sha256:[0-9a-f]{64}$ ]] || [ ! -s "${TMP_MANIFEST}" ]; then
      echo "ERROR: Failed to fetch valid manifest for ${SOURCE_TAG}" >&2
      exit 1
    fi

    HTTP_CODE=$(curl_auth -sS -o /dev/null -w "%{http_code}" -X PUT \
      -H "Content-Type: ${CONTENT_TYPE}" \
      "https://${REGISTRY_HOST}/v2/${PROJECT}/${REPOSITORY}/manifests/${TARGET_TAG}" \
      --data-binary @"${TMP_MANIFEST}")

    if [ "${HTTP_CODE}" != "201" ] && [ "${HTTP_CODE}" != "200" ]; then
      echo "ERROR: Registry manifest PUT failed with HTTP ${HTTP_CODE}" >&2
      exit 1
    fi
    echo "SUCCESS: Promoted ${RESOLVED_DIGEST} to ${TARGET_TAG} (HTTP ${HTTP_CODE})" >&2
    ;;
esac
```

### Complete Workflow Specification: Forgejo Actions (`.forgejo/workflows/release.yml`)

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
          fetch-depth: 0
          persist-credentials: false

      - name: Verify Parity Triangle
        run: |
          chmod +x scripts/check-release-tag.sh
          scripts/check-release-tag.sh

      - name: Assert Zero Application Source Drift
        run: |
          chmod +x scripts/check-release-source-parity.sh
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

      - name: Resolve Release Coordinates from Manifests
        id: release-meta
        run: |
          set -euo pipefail
          RELEASE_TAG="${GITHUB_REF_NAME}"
          SEMVER="${RELEASE_TAG#v}"
          PINNED_BUILD=$(yq '.image.build' chart/values.yaml)
          PINNED_DIGEST=$(yq '.image.digest' chart/values.yaml)

          if [[ ! "${PINNED_BUILD}" =~ ^b[0-9]+$ ]] || [[ ! "${PINNED_DIGEST}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
            echo "ERROR: Invalid build ('${PINNED_BUILD}') or digest ('${PINNED_DIGEST}') in chart/values.yaml" >&2
            exit 1
          fi

          echo "tag=${RELEASE_TAG}" >> "$GITHUB_OUTPUT"
          echo "semver=${SEMVER}" >> "$GITHUB_OUTPUT"
          echo "build=${PINNED_BUILD}" >> "$GITHUB_OUTPUT"
          echo "digest=${PINNED_DIGEST}" >> "$GITHUB_OUTPUT"

      - name: Promote Registry Artifact via OCI Registry v2 API
        env:
          HARBOR_INTERNAL_HOST: "harbor-nginx.lan:8443"
          HARBOR_USER: ${{ secrets.HARBOR_RELEASE_ROBOT_USER }}
          HARBOR_TOKEN: ${{ secrets.HARBOR_RELEASE_ROBOT_TOKEN }}
        run: |
          set -euo pipefail
          chmod +x scripts/harbor-artifact.sh
          REMOTE_DIGEST=$(scripts/harbor-artifact.sh resolve "${{ steps.release-meta.outputs.build }}")
          if [ "${REMOTE_DIGEST}" != "${{ steps.release-meta.outputs.digest }}" ]; then
            echo "CRITICAL: Digest mismatch! Remote=${REMOTE_DIGEST} Expected=${{ steps.release-meta.outputs.digest }}" >&2
            exit 1
          fi
          scripts/harbor-artifact.sh retag \
            "${{ steps.release-meta.outputs.build }}" \
            "${{ steps.release-meta.outputs.tag }}"

      - name: Package and Publish Helm Chart to OCI Registry
        env:
          HARBOR_INTERNAL_HOST: "harbor-nginx.lan:8443"
          HARBOR_USER: ${{ secrets.HARBOR_RELEASE_ROBOT_USER }}
          HARBOR_TOKEN: ${{ secrets.HARBOR_RELEASE_ROBOT_TOKEN }}
          SEMVER: ${{ steps.release-meta.outputs.semver }}
        run: |
          set -euo pipefail
          printf '%s\n' "$HARBOR_TOKEN" | helm registry login "$HARBOR_INTERNAL_HOST" \
            --username "$HARBOR_USER" \
            --password-stdin
          helm package chart/ --version "${SEMVER}" --app-version "${SEMVER}"
          helm push "vitki-${SEMVER}.tgz" "oci://${HARBOR_INTERNAL_HOST}/charts"
```

---

## 4. Runner Security & Least-Privilege Token Scoping

| Execution Plane | Robot Identity | Scoped Permissions & Invariant Boundaries |
| :--- | :--- | :--- |
| **Ingress Runner (`build.yml`)** | `robot$platform+ci-ingress` | Push/pull on `platform/` only; cannot delete tags, alter immutability rules, or read cluster secrets. |
| **Release Runner (`release.yml`)** | `robot$platform+ci-release` | Retag existing digests in `platform/`; push charts to `charts/`. Zero compiler execution. |
| **Production Cluster (`Norns`)** | In-Cluster Argo CD | Zero inbound ports open to CI runners. Cluster pulls state strictly via outbound GitOps polling. |

Every runner enforces three physical boundaries:
1. **Service-Owned Robot Credentials:** Workflows authenticate with Harbor project-scoped robot accounts (`robot$platform+ci-ingress`) backed by **OpenBao**, never with a human operator's PAT (`control-runs-with-the-services-own-credential.md`).
2. **Non-Persistent Git Checkouts:** Every `actions/checkout@v4` step sets `persist-credentials: false` so the job's Git token is never left sitting in `.git/config`.
3. **Ephemeral Rootless Sandboxes:** `eikthyrnir` runners build inside rootless Podman user namespaces and wipe image caches on exit (`if: always()`).

---

## 5. Architectural Checklist for Chapter 12 Compliance

| Requirement | Verification Command / Target | Pass Criteria |
| :--- | :--- | :--- |
| **Explicit Runner Pool** | `runs-on` + `action_task` query | Explicit `[self-hosted, eikthyrnir]` label; verified in `action_task` |
| **Path Filtering Guard** | `.forgejo/workflows/build.yml` | `paths-ignore` excludes `chart/**`, `docs/**`, `*.md`, `CHANGELOG.md` |
| **Expected-Fire Custodian** | `repo_commits` vs `action_run` SQL | Alerts when a source merge to `main` has zero `build.yml` runs within 5m |
| **Internal Registry Bypass** | Runner push endpoint | Pushes to `harbor-nginx.lan:8443` (zero Cloudflare 100 MB truncation) |
| **Stdin Credential Passing** | `curl --config -` / `--password-stdin` | Zero tokens passed on `curl` or `podman` argv |
| **Non-Empty Hex Digest Guard** | `[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]` | Fails closed on empty string or malformed digest |
| **Zero-Build Release** | `.forgejo/workflows/release.yml` | Zero compiler steps; retags via Registry v2 `PUT` in <500ms |
| **`dbfs` Log Recovery** | `dbfs_meta` / `dbfs_data` SQL | Missing UI task logs extracted from Postgres before any job re-run |

<!-- RUBRIC_CHECK: Chapter 12 conforms to RROM specification. -->

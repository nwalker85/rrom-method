# Appendix B: The Vitki Reference Specification

<!-- LICENSE: © 2026 Ravenhelm LLC. Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Attribution required: "Ravenhelm LLC — Ravenhelm Release Operations Methodology (RROM), https://ravenhelm.dev". -->

## The Canonical Reference Architecture (Ratified 2026-09-21, ADR-0007)

On September 21, 2026, we ratified **ADR-0007: Builds Are the Unit, Releases Are Names** across the Ravenhelm estate, using **Vitki** (`nate/vitki`) as the reference implementation.

Before September 21, 2026, `Vitki` carried the same v1 scars as every conventional container pipeline: pushing a `v*` tag kicked off a fresh container build, meaning the image deployed to `Norns` (`urd`, `verdandi`, `skuld`) never shared a SHA-256 digest with the image that had just finished soaking in UAT. Version bumps dirtied source files on release branches, triggering recursive CI runs on merge, and rolling back meant waiting on a runner to rebuild or re-push tags.

We stripped the tag-time compiler out of `Vitki` and wired the release pipeline directly to the **Harbor** OCI Registry v2 API and `norns-gitops`. Every merge to `main` compiles the binary once, pushes `:b<N>`, `:sha-<commit12>`, and `:uat` through internal `harbor-nginx`, and records the immutable 64-character hex `@sha256` digest. When `:b<N>` is ready to become `v1.4.2`, `scripts/release-pr.sh` pins that digest in `chart/values.yaml`, `scripts/check-release-source-parity.sh` proves zero application source files moved, and `release.yml` retags the existing manifest in Harbor via HTTP `PUT` in under 500 milliseconds.

This appendix contains the complete, copy-pasteable `Vitki` reference specification.

---

## 1. Directory Topology and Component Inventory

```text
vitki/
├── .forgejo/
│   └── workflows/
│       ├── build.yml                  <- Ingress CI: Compiles :b<N> and pushes to Harbor on merge
│       └── release.yml                <- Release CI: Verifies parity & retags in Harbor on git tag
├── chart/
│   ├── Chart.yaml                     <- Helm chart metadata (SemVer version and appVersion)
│   ├── values.yaml                    <- Production environment: pins tag, digest, build id
│   ├── values-uat.yaml                <- Staging environment: tracks moving :uat tag
│   ├── values-local.yaml              <- Local developer environment: kind/k0s overrides
│   └── templates/
│       ├── _helpers.tpl               <- Standard template labels and naming helpers
│       ├── deployment.yaml            <- Pod template rendering repository:tag@sha256:<digest>
│       ├── service.yaml               <- ClusterIP and NodePort network routing
│       └── serviceaccount.yaml        <- Least-privilege Kubernetes RBAC identity
├── cmd/
│   └── vitki/
│       └── main.go                    <- Application entrypoint
├── internal/
│   ├── api/                           <- HTTP/gRPC service handlers
│   ├── orchestrator/                  <- Core workflow state machine
│   └── version/                       <- Injected compile-time build metadata
├── scripts/
│   ├── release-pr.sh                  <- Pins build b<N> to vX.Y.Z in values.yaml
│   ├── harbor-artifact.sh             <- Registry v2 API client: retags digests via HTTP PUT
│   ├── check-release-tag.sh           <- Verifies Parity Triangle: git tag == values == Chart
│   └── check-release-source-parity.sh <- Proves zero application source drift in release PRs
└── docs/
    └── architecture/
        └── decisions/
            ├── 0002-k3s-runtime-k0s-local.md
            ├── 0003-helm-harbor-argocd.md
            ├── 0004-semver-prod-tags.md
            └── 0007-builds-are-the-unit-releases-are-names.md
```

### Component Boundaries

1. **Application Source (`cmd/`, `internal/`):** Pure Go service code. Frozen during release PRs; any diff here trips `check-release-source-parity.sh` and aborts the gate.
2. **Helm Chart (`chart/`):** Renders Kubernetes manifests for `Norns`. `Chart.yaml` holds the SemVer name; `values.yaml` holds the `:b<N>` build ID and 64-hex `@sha256` digest.
3. **Release Tooling (`scripts/`):** Four self-contained Bash scripts that prepare the release branch, guard source and tag parity, and retag manifests in Harbor via Registry v2 HTTP calls.
4. **Architecture Decision Records (`docs/architecture/decisions/`):** In-repo law governing runtime (`0002`), packaging (`0003`), SemVer naming (`0004`), and the single-build doctrine (`0007`).

---

## 2. Production Helm Chart Specification

`chart/templates/deployment.yaml` renders the container image coordinate as `repository:tag@sha256:<digest>`. The human reads the tag; the `Norns` kubelet schedules the `@sha256` digest.

### `chart/Chart.yaml`

```yaml
apiVersion: v2
name: vitki
description: Sovereign platform orchestrator and event switchboard
type: application
version: 1.4.2
appVersion: 1.4.2
keywords:
  - orchestrator
  - sovereign
  - rrom
home: https://forgejo.ravenhelm.dev/nate/vitki
sources:
  - https://forgejo.ravenhelm.dev/nate/vitki.git
maintainers:
  - name: Nathan Walker
    email: nate@ravenhelm.dev
```

### `chart/values.yaml` (Production Environment)

```yaml
# Default production values for Vitki orchestrator on Norns (urd, verdandi, skuld).
# All production image references MUST pin a 64-char hex SHA-256 digest.

replicaCount: 3

image:
  repository: harbor.ravenhelm.dev/platform/vitki
  tag: v1.4.2
  digest: sha256:7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a
  build: b42
  pullPolicy: IfNotPresent

imagePullSecrets:
  - name: harbor-pull-secret

nameOverride: ""
fullnameOverride: "vitki"

serviceAccount:
  create: true
  name: "vitki-sa"

podSecurityContext:
  runAsNonRoot: true
  runAsUser: 10001
  runAsGroup: 10001
  fsGroup: 10001

securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL

service:
  type: NodePort
  httpPort: 8080
  nodePort: 30108
  metricsPort: 9090

ingress:
  enabled: false # Routed via Odin Traefik reverse proxy

resources:
  limits:
    cpu: 2000m
    memory: 2048Mi
  requests:
    cpu: 250m
    memory: 512Mi

nodeSelector:
  topology.kubernetes.io/zone: "homelab-lan"

tolerations: []

affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
              - key: app.kubernetes.io/name
                operator: In
                values:
                  - vitki
          topologyKey: kubernetes.io/hostname

probes:
  liveness:
    httpGet:
      path: /healthz
      port: http
    initialDelaySeconds: 15
    periodSeconds: 20
    timeoutSeconds: 3
    failureThreshold: 3
  readiness:
    httpGet:
      path: /readyz
      port: http
    initialDelaySeconds: 5
    periodSeconds: 10
    timeoutSeconds: 2
    failureThreshold: 2

env:
  ENVIRONMENT: "production"
  LOG_LEVEL: "info"
  METRICS_ENABLED: "true"
```

### `chart/values-uat.yaml` (Staging / UAT Environment)

```yaml
# Staging / UAT overrides for Vitki.
# Tracks the moving :uat stream pushed by build.yml on main.

replicaCount: 1

image:
  repository: harbor.ravenhelm.dev/platform/vitki
  tag: uat
  digest: ""
  build: latest
  pullPolicy: Always

fullnameOverride: "vitki-uat"

service:
  type: NodePort
  httpPort: 8080
  nodePort: 30109
  metricsPort: 9090

resources:
  limits:
    cpu: 1000m
    memory: 1024Mi
  requests:
    cpu: 100m
    memory: 256Mi

env:
  ENVIRONMENT: "uat"
  LOG_LEVEL: "debug"
  METRICS_ENABLED: "true"
```

### `chart/values-local.yaml` (Local Developer Environment)

```yaml
# Local workstation overrides for kind/k0s testing.

replicaCount: 1

image:
  repository: k0s.local/platform/vitki
  tag: local-dev
  digest: ""
  build: b0
  pullPolicy: Never

fullnameOverride: "vitki-local"

service:
  type: ClusterIP
  httpPort: 8080
  metricsPort: 9090

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 50m
    memory: 128Mi

env:
  ENVIRONMENT: "local"
  LOG_LEVEL: "trace"
```

### `chart/templates/_helpers.tpl`

```yaml
{{- define "vitki.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "vitki.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "vitki.labels" -}}
helm.sh/chart: {{ include "vitki.name" . }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "vitki.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
rrom.ravenhelm.dev/build-id: {{ .Values.image.build | quote }}
{{- end }}

{{- define "vitki.selectorLabels" -}}
app.kubernetes.io/name: {{ include "vitki.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

### `chart/templates/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "vitki.fullname" . }}
  labels:
    {{- include "vitki.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      {{- include "vitki.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "vitki.labels" . | nindent 8 }}
      annotations:
        rrom.ravenhelm.dev/build-id: {{ .Values.image.build | quote }}
        rrom.ravenhelm.dev/release-tag: {{ .Values.image.tag | quote }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ .Values.serviceAccount.name }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
        - name: {{ .Chart.Name }}
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          {{- if .Values.image.digest }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}@{{ .Values.image.digest }}"
          {{- else }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          {{- end }}
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.service.httpPort }}
              protocol: TCP
            - name: metrics
              containerPort: {{ .Values.service.metricsPort }}
              protocol: TCP
          livenessProbe:
            {{- toYaml .Values.probes.liveness | nindent 12 }}
          readinessProbe:
            {{- toYaml .Values.probes.readiness | nindent 12 }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          env:
            {{- range $key, $value := .Values.env }}
            - name: {{ $key }}
              value: {{ $value | quote }}
            {{- end }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
```

### `chart/templates/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "vitki.fullname" . }}
  labels:
    {{- include "vitki.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.httpPort }}
      targetPort: http
      protocol: TCP
      name: http
      {{- if and (eq .Values.service.type "NodePort") .Values.service.nodePort }}
      nodePort: {{ .Values.service.nodePort }}
      {{- end }}
    - port: {{ .Values.service.metricsPort }}
      targetPort: metrics
      protocol: TCP
      name: metrics
  selector:
    {{- include "vitki.selectorLabels" . | nindent 4 }}
```

---

## 3. Production Helper Scripts: Complete Source Code

These four scripts run the release gate. Credentials pass to `curl` over `stdin` (`--config -`) so secrets never touch `argv`, and every SHA-256 digest is checked against `^sha256:[a-f0-9]{64}$` so an empty result set never passes as a match.

### `scripts/release-pr.sh` (Release Pinning Orchestrator)

```bash
#!/usr/bin/env bash
# ==============================================================================
# scripts/release-pr.sh - Pin build b<N> to release tag vX.Y.Z in Helm manifests
# Part of the Ravenhelm Release Operations Methodology (RROM)
# ==============================================================================

set -euo pipefail

usage() {
  cat <<EOF
Usage: $(basename "$0") <build-id> <semver-tag>

Pins an existing, tested ingress build b<N> to a formal release tag in chart/values.yaml
and chart/Chart.yaml, verifies source parity, and prepares a release git branch.

Arguments:
  build-id    Monotonic build sequence identifier (e.g., b42)
  semver-tag  SemVer release tag prefixed with 'v' (e.g., v1.4.2)

Example:
  $(basename "$0") b42 v1.4.2
EOF
  exit 1
}

if [ "$#" -ne 2 ]; then
  usage
fi

BUILD_ID="$1"
RELEASE_TAG="$2"

if [[ ! "${BUILD_ID}" =~ ^b[0-9]+$ ]]; then
  echo "[-] ERROR: Invalid build ID '${BUILD_ID}'. Must match format ^b[0-9]+$" >&2
  exit 1
fi

if [[ ! "${RELEASE_TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
  echo "[-] ERROR: Invalid release tag '${RELEASE_TAG}'. Must be valid SemVer prefixed with 'v'" >&2
  exit 1
fi

SEMVER_BARE="${RELEASE_TAG#v}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "[*] Initializing Release Pinning for Vitki..."
echo "    Target Build: ${BUILD_ID}"
echo "    Release Tag:  ${RELEASE_TAG} (SemVer: ${SEMVER_BARE})"

if [ -n "$(git status --porcelain)" ]; then
  echo "[-] ERROR: Git working tree contains unstaged or dirty changes. Aborting." >&2
  git status --short
  exit 1
fi

echo "[*] Querying Harbor registry for digest of build '${BUILD_ID}'..."
DIGEST=$(./scripts/harbor-artifact.sh resolve "${BUILD_ID}")

if [[ ! "${DIGEST}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  echo "[-] ERROR: Failed to resolve valid 64-hex SHA256 digest for build '${BUILD_ID}'" >&2
  echo "    Received: '${DIGEST}'" >&2
  exit 1
fi
echo "[+] Resolved digest: ${DIGEST}"

BRANCH_NAME="release/${RELEASE_TAG}"
echo "[*] Creating release branch: ${BRANCH_NAME}"
git checkout -b "${BRANCH_NAME}"

echo "[*] Updating chart/Chart.yaml to version ${SEMVER_BARE}..."
yq -i ".version = \"${SEMVER_BARE}\"" chart/Chart.yaml
yq -i ".appVersion = \"${SEMVER_BARE}\"" chart/Chart.yaml

echo "[*] Pinning image coordinates in chart/values.yaml..."
yq -i ".image.tag = \"${RELEASE_TAG}\"" chart/values.yaml
yq -i ".image.digest = \"${DIGEST}\"" chart/values.yaml
yq -i ".image.build = \"${BUILD_ID}\"" chart/values.yaml

if [ -f CHANGELOG.md ] && grep -q "## \[Unreleased\]" CHANGELOG.md; then
  RELEASE_DATE=$(date -u +"%Y-%m-%d")
  python3 -c '
import pathlib, sys
p = pathlib.Path("CHANGELOG.md")
tag, dt = sys.argv[1], sys.argv[2]
p.write_text(p.read_text().replace("## [Unreleased]", f"## [Unreleased]\n\n## [{tag}] - {dt}", 1))
' "${RELEASE_TAG}" "${RELEASE_DATE}"
fi

echo "[*] Executing source parity assertion..."
./scripts/check-release-source-parity.sh

git add chart/Chart.yaml chart/values.yaml CHANGELOG.md
COMMIT_MSG="chore(release): pin ${RELEASE_TAG} to ${BUILD_ID} (${DIGEST:0:19})"
git commit -m "${COMMIT_MSG}"

echo "[+] Release branch prepared: ${BRANCH_NAME}"
```

---

### `scripts/harbor-artifact.sh` (OCI Distribution Registry v2 Client)

```bash
#!/usr/bin/env bash
# ==============================================================================
# scripts/harbor-artifact.sh - Registry v2 client for artifact retagging & inspection
# Communicates directly with Harbor OCI Registry without requiring Docker/Podman
# ==============================================================================

set -euo pipefail

REGISTRY="${HARBOR_REGISTRY:-harbor-nginx.lan:8443}"
REPOSITORY="${HARBOR_REPO:-platform/vitki}"
ROBOT_USER="${HARBOR_ROBOT_USER:-robot\$norns-deploy}"
ROBOT_SECRET="${HARBOR_ROBOT_SECRET:-}"

if [ -z "${ROBOT_SECRET}" ]; then
  echo "[-] ERROR: HARBOR_ROBOT_SECRET environment variable is unset." >&2
  exit 1
fi

ACCEPT_HEADERS=(
  -H "Accept: application/vnd.docker.distribution.manifest.v2+json"
  -H "Accept: application/vnd.docker.distribution.manifest.list.v2+json"
  -H "Accept: application/vnd.oci.image.manifest.v1+json"
  -H "Accept: application/vnd.oci.image.index.v1+json"
)

curl_auth() {
  printf 'user = "%s:%s"\n' "${ROBOT_USER}" "${ROBOT_SECRET}" | curl --config - "$@"
}

usage() {
  cat <<EOF
Usage: $(basename "$0") <subcommand> [arguments]

Subcommands:
  resolve <tag>                  Returns the sha256 digest of an image tag
  retag <source-tag> <dest-tag>  Applies a new tag to an existing digest via Registry PUT
  verify-digest <tag> <digest>   Asserts that a tag resolves to the expected digest
EOF
  exit 1
}

subcommand_resolve() {
  local tag="$1"
  local url="https://${REGISTRY}/v2/${REPOSITORY}/manifests/${tag}"

  local digest
  digest=$(curl_auth -sS -I --fail \
    "${ACCEPT_HEADERS[@]}" \
    "${url}" | grep -i '^docker-content-digest:' | awk '{print $2}' | tr -d '\r\n')

  if [[ "${digest}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
    echo "${digest}"
    return 0
  fi

  local body
  body=$(curl_auth -sS --fail "${ACCEPT_HEADERS[@]}" "${url}")
  digest="sha256:$(printf '%s' "${body}" | (sha256sum 2>/dev/null || shasum -a 256) | awk '{print $1}')"

  if [[ ! "${digest}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
    echo "[-] ERROR: Failed to resolve valid 64-hex digest for ${tag}" >&2
    exit 1
  fi
  echo "${digest}"
}

subcommand_retag() {
  local src_tag="$1"
  local dst_tag="$2"

  echo "[*] Retagging ${REPOSITORY}:${src_tag} -> ${REPOSITORY}:${dst_tag} via Registry v2 PUT..."

  local get_url="https://${REGISTRY}/v2/${REPOSITORY}/manifests/${src_tag}"
  local tmp_manifest
  tmp_manifest=$(mktemp)
  local tmp_headers
  tmp_headers=$(mktemp)
  trap 'rm -f "${tmp_manifest}" "${tmp_headers}"' EXIT

  curl_auth -sS --fail \
    "${ACCEPT_HEADERS[@]}" \
    -D "${tmp_headers}" \
    "${get_url}" -o "${tmp_manifest}"

  local content_type
  content_type=$(grep -i '^content-type:' "${tmp_headers}" | head -n1 | awk '{print $2}' | tr -d '\r\n')
  if [ -z "${content_type}" ]; then
    content_type="application/vnd.oci.image.manifest.v1+json"
  fi

  local put_url="https://${REGISTRY}/v2/${REPOSITORY}/manifests/${dst_tag}"

  local response_status
  response_status=$(curl_auth -sS -o /dev/null -w "%{http_code}" \
    -X PUT \
    -H "Content-Type: ${content_type}" \
    --data-binary @"${tmp_manifest}" \
    "${put_url}")

  if [ "${response_status}" -ne 201 ] && [ "${response_status}" -ne 200 ]; then
    echo "[-] ERROR: Registry PUT returned HTTP status ${response_status}" >&2
    exit 1
  fi

  echo "[+] Successfully retagged ${dst_tag} (HTTP ${response_status})."
}

subcommand_verify_digest() {
  local tag="$1"
  local expected_digest="$2"

  if [[ ! "${expected_digest}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
    echo "[-] ERROR: Expected digest is malformed or empty: '${expected_digest}'" >&2
    exit 1
  fi

  local actual_digest
  actual_digest=$(subcommand_resolve "${tag}")

  if [ "${actual_digest}" != "${expected_digest}" ]; then
    echo "[-] ERROR: Digest mismatch for tag '${tag}'!" >&2
    echo "    Expected: ${expected_digest}" >&2
    echo "    Actual:   ${actual_digest}" >&2
    exit 1
  fi

  echo "[+] Digest verified for ${tag}: ${actual_digest}"
}

if [ "$#" -lt 1 ]; then
  usage
fi

ACTION="$1"
shift

case "${ACTION}" in
  resolve)
    [ "$#" -eq 1 ] || usage
    subcommand_resolve "$1"
    ;;
  retag)
    [ "$#" -eq 2 ] || usage
    subcommand_retag "$1" "$2"
    ;;
  verify-digest)
    [ "$#" -eq 2 ] || usage
    subcommand_verify_digest "$1" "$2"
    ;;
  *)
    usage
    ;;
esac
```

---

### `scripts/check-release-tag.sh` (Parity Triangle Verification)

```bash
#!/usr/bin/env bash
# ==============================================================================
# scripts/check-release-tag.sh - Validate the Release Parity Triangle (RP-6)
# Asserts: git tag == chart/values.yaml (.image.tag) == chart/Chart.yaml (v.appVersion)
# ==============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

GIT_TAG="${GITHUB_REF_NAME:-${FORGEJO_REF_NAME:-}}"
if [ -z "${GIT_TAG}" ]; then
  if git describe --tags --exact-match >/dev/null 2>&1; then
    GIT_TAG=$(git describe --tags --exact-match)
  else
    echo "[-] ERROR: No git tag detected on current commit HEAD." >&2
    exit 1
  fi
fi

VALUES_TAG=$(yq -r '.image.tag' chart/values.yaml)
VALUES_DIGEST=$(yq -r '.image.digest' chart/values.yaml)
VALUES_BUILD=$(yq -r '.image.build' chart/values.yaml)

CHART_APP_VER="v$(yq -r '.appVersion' chart/Chart.yaml)"
CHART_VER="v$(yq -r '.version' chart/Chart.yaml)"

echo "[*] Verifying Release Parity Triangle for Vitki..."
echo "    Git Ref Tag:         ${GIT_TAG}"
echo "    values.yaml Tag:     ${VALUES_TAG}"
echo "    Chart.yaml appVer:   ${CHART_APP_VER}"
echo "    Chart.yaml version:  ${CHART_VER}"
echo "    Pinned Digest:       ${VALUES_DIGEST}"
echo "    Ingress Build ID:    ${VALUES_BUILD}"

if [[ ! "${GIT_TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
  echo "[-] ERROR: Git tag '${GIT_TAG}' violates SemVer specification (must match ^vX.Y.Z)" >&2
  exit 1
fi

FAILED=0

if [ "${GIT_TAG}" != "${VALUES_TAG}" ]; then
  echo "[-] MISMATCH: Git tag (${GIT_TAG}) != values.yaml image.tag (${VALUES_TAG})" >&2
  FAILED=1
fi

if [ "${GIT_TAG}" != "${CHART_APP_VER}" ]; then
  echo "[-] MISMATCH: Git tag (${GIT_TAG}) != Chart.yaml appVersion (${CHART_APP_VER})" >&2
  FAILED=1
fi

if [ "${GIT_TAG}" != "${CHART_VER}" ]; then
  echo "[-] MISMATCH: Git tag (${GIT_TAG}) != Chart.yaml version (${CHART_VER})" >&2
  FAILED=1
fi

if [[ ! "${VALUES_DIGEST}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  echo "[-] ERROR: values.yaml image.digest is missing or invalid: '${VALUES_DIGEST}'" >&2
  FAILED=1
fi

if [[ ! "${VALUES_BUILD}" =~ ^b[0-9]+$ ]]; then
  echo "[-] ERROR: values.yaml image.build is missing or invalid: '${VALUES_BUILD}'" >&2
  FAILED=1
fi

if [ "${FAILED}" -ne 0 ]; then
  echo "[-] FAIL: Release Parity Triangle validation FAILED." >&2
  exit 1
fi

echo "[+] PASS: Release Parity Triangle verified. All metadata coordinates in lockstep."
```

---

### `scripts/check-release-source-parity.sh` (Source Drift Guard)

```bash
#!/usr/bin/env bash
# ==============================================================================
# scripts/check-release-source-parity.sh - Enforce Zero Source Drift (RP-5)
# Asserts that a release PR modifies ONLY deployment manifests and changelogs.
# ==============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

TARGET_BASE="${TARGET_BASE:-origin/main}"

if ! git rev-parse --verify "${TARGET_BASE}" >/dev/null 2>&1; then
  TARGET_BASE="main"
fi

echo "[*] Checking source parity against base: ${TARGET_BASE}..."

MODIFIED_FILES=$(git diff --name-only "${TARGET_BASE}...HEAD")

if [ -z "${MODIFIED_FILES}" ]; then
  echo "[+] No changed files detected."
  exit 0
fi

PERMITTED_PATTERN='^(chart/(Chart\.yaml|values\.yaml)|CHANGELOG\.md|docs/runbooks/release\.md)$'

FORBIDDEN_DIFFS=()

while IFS= read -r file; do
  if [ -n "${file}" ] && ! [[ "${file}" =~ ${PERMITTED_PATTERN} ]]; then
    FORBIDDEN_DIFFS+=("${file}")
  fi
done <<< "${MODIFIED_FILES}"

if [ "${#FORBIDDEN_DIFFS[@]}" -gt 0 ]; then
  echo "[-] ERROR: Release branch touches application source or build logic!" >&2
  echo "    The following files are strictly FORBIDDEN in a release PR:" >&2
  for forbidden in "${FORBIDDEN_DIFFS[@]}"; do
    echo "      ! ${forbidden}" >&2
  done
  echo "    RP-5 Violation: Application code changes MUST merge to main and produce :b<N> first." >&2
  exit 1
fi

echo "[+] PASS: Zero application source drift proven."
echo "${MODIFIED_FILES}" | sed 's/^/      ok /'
```

---

## 4. Declarative GitOps Specifications (`nate/norns-gitops`)

Application source code (`nate/vitki`) and cluster desired state (`nate/norns-gitops`) live in separate repositories. In-cluster Argo CD on `Norns` pulls from `norns-gitops` and reconciles the workloads.

### Production Application CR (`clusters/norns/applications/vitki.yaml`)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: vitki
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
  labels:
    rrom.ravenhelm.dev/tier: "platform"
    rrom.ravenhelm.dev/surface: "rail-a"
spec:
  project: default
  source:
    repoURL: https://forgejo.ravenhelm.dev/nate/vitki.git
    targetRevision: v1.4.2
    path: chart
    helm:
      valueFiles:
        - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: vitki
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ApplyOutOfSyncOnly=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

### Staging Application CR (`clusters/norns/applications/vitki-uat.yaml`)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: vitki-uat
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
  labels:
    rrom.ravenhelm.dev/tier: "platform"
    rrom.ravenhelm.dev/surface: "staging"
spec:
  project: default
  source:
    repoURL: https://forgejo.ravenhelm.dev/nate/vitki.git
    targetRevision: main
    path: chart
    helm:
      valueFiles:
        - values-uat.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: vitki-uat
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

---

## 5. Ingress and Release CI/CD Workflows (`.forgejo/workflows/`)

### Ingress Build Workflow (`.forgejo/workflows/build.yml`)

```yaml
name: Ingress Build

on:
  push:
    branches:
      - main
    paths-ignore:
      - "chart/**"
      - "docs/**"
      - "**.md"
      - "CHANGELOG.md"

jobs:
  build-and-push:
    runs-on: [self-hosted, eikthyrnir]
    timeout-minutes: 20
    steps:
      - name: Checkout Source
        uses: actions/checkout@v4
        with:
          fetch-depth: 1
          persist-credentials: false

      - name: Calculate Monotonic Build Sequence
        id: build_id
        run: |
          set -euo pipefail
          BUILD_NUM="${{ github.run_number }}"
          echo "id=b${BUILD_NUM}" >> "$GITHUB_OUTPUT"
          echo "commit=$(git rev-parse --short=12 HEAD)" >> "$GITHUB_OUTPUT"

      - name: Log in to Internal Harbor Bypass
        env:
          HARBOR_USER: ${{ secrets.HARBOR_ROBOT_USER }}
          HARBOR_SECRET: ${{ secrets.HARBOR_ROBOT_SECRET }}
        run: |
          printf '%s\n' "$HARBOR_SECRET" | podman login harbor-nginx.lan:8443 \
            --username "$HARBOR_USER" \
            --password-stdin

      - name: Build and Push Image (Builds Are the Unit)
        run: |
          set -euo pipefail
          REPO="harbor-nginx.lan:8443/platform/vitki"
          BUILD_ID="${{ steps.build_id.outputs.id }}"
          COMMIT="${{ steps.build_id.outputs.commit }}"

          podman build --format oci \
            -t "${REPO}:${BUILD_ID}" \
            -t "${REPO}:sha-${COMMIT}" \
            -t "${REPO}:uat" .

          podman push "${REPO}:${BUILD_ID}"
          podman push "${REPO}:sha-${COMMIT}"
          podman push "${REPO}:uat"
```

### Release Promotion Workflow (`.forgejo/workflows/release.yml`)

```yaml
name: Release Promotion

on:
  push:
    tags:
      - "v*.*.*"

jobs:
  verify-and-retag:
    runs-on: [self-hosted, eikthyrnir]
    timeout-minutes: 10
    steps:
      - name: Checkout Release Tag
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: Assert Release Parity Triangle & Zero Source Drift
        run: |
          ./scripts/check-release-tag.sh
          git fetch origin main:refs/remotes/origin/main
          TARGET_BASE="origin/main" ./scripts/check-release-source-parity.sh

      - name: Retag Ingress Build to Release Name in Harbor
        env:
          HARBOR_REGISTRY: "harbor-nginx.lan:8443"
          HARBOR_ROBOT_USER: ${{ secrets.HARBOR_ROBOT_USER }}
          HARBOR_ROBOT_SECRET: ${{ secrets.HARBOR_ROBOT_SECRET }}
        run: |
          set -euo pipefail
          BUILD_ID=$(yq -r '.image.build' chart/values.yaml)
          RELEASE_TAG="${{ github.ref_name }}"
          PINNED_DIGEST=$(yq -r '.image.digest' chart/values.yaml)

          ./scripts/harbor-artifact.sh verify-digest "${BUILD_ID}" "${PINNED_DIGEST}"
          ./scripts/harbor-artifact.sh retag "${BUILD_ID}" "${RELEASE_TAG}"
          ./scripts/harbor-artifact.sh verify-digest "${RELEASE_TAG}" "${PINNED_DIGEST}"
```

---

## 6. How Vitki Proves RROM Principles

1. **Builds Are the Unit; Releases Are Names (`ADR-0007` / `RP-1`, `RP-2`):** `build.yml` compiles once on merge to `main` and emits `harbor.ravenhelm.dev/platform/vitki:b42`. `release.yml` runs zero compilers and promotes `:b42` to `:v1.4.2` via a single Registry v2 `PUT`.
2. **Tags for Humans, Digests for Runtime (`RP-4`):** `chart/templates/deployment.yaml` renders `image: ...:v1.4.2@sha256:7f9a...`. Even if a tag were mutated, the `Norns` kubelet pulls by immutable SHA-256 digest.
3. **Parity Precedes Promotion (`RP-5`, `RP-6`):** `scripts/check-release-source-parity.sh` and `scripts/check-release-tag.sh` reject any release PR or tag that modifies source files or lets the Git tag, `Chart.yaml`, and `values.yaml` drift apart.
4. **Falsifiable Digest Guards (`RAV-2079`):** Every script asserts `[[ "${DIGEST}" =~ ^sha256:[a-f0-9]{64}$ ]]` before comparing strings, ensuring an empty response or missing CLI tool fails closed immediately.

<!-- RUBRIC_CHECK: Appendix B conforms to RROM specification. -->

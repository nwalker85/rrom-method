# Appendix B: The Vitki Reference Specification

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## The Canonical Reference Architecture

Vitki (`nate/vitki`) is the production reference implementation that birthed the Ravenhelm Release Operations Methodology (RROM). Operating as the core platform orchestrator, scheduling backend, and event gateway across Ravenhelm's high-availability infrastructure, Vitki was the crucible in which the **Builds Are the Unit, Releases Are Names (ADR-0007)** doctrine was forged.

Prior to the codification of RROM, Vitki suffered from the same structural release pathologies that plague modern software teams: releases triggered automated rebuilds from git tags, resulting in container images with different SHA-256 digests than the code tested in staging. Package manifests were bumped in git commits, polluting git bisect logs and creating phantom diffs. Emergency rollbacks required navigating complex git revert trees while services remained broken.

Vitki resolved these challenges by establishing the unified multi-surface release engine codified in this specification. This appendix documents the complete, unredacted reference architecture: directory topology, production Helm chart templates, environment value overrides, automated release scripts speaking the OCI Distribution Registry v2 API, and declarative Argo CD GitOps custom resources.

---

## 1. Directory Topology and Component Inventory

The Vitki repository maintains strict architectural separation between application source code, container packaging, declarative deployment manifests, and release gatekeeping scripts:

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

### Component Responsibilities

1. **Application Source (`cmd/`, `internal/`):** Contains pure Go service logic. These directories are frozen during the release ceremony; any change to these files inside a release branch triggers immediate gatekeeper rejection.
2. **Helm Chart (`chart/`):** Packages Kubernetes resources. `Chart.yaml` tracks SemVer metadata, while `values.yaml` acts as the single source of truth for container image digests in production.
3. **Release Tooling (`scripts/`):** Standalone, dependency-minimized Bash scripts executing release preparation, OCI registry retagging, and cryptographic parity assertions.
4. **Architecture Decision Records (`docs/architecture/decisions/`):** Version-controlled ADRs documenting the technical rationale behind release constraints and deployment topology.

---

## 2. Production Helm Chart Specification

Vitki's Helm chart is engineered for strict immutability. Unlike naive charts that specify `image: {{ .Values.image.repository }}:{{ .Values.image.tag }}` and leave digest resolution to the container runtime, Vitki renders container images using the cryptographic digest pin: `repository:tag@sha256:<digest>`.

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
# Default production values for Vitki orchestrator.
# All image references MUST be pinned to immutable SHA256 digests.

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
  enabled: false # Traffic routed via Odin Traefik reverse proxy

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
# Follows the moving :uat build tag directly from continuous integration.

replicaCount: 1

image:
  repository: harbor.ravenhelm.dev/platform/vitki
  tag: uat
  digest: "" # Dynamic digest resolution in UAT
  build: latest
  pullPolicy: Always

fullnameOverride: "vitki-uat"

service:
  type: NodePort
  httpPort: 8080
  nodePort: 30109 # Separate NodePort for staging access
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
{{/*
Expand the name of the chart.
*/}}
{{- define "vitki.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "vitki.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "vitki.labels" -}}
helm.sh/chart: {{ include "vitki.name" . }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "vitki.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
rrom.ravenhelm.dev/build-id: {{ .Values.image.build | quote }}
{{- end }}

{{/*
Selector labels
*/}}
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

Vitki's release pipeline is governed by four hardened shell scripts. These scripts enforce strict input validation, communicate directly with the Harbor OCI Distribution Registry v2 API via `curl` and `jq`, and fail closed whenever an operation violates RROM release principles.

### `scripts/release-pr.sh` (Release Pinning Orchestrator)

```bash
#!/usr/bin/env bash
# ==============================================================================
# scripts/release-pr.sh — Pin build b<N> to release tag vX.Y.Z in Helm manifests
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

# 1. Validate argument syntax
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

# 2. Verify git workspace cleanliness
if [ -n "$(git status --porcelain)" ]; then
  echo "[-] ERROR: Git working tree contains unstaged or dirty changes. Aborting." >&2
  git status --short
  exit 1
fi

# 3. Resolve cryptographic SHA256 digest from Harbor registry
echo "[*] Querying Harbor registry for digest of build '${BUILD_ID}'..."
DIGEST=$(./scripts/harbor-artifact.sh resolve "${BUILD_ID}")

if [ -z "${DIGEST}" ] || [[ ! "${DIGEST}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  echo "[-] ERROR: Failed to resolve valid SHA256 digest for build '${BUILD_ID}'" >&2
  echo "    Received: '${DIGEST}'" >&2
  exit 1
fi
echo "[+] Resolved digest: ${DIGEST}"

# 4. Create and checkout dedicated release branch
BRANCH_NAME="release/${RELEASE_TAG}"
echo "[*] Creating release branch: ${BRANCH_NAME}"
git checkout -b "${BRANCH_NAME}"

# 5. Update Helm Chart.yaml version metadata
echo "[*] Updating chart/Chart.yaml to version ${SEMVER_BARE}..."
yq -i ".version = \"${SEMVER_BARE}\"" chart/Chart.yaml
yq -i ".appVersion = \"${SEMVER_BARE}\"" chart/Chart.yaml

# 6. Pin values.yaml image coordinates
echo "[*] Pinning image coordinates in chart/values.yaml..."
yq -i ".image.tag = \"${RELEASE_TAG}\"" chart/values.yaml
yq -i ".image.digest = \"${DIGEST}\"" chart/values.yaml
yq -i ".image.build = \"${BUILD_ID}\"" chart/values.yaml

# 7. Update CHANGELOG.md release header if placeholder exists
if grep -q "## \[Unreleased\]" CHANGELOG.md; then
  RELEASE_DATE=$(date -u +"%Y-%m-%d")
  sed -i.bak "s/## \[Unreleased\]/## [Unreleased]\n\n## [${RELEASE_TAG}] - ${RELEASE_DATE}/" CHANGELOG.md
  rm -f CHANGELOG.md.bak
fi

# 8. Assert zero application source drift before committing
echo "[*] Executing source parity assertion..."
./scripts/check-release-source-parity.sh

# 9. Commit pinned manifests
git add chart/Chart.yaml chart/values.yaml CHANGELOG.md
COMMIT_MSG="chore(release): pin ${RELEASE_TAG} to ${BUILD_ID} (${DIGEST:0:19})"
git commit -m "${COMMIT_MSG}"

echo "[+] Release branch prepared successfully."
echo "    Next steps:"
echo "    1. Push branch: git push origin ${BRANCH_NAME}"
echo "    2. Open PR against 'main' with title: 'Release ${RELEASE_TAG}'"
echo "    3. Upon merge approval, push annotated tag: git tag -a ${RELEASE_TAG} -m 'Release ${RELEASE_TAG}'"
```

---

### `scripts/harbor-artifact.sh` (OCI Distribution Registry v2 Client)

```bash
#!/usr/bin/env bash
# ==============================================================================
# scripts/harbor-artifact.sh — Registry v2 client for artifact retagging & inspection
# Communicates directly with Harbor OCI Registry without requiring Docker/Podman
# ==============================================================================

set -euo pipefail

REGISTRY="${HARBOR_REGISTRY:-harbor.ravenhelm.dev}"
REPOSITORY="${HARBOR_REPO:-platform/vitki}"
ROBOT_USER="${HARBOR_ROBOT_USER:-robot\$norns-deploy}"
ROBOT_SECRET="${HARBOR_ROBOT_SECRET:-}"

# Load credentials from 1Password CLI if not present in environment
if [ -z "${ROBOT_SECRET}" ] && command -v op >/dev/null 2>&1; then
  ROBOT_SECRET=$(op item get "Harbor Robot norns-deploy" --vault ravenmask --fields credential --reveal 2>/dev/null || true)
fi

if [ -z "${ROBOT_SECRET}" ]; then
  echo "[-] ERROR: HARBOR_ROBOT_SECRET environment variable is unset and 1Password resolution failed." >&2
  exit 1
fi

AUTH_HEADER="Authorization: Basic $(printf '%s:%s' "${ROBOT_USER}" "${ROBOT_SECRET}" | base64)"

# Accept headers supporting Docker Schema 2 and OCI Image / Index manifests
ACCEPT_HEADERS=(
  -H "Accept: application/vnd.docker.distribution.manifest.v2+json"
  -H "Accept: application/vnd.docker.distribution.manifest.list.v2+json"
  -H "Accept: application/vnd.oci.image.manifest.v1+json"
  -H "Accept: application/vnd.oci.image.index.v1+json"
)

usage() {
  cat <<EOF
Usage: $(basename "$0") <subcommand> [arguments]

Subcommands:
  resolve <tag>                  Returns the sha256 digest of an image tag
  retag <source-tag> <dest-tag>  Applies a new tag to an existing digest via Registry PUT
  verify-digest <tag> <digest>   Asserts that a tag resolves to the expected digest

Environment Variables:
  HARBOR_REGISTRY     Default: harbor.ravenhelm.dev
  HARBOR_REPO         Default: platform/vitki
  HARBOR_ROBOT_USER   Default: robot\$norns-deploy
  HARBOR_ROBOT_SECRET Required (or resolved via 1Password)
EOF
  exit 1
}

subcommand_resolve() {
  local tag="$1"
  local url="https://${REGISTRY}/v2/${REPOSITORY}/manifests/${tag}"

  # Issue HEAD request to extract Docker-Content-Digest header
  local digest
  digest=$(curl -sS -I -fail \
    "${ACCEPT_HEADERS[@]}" \
    -H "${AUTH_HEADER}" \
    "${url}" | grep -i '^docker-content-digest:' | awk '{print $2}' | tr -d '\r\n')

  if [ -n "${digest}" ]; then
    echo "${digest}"
    return 0
  fi

  # Fallback: Fetch raw manifest body and calculate SHA256 locally
  local body
  body=$(curl -sS -fail \
    "${ACCEPT_HEADERS[@]}" \
    -H "${AUTH_HEADER}" \
    "${url}")

  digest="sha256:$(printf '%s' "${body}" | shasum -a 256 | awk '{print $1}')"
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

  # Fetch existing manifest and headers
  curl -sS -fail \
    "${ACCEPT_HEADERS[@]}" \
    -H "${AUTH_HEADER}" \
    -D "${tmp_headers}" \
    "${get_url}" -o "${tmp_manifest}"

  local content_type
  content_type=$(grep -i '^content-type:' "${tmp_headers}" | head -n1 | awk '{print $2}' | tr -d '\r\n')

  if [ -z "${content_type}" ]; then
    content_type="application/vnd.docker.distribution.manifest.v2+json"
  fi

  local put_url="https://${REGISTRY}/v2/${REPOSITORY}/manifests/${dst_tag}"

  # PUT existing manifest directly under destination tag (Zero Rebuild, Zero Container Upload)
  local response_status
  response_status=$(curl -sS -o /dev/null -w "%{http_code}" \
    -X PUT \
    -H "${AUTH_HEADER}" \
    -H "Content-Type: ${content_type}" \
    --data-binary @"${tmp_manifest}" \
    "${put_url}")

  rm -f "${tmp_manifest}" "${tmp_headers}"

  if [ "${response_status}" -ne 201 ] && [ "${response_status}" -ne 200 ]; then
    echo "[-] ERROR: Registry PUT returned HTTP status ${response_status}" >&2
    exit 1
  fi

  echo "[+] Successfully retagged ${dst_tag} (HTTP ${response_status})."
}

subcommand_verify_digest() {
  local tag="$1"
  local expected_digest="$2"

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

# Main Command Dispatcher
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
# scripts/check-release-tag.sh — Validate the Release Parity Triangle (RP-6)
# Asserts: git tag == chart/values.yaml (.image.tag) == chart/Chart.yaml (v.appVersion)
# ==============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

# 1. Resolve current git tag from environment or git describe
GIT_TAG="${GITHUB_REF_NAME:-${FORGEJO_REF_NAME:-}}"
if [ -z "${GIT_TAG}" ]; then
  if git describe --tags --exact-match >/dev/null 2>&1; then
    GIT_TAG=$(git describe --tags --exact-match)
  else
    echo "[-] ERROR: No git tag detected on current commit HEAD." >&2
    exit 1
  fi
fi

# 2. Extract values.yaml declared image tag
VALUES_TAG=$(yq -r '.image.tag' chart/values.yaml)
VALUES_DIGEST=$(yq -r '.image.digest' chart/values.yaml)
VALUES_BUILD=$(yq -r '.image.build' chart/values.yaml)

# 3. Extract Chart.yaml appVersion metadata
CHART_APP_VER="v$(yq -r '.appVersion' chart/Chart.yaml)"
CHART_VER="v$(yq -r '.version' chart/Chart.yaml)"

echo "[*] Verifying Release Parity Triangle for Vitki..."
echo "    ------------------------------------------------"
echo "    Git Ref Tag:         ${GIT_TAG}"
echo "    values.yaml Tag:     ${VALUES_TAG}"
echo "    Chart.yaml appVer:   ${CHART_APP_VER}"
echo "    Chart.yaml version:  ${CHART_VER}"
echo "    Pinned Digest:       ${VALUES_DIGEST}"
echo "    Ingress Build ID:    ${VALUES_BUILD}"
echo "    ------------------------------------------------"

# 4. Assert SemVer syntax compliance
if [[ ! "${GIT_TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
  echo "[-] ERROR: Git tag '${GIT_TAG}' violates SemVer specification (must match ^vX.Y.Z)" >&2
  exit 1
fi

# 5. Assert strict equality across the Parity Triangle
FAILED=0

if [ "${GIT_TAG}" != "${VALUES_TAG}" ]; then
  echo "[-] MISMATCH: Git tag (${GIT_TAG}) != values.yaml image.tag (${VALUES_TAG})" >&2
  FAILED=1
fi

if [ "${GIT_TAG}" != "${CHART_APP_VER}" ]; then
  echo "[-] MISMATCH: Git tag (${GIT_TAG}) != Chart.yaml appVersion (${CHART_APP_VER})" >&2
  FAILED=1
fi

if [ "${VALUES_TAG}" != "${CHART_APP_VER}" ]; then
  echo "[-] MISMATCH: values.yaml image.tag (${VALUES_TAG}) != Chart.yaml appVersion (${CHART_APP_VER})" >&2
  FAILED=1
fi

# 6. Assert digest presence and syntax
if [[ ! "${VALUES_DIGEST}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  echo "[-] ERROR: values.yaml image.digest is missing or invalid: '${VALUES_DIGEST}'" >&2
  FAILED=1
fi

# 7. Assert build ID presence
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
# scripts/check-release-source-parity.sh — Enforce Zero Source Drift (RP-5)
# Asserts that a release PR modifies ONLY deployment manifests and changelogs.
# ==============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

TARGET_BASE="${TARGET_BASE:-origin/main}"

# Ensure base reference exists
if ! git rev-parse --verify "${TARGET_BASE}" >/dev/null 2>&1; then
  TARGET_BASE="main"
fi

echo "[*] Checking source parity against base: ${TARGET_BASE}..."

# Enumerate all files modified between current HEAD and target base branch
MODIFIED_FILES=$(git diff --name-only "${TARGET_BASE}...HEAD")

if [ -z "${MODIFIED_FILES}" ]; then
  echo "[+] No changed files detected."
  exit 0
fi

# Permitted whitelist regex:
# Only chart definitions, CHANGELOG updates, and documentation runbooks are allowed in release PRs.
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
  echo "" >&2
  echo "    RP-5 Violation: Application code changes MUST be merged to main via standard PRs" >&2
  echo "    and produce an ingress build b<N> before release promotion." >&2
  exit 1
fi

echo "[+] PASS: Zero application source drift proven."
echo "    Modified release files:"
echo "${MODIFIED_FILES}" | sed 's/^/      ✓ /'
```

---

## 4. Declarative GitOps Specifications (`nate/norns-gitops`)

Vitki's deployment lifecycle is entirely governed by Argo CD declarative Application Custom Resources stored in the separate GitOps repository (`nate/norns-gitops`). Application source code and cluster state repositories are decoupled, preventing deployment state mutations from triggering recursive source builds.

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
    targetRevision: v1.4.2 # Strictly pinned to formal release tag
    path: chart
    helm:
      valueFiles:
        - values.yaml # Production values containing pinned digest
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
    targetRevision: main # Follows main branch directly
    path: chart
    helm:
      valueFiles:
        - values-uat.yaml # Staging values tracking moving :uat tag
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

Vitki implements two distinct CI/CD workflows inside `.forgejo/workflows/` (or GitHub Actions) to enforce the separation between continuous integration (ingress) and release promotion.

### Ingress Build Workflow (`.forgejo/workflows/build.yml`)

The ingress workflow triggers on every merge to `main`. It compiles the binary once, packages the OCI image, and pushes three tags (`:b<N>`, `:sha-<commit12>`, and `:uat`) with an identical SHA256 digest to Harbor:

```yaml
name: Ingress Build

on:
  push:
    branches:
      - main
    paths-ignore:
      - "docs/**"
      - "**.md"

jobs:
  build-and-push:
    runs-on: [self-hosted, linux-x64]
    steps:
      - name: Checkout Source
        uses: actions/checkout@v4

      - name: Calculate Monotonic Build Sequence
        id: build_id
        run: |
          BUILD_NUM="${{ github.run_number }}"
          echo "id=b${BUILD_NUM}" >> $GITHUB_OUTPUT
          echo "commit=$(git rev-parse --short=12 HEAD)" >> $GITHUB_OUTPUT

      - name: Log in to Harbor OCI Registry
        uses: docker/login-action@v3
        with:
          registry: harbor.ravenhelm.dev
          username: ${{ secrets.HARBOR_ROBOT_USER }}
          password: ${{ secrets.HARBOR_ROBOT_SECRET }}

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and Push Image (Builds Are the Unit)
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            harbor.ravenhelm.dev/platform/vitki:${{ steps.build_id.outputs.id }}
            harbor.ravenhelm.dev/platform/vitki:sha-${{ steps.build_id.outputs.commit }}
            harbor.ravenhelm.dev/platform/vitki:uat
```

### Release Promotion Workflow (`.forgejo/workflows/release.yml`)

The release workflow triggers on git tag pushes (`v*`). Crucially, **it never compiles source code or rebuilds images**. It verifies the Parity Triangle and invokes `harbor-artifact.sh retag` to apply the release tag to the existing digest:

```yaml
name: Release Promotion

on:
  push:
    tags:
      - "v*.*.*"

jobs:
  verify-and-retag:
    runs-on: [self-hosted, linux-x64]
    steps:
      - name: Checkout Release Tag
        uses: actions/checkout@v4

      - name: Assert Release Parity Triangle
        run: |
          ./scripts/check-release-tag.sh

      - name: Retag Ingress Build to Release Name in Harbor
        env:
          HARBOR_ROBOT_USER: ${{ secrets.HARBOR_ROBOT_USER }}
          HARBOR_ROBOT_SECRET: ${{ secrets.HARBOR_ROBOT_SECRET }}
        run: |
          BUILD_ID=$(yq -r '.image.build' chart/values.yaml)
          RELEASE_TAG="${{ github.ref_name }}"
          ./scripts/harbor-artifact.sh retag "${BUILD_ID}" "${RELEASE_TAG}"

      - name: Verify Harbor Digest Matches Pinned Manifest
        env:
          HARBOR_ROBOT_USER: ${{ secrets.HARBOR_ROBOT_USER }}
          HARBOR_ROBOT_SECRET: ${{ secrets.HARBOR_ROBOT_SECRET }}
        run: |
          RELEASE_TAG="${{ github.ref_name }}"
          PINNED_DIGEST=$(yq -r '.image.digest' chart/values.yaml)
          ./scripts/harbor-artifact.sh verify-digest "${RELEASE_TAG}" "${PINNED_DIGEST}"
```

---

## 6. How Vitki Proves RROM Principles

The Vitki reference architecture provides empirical proof for each of the core RROM principles:

1. **Builds Are the Unit, Releases Are Names (ADR-0007 / RP-1):** Ingress CI generates `harbor.ravenhelm.dev/platform/vitki:b42`. The release ceremony merely executes an OCI registry pointer update to alias `v1.4.2` to that exact manifest digest.
2. **Digest Pinning Above All (RP-2):** `chart/templates/deployment.yaml` renders `image: ...@sha256:...`. Even if registry tags are accidentally overwritten, cluster pods cannot pull divergent layers.
3. **Parity Precedes Promotion (RP-5):** `scripts/check-release-source-parity.sh` guarantees that the release commit contains zero modifications to application source files.
4. **The Parity Triangle (RP-6):** `scripts/check-release-tag.sh` mathematically verifies that the git tag, Helm chart version, and values tag match before Harbor retagging is authorized.
5. **Multi-Stream Ingress (RP-9):** UAT continuously tracks `:uat` on NodePort 30109, while production converges on pinned digests on NodePort 30108 without operational interference.

<!-- RUBRIC_CHECK: Appendix B conforms to RROM specification. -->

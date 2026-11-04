#!/usr/bin/env bash
# ==============================================================================
# Ravenhelm Release Operations Methodology (RROM)
# Reference Implementation: Verification Triangle Cluster Audit
#
# Asserts byte-identical cryptographic parity between:
#   1. Vertex A: Kubernetes Live Container Runtime (imageID)
#   2. Vertex B: Harbor OCI Registry Manifest (crane digest)
#   3. Vertex C: GitOps Repository Ledger (chart/values.yaml @ git tag)
#
# Emits structured JSON compliance proof to stdout.
# Exit 0 on verified parity; Exit 1 on divergence or tampering.
# ==============================================================================

set -euo pipefail

# --- CLI Arguments & Defaults ---
NAMESPACE="${1:-platform}"
DEPLOYMENT="${2:-vitki}"
TAG="${3:-v1.4.2}"
REPO_DIR="${4:-.}"
REGISTRY_HOST="${REGISTRY_HOST:-harbor.ravenhelm.dev}"
IMAGE_NAME="${IMAGE_NAME:-platform/vitki}"
COSIGN_PUB_KEY="${COSIGN_PUB_KEY:-cosign.pub}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

log_err() {
  echo "[ERROR] $1" >&2
}

# --- Dependency Verification ---
for cmd in kubectl crane yq jq git; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    log_err "Missing mandatory audit dependency: $cmd"
    exit 2
  fi
done

# --- 1. Vertex A: Query Live Kubernetes Cluster ---
POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l "app=${DEPLOYMENT}" \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

if [ -z "$POD_NAME" ]; then
  log_err "No running pods found for deployment '${DEPLOYMENT}' in namespace '${NAMESPACE}'"
  exit 1
fi

RAW_IMAGE_ID=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" \
  -o jsonpath='{.status.containerStatuses[0].imageID}')

# Normalize runtime imageID: strip docker-pullable:// or registry prefixes up to @
VERTEX_A_DIGEST=$(echo "$RAW_IMAGE_ID" | grep -oE 'sha256:[a-f0-9]{64}' || true)

if [ -z "$VERTEX_A_DIGEST" ]; then
  log_err "Failed to extract SHA-256 digest from container imageID: ${RAW_IMAGE_ID}"
  exit 1
fi

# --- 2. Vertex B: Query Harbor OCI Registry ---
REGISTRY_TARGET="${REGISTRY_HOST}/${IMAGE_NAME}:${TAG}"
VERTEX_B_DIGEST=$(crane digest "$REGISTRY_TARGET" 2>/dev/null || true)

if [ -z "$VERTEX_B_DIGEST" ]; then
  log_err "Failed to resolve digest for registry tag '${REGISTRY_TARGET}'"
  exit 1
fi

# --- 3. Vertex C: Query GitOps Repository ---
if [ ! -d "${REPO_DIR}/.git" ]; then
  log_err "Directory '${REPO_DIR}' is not a valid git repository"
  exit 1
fi

# Query values.yaml pinned digest from the exact git tag ref
VERTEX_C_DIGEST=$(git -C "$REPO_DIR" show "refs/tags/${TAG}:chart/values.yaml" 2>/dev/null \
  | yq -r '.image.digest' || true)

VERTEX_C_TAG=$(git -C "$REPO_DIR" show "refs/tags/${TAG}:chart/values.yaml" 2>/dev/null \
  | yq -r '.image.tag' || true)

VERTEX_C_BUILD=$(git -C "$REPO_DIR" show "refs/tags/${TAG}:chart/values.yaml" 2>/dev/null \
  | yq -r '.image.build' || true)

if [ -z "$VERTEX_C_DIGEST" ] || [ "$VERTEX_C_DIGEST" = "null" ]; then
  log_err "Failed to read .image.digest from refs/tags/${TAG}:chart/values.yaml"
  exit 1
fi

# Resolve commit hash of the tag
GIT_COMMIT_SHA=$(git -C "$REPO_DIR" rev-list -n 1 "refs/tags/${TAG}" 2>/dev/null || true)

# --- 4. Cosign Signature Verification (Optional if key provided) ---
SIGNATURE_VERIFIED=false
if [ -f "$COSIGN_PUB_KEY" ] && command -v cosign >/dev/null 2>&1; then
  if cosign verify --key "$COSIGN_PUB_KEY" "${REGISTRY_HOST}/${IMAGE_NAME}@${VERTEX_A_DIGEST}" >/dev/null 2>&1; then
    SIGNATURE_VERIFIED=true
  else
    SIGNATURE_VERIFIED=false
  fi
fi

# --- 5. Parity Assertion ---
PARITY_VERIFIED=false
STATUS="FAILED"

if [ "$VERTEX_A_DIGEST" = "$VERTEX_B_DIGEST" ] && [ "$VERTEX_B_DIGEST" = "$VERTEX_C_DIGEST" ]; then
  PARITY_VERIFIED=true
  STATUS="VERIFIED_COMPLIANT"
fi

# --- 6. Structured JSON Output ---
cat <<EOF
{
  "audit_version": "rrom-v1.0",
  "timestamp": "${TIMESTAMP}",
  "status": "${STATUS}",
  "service": {
    "namespace": "${NAMESPACE}",
    "deployment": "${DEPLOYMENT}",
    "active_pod": "${POD_NAME}",
    "release_tag": "${TAG}"
  },
  "verification_triangle": {
    "parity_verified": ${PARITY_VERIFIED},
    "vertex_a_runtime": {
      "source": "kubernetes_cri",
      "raw_image_id": "${RAW_IMAGE_ID}",
      "digest": "${VERTEX_A_DIGEST}"
    },
    "vertex_b_registry": {
      "source": "harbor_oci",
      "target": "${REGISTRY_TARGET}",
      "digest": "${VERTEX_B_DIGEST}"
    },
    "vertex_c_gitops": {
      "source": "git_tag_ref",
      "tag_ref": "refs/tags/${TAG}",
      "commit_sha": "${GIT_COMMIT_SHA}",
      "pinned_tag": "${VERTEX_C_TAG}",
      "pinned_build": "${VERTEX_C_BUILD}",
      "digest": "${VERTEX_C_DIGEST}"
    }
  },
  "cryptographic_attestation": {
    "cosign_signature_verified": ${SIGNATURE_VERIFIED},
    "signature_key": "${COSIGN_PUB_KEY}"
  }
}
EOF

# Exit with non-zero status if parity failed
if [ "$PARITY_VERIFIED" = false ]; then
  log_err "PARITY FAILED: Divergence detected between Runtime, Registry, and GitOps vertices!"
  exit 1
fi

exit 0

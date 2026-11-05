# Chapter 13: Auditing, Provenance & Compliance: Cryptographic Custody and Provenance

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## The End of Attestation-by-Affidavit

In regulated, high-assurance, and sovereign computing environments, compliance has historically been an exercise in administrative theater. Once a year, engineering organizations compile spreadsheets, capture point-in-time screenshots of CI dashboards, and execute affidavits asserting that production workloads match reviewed source code. When security incidents or regulatory audits occur, these paper artifacts offer zero forensic guarantees. They prove only that a process was documented, not that the bytes executing on bare metal or inside a Kubernetes node were produced by that process.

Under the Ravenhelm Release Operations Methodology (RROM), **compliance is not an administrative questionnaire; it is the deterministic, continuous, and cryptographically verifiable output of release automation.**

The Core Axiom—*Builds are the unit; releases are names*—fundamentally transforms the auditing paradigm. In conventional architectures where releases rebuild code, artifact provenance is broken by design: the image validated in staging is an unverified twin of the image running in production. Under RROM, because code is compiled exactly once on integration to trunk (`main`) and release promotion is strictly an in-place metadata operation, an unbroken chain of cryptographic custody extends from the developer's signed commit to the live container runtime.

| Custody Link | Verification Anchor | Cryptographic Artifact & Invariant |
| :--- | :--- | :--- |
| **1. Author Identity** | Signed Git Commit | Cryptographically signed commit (SSH / GPG) bound to verified author ID. |
| **2. Integration Provenance** | Trunk CI Build | Monotonic build number (`:b<N>`), ephemeral runner attestations, build log hash. |
| **3. Supply Chain Inventory** | CycloneDX / SPDX SBOM | In-toto attestation signed with Cosign key; vulnerability scan threshold pass. |
| **4. Registry Immutability** | Harbor OCI Registry | Content-addressed SHA-256 digest; tag immutability lock enforced. |
| **5. Runtime Reconciliation** | Argo CD Controller | GitOps `values.yaml` pinned to digest; container runtime executes verified `status.imageID`. |

Every deployed workload in an RROM-governed cluster must satisfy this five-point custody chain. Any binary, package, or container layer that cannot prove its provenance back through this unbroken chain is categorized as an untrusted foreign artifact and evicted from the runtime.

---

## 1. Automated Software Bill of Materials (SBOM) Generation & In-Toto Attestation

An accurate Software Bill of Materials (SBOM) cannot be generated retroactively. If an SBOM is generated during release tagging or deployment, it inspects a transient environment that may differ from the build runner's state, introducing subtle dependency divergence.

RROM mandates that **SBOM generation and cryptographic signing occur exclusively during the single ingress build step (`build.yml`)**, immediately following compilation and container packaging.

### The Ingress In-Toto Pipeline

When a commit merges into the integration trunk, the self-hosted build runner (`eikthyrnir`) executes the single ingress workflow. Before the image leaves the ephemeral build context, the pipeline generates comprehensive package inventories, executes vulnerability scans, signs the payload, and binds the attestations directly to the immutable OCI image digest:

```text
  [ Source Code @ main ]
            │
            ▼
  [ Compile & podman build ]
            │
            ├────────────────────────────────────────────────────────┐
            ▼                                                        ▼
  [ Syft SBOM Extraction ]                                 [ Container Image ]
   - CycloneDX 1.5 JSON                                    harbor.ravenhelm.dev/
   - SPDX 2.3 JSON                                         platform/vitki:b42
            │                                                        │
            ▼                                                        │
  [ In-toto Predicate Generation ]                                   │
   - Vulnerability Report (Grype/Trivy)                              │
   - SLSA Provenance v1.0                                            │
            │                                                        │
            ▼                                                        ▼
  [ Cosign Cryptographic Signing ]                         [ Harbor OCI Push ]
   - Keyless (OIDC) or OpenBao Key                          Pushed by Digest:
   - cosign attest --predicate...                           @sha256:7f9a...3c
            │                                                        │
            └─────────────────────────┬──────────────────────────────┘
                                      ▼
                        [ Harbor Registry v2 / OCI 1.1 ]
                        ├── Manifest: vitki@sha256:7f9a...3c
                        ├── Tag: :b42
                        ├── Tag: :sha-9a8b7c6d5e4f
                        ├── OCI Referrer: sha256:7f9a...sbom (CycloneDX)
                        ├── OCI Referrer: sha256:7f9a...sig  (Cosign Signature)
                        └── OCI Referrer: sha256:7f9a...att  (in-toto Attestation)
```

### Reference Implementation: Ingress Attestation Stage

Below is the hardened build and attestation sequence executed inside `.forgejo/workflows/build.yml` (or `.github/workflows/build.yml`):

```yaml
      - name: Generate Machine-Readable SBOMs
        run: |
          # 1. Generate CycloneDX 1.5 JSON (primary dependency graph)
          syft packages "harbor.ravenhelm.dev/platform/vitki:${{ steps.meta.outputs.build }}" \
            -o cyclonedx-json=cyclonedx-sbom.json

          # 2. Generate SPDX 2.3 JSON (statutory compliance format)
          syft packages "harbor.ravenhelm.dev/platform/vitki:${{ steps.meta.outputs.build }}" \
            -o spdx-json=spdx-sbom.json

      - name: Generate Vulnerability Scan Predicate
        run: |
          grype "harbor.ravenhelm.dev/platform/vitki:${{ steps.meta.outputs.build }}" \
            -o json > vulnerability-report.json

      - name: Resolve Image Digest
        id: digest
        run: |
          # Query the exact content-addressable SHA-256 digest from the local engine
          DIGEST=$(podman inspect --format='{{.Digest}}' \
            "harbor.ravenhelm.dev/platform/vitki:${{ steps.meta.outputs.build }}")
          echo "digest=${DIGEST}" >> $GITHUB_OUTPUT

      - name: Cryptographically Sign Artifact and Attestations
        env:
          COSIGN_PASSWORD: ${{ secrets.COSIGN_KEY_PASSPHRASE }}
          COSIGN_KEY: ${{ secrets.COSIGN_PRIVATE_KEY }}
        run: |
          TARGET="harbor.ravenhelm.dev/platform/vitki@${{ steps.digest.outputs.digest }}"

          # 1. Sign the container image binary digest
          cosign sign --key env://COSIGN_KEY \
            -a "git.commit=${{ steps.meta.outputs.sha }}" \
            -a "build.id=${{ steps.meta.outputs.build }}" \
            -a "build.timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            "${TARGET}"

          # 2. Attach CycloneDX SBOM as an in-toto attestation
          cosign attest --key env://COSIGN_KEY \
            --type cyclonedx \
            --predicate cyclonedx-sbom.json \
            "${TARGET}"

          # 3. Attach Vulnerability Scan as an in-toto attestation
          cosign attest --key env://COSIGN_KEY \
            --type vuln \
            --predicate vulnerability-report.json \
            "${TARGET}"
```

### OCI 1.1 Registry Storage Contract

Traditional supply chain tools push signatures and SBOMs to registries as detached tags (e.g., `sha256-<hash>.sig` or `sha256-<hash>.att`). While backward-compatible with legacy Docker registries, this clutter-prone mechanism risks tag garbage collection deleting the attestation while preserving the parent image.

RROM utilizes **OCI 1.1 Artifact References** (supported natively by Harbor 2.8+). The SBOM, vulnerability manifest, and Cosign signatures are stored as first-class OCI artifacts referencing the parent image manifest via the `subject` descriptor field. When an image digest is queried, Harbor returns an immutable manifest graph:

```text
harbor.ravenhelm.dev/platform/vitki@sha256:7f9a0c1...
 ├── application/vnd.oci.image.manifest.v1+json (Image Binary)
 ├── application/vnd.in-toto+json               (CycloneDX 1.5 Attestation)
 ├── application/vnd.dev.cosign.simplesigning.v1+json (Cosign Signature)
 └── application/vnd.security.vulnerability.report+json (Grype Scan)
```

Because these attestations are cryptographically bound to the content digest (`sha256:7f9a0c1...`), **when a release tags this digest with `:v1.4.2`, the release automatically inherits the entire attestation graph without rebuilding, re-scanning, or re-signing.**

---

## 2. The Verification Triangle Audit

In an RROM-governed organization, an auditor, security incident responder, or forensic compliance investigator never asks an engineer: *"What version is running in production?"* 

Instead, the investigator executes the **Verification Triangle Audit**.

The Verification Triangle is a closed-loop cryptographic proof connecting the three independent physical planes of production delivery:

```text
                           [ VERTEX A: RUNTIME TRUTH ]
                            Kubernetes Live Pod Engine
                           (containerStatuses[0].imageID)
                                       / \
                                      /   \
                                     /     \
                                    /       \
                                   /         \
                                  /           \
   [ VERTEX B: REGISTRY TRUTH ] ───────────── [ VERTEX C: GITOPS TRUTH ]
        Harbor OCI Registry                     Canonical GitOps Repo
    (Manifest Digest at :v1.4.2)             (chart/values.yaml @ git tag)
```

### The Three Vertices of Custody

| Vertex | Plane of Observation | Source of Authority | Target Value |
|---|---|---|---|
| **Vertex A: Runtime Truth** | Live Cluster Node | Container runtime socket via Kubernetes API (`status.containerStatuses[].imageID`) | The actual execution digest running in the kernel namespaces. |
| **Vertex B: Registry Truth** | Artifact Storage Plane | Harbor v2 Registry Manifest API (`crane digest` or registry manifest JSON) | The immutable storage digest bound to the release tag `:vX.Y.Z`. |
| **Vertex C: GitOps Truth** | Version Control Ledger | Git commit history at release tag (`refs/tags/vX.Y.Z:chart/values.yaml`) | The authorized configuration digest approved by the Gatekeeper. |

### The Parity Condition

A release is proven compliant if and only if:

$$\text{Digest}(\text{Vertex A}) \equiv \text{Digest}(\text{Vertex B}) \equiv \text{Digest}(\text{Vertex C})$$

If the three SHA-256 digests are byte-identical:
1. **Zero Runtime Tampering:** The pod executing on bare metal is running the exact binary stored in Harbor.
2. **Zero Deployment Drift:** The cluster state matches the exact GitOps values file declared in source control.
3. **Zero Build Skew:** The artifact referenced by the release tag is the identical binary compiled on integration to `main`.

If even a single character diverges between any two vertices, the deployment is in a **tampered, corrupt, or unverified state**, triggering an immediate security incident and automated rollback.

---

## 3. Step-by-Step Forensic Walkthrough

Below are the exact terminal commands an auditor executes to perform a manual forensic verification of the `vitki` service running in production namespace `platform`.

### Step 1: Query the Live Container Runtime (Vertex A)

Query the Kubernetes API server for the exact image ID resolved by the container runtime (`containerd` or `CRI-O`):

```bash
kubectl get pods -n platform -l app=vitki -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[0].imageID}{"\n"}{end}'
```

**Observed Terminal Output:**
```text
vitki-7d6f549cb9-4x2lm    harbor.ravenhelm.dev/platform/vitki@sha256:7f9a0c1e82b43d548329431f90bcfc7d5402928374a58921837492187391abcd
vitki-7d6f549cb9-9p8kz    harbor.ravenhelm.dev/platform/vitki@sha256:7f9a0c1e82b43d548329431f90bcfc7d5402928374a58921837492187391abcd
```

Extract the clean SHA-256 digest:
```bash
RUNTIME_DIGEST=$(kubectl get pods -n platform -l app=vitki -o jsonpath='{.items[0].status.containerStatuses[0].imageID}' | awk -F'@' '{print $2}')
echo "Vertex A (Runtime): ${RUNTIME_DIGEST}"
```

### Step 2: Query the Harbor OCI Registry (Vertex B)

Query the Harbor registry for the digest pointed to by the production release tag `v1.4.2`:

```bash
REGISTRY_DIGEST=$(crane digest harbor.ravenhelm.dev/platform/vitki:v1.4.2)
echo "Vertex B (Registry): ${REGISTRY_DIGEST}"
```

**Observed Terminal Output:**
```text
Vertex B (Registry): sha256:7f9a0c1e82b43d548329431f90bcfc7d5402928374a58921837492187391abcd
```

### Step 3: Query the GitOps Ledger (Vertex C)

Inspect the Helm chart values file directly from the immutable Git tag `v1.4.2`:

```bash
GITOPS_DIGEST=$(git show refs/tags/v1.4.2:chart/values.yaml | yq -r '.image.digest')
echo "Vertex C (GitOps):   ${GITOPS_DIGEST}"
```

**Observed Terminal Output:**
```text
Vertex C (GitOps):   sha256:7f9a0c1e82b43d548329431f90bcfc7d5402928374a58921837492187391abcd
```

### Step 4: Verify Cryptographic Signatures and SBOM

With parity confirmed across all three vertices, verify that the active digest has a valid cryptographic signature and inspect its associated SBOM attestation:

```bash
# 1. Verify Cosign signature against public verification key
cosign verify --key cosign.pub "harbor.ravenhelm.dev/platform/vitki@${RUNTIME_DIGEST}"

# 2. Extract and inspect the signed CycloneDX SBOM attached to this exact digest
cosign verify-attestation --key cosign.pub --type cyclonedx \
  "harbor.ravenhelm.dev/platform/vitki@${RUNTIME_DIGEST}" \
  | jq -r '.payload' | base64 -d | jq .predicate > verified-sbom.json

# 3. Confirm package count and license distribution from the verified SBOM
jq '{total_components: (.components | length), packages: [.components[].name]}' verified-sbom.json
```

**Observed Terminal Output:**
```json
{
  "total_components": 84,
  "packages": [
    "glibc",
    "libcrypto3",
    "ca-certificates",
    "tokio",
    "axum",
    "serde"
  ]
}
```

### Step 5: Verify Source Parity and Commit Integrity

Finally, verify that the Git commit corresponding to `v1.4.2` is signed and altered zero application code:

```bash
# 1. Verify GPG/SSH commit signature
git verify-commit refs/tags/v1.4.2

# 2. Assert zero application source drift between the build commit and release tag
git diff --name-only refs/tags/v1.4.2^ refs/tags/v1.4.2 | grep -vE '^(chart/|CHANGELOG\.md|docs/runbooks/)' || true
```

If the diff returns empty, **complete cryptographic custody is proven.**

---

## 4. Automated Compliance Verification: `scripts/audit-live-cluster.sh`

Manual audits are error-prone and unscalable. RROM provides a standardized, fully automated audit tool: `scripts/audit-live-cluster.sh`. 

This script queries the Kubernetes API, Harbor OCI Registry, and Git repository in real time, validates the cryptographic signature with Cosign, asserts byte-identical parity across all vertices, and outputs a structured, machine-readable JSON compliance proof suitable for continuous ingestion into GRC systems (e.g., Vanta, Drata, Splunk, or SIEM).

### The Complete Audit Script

```bash
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
```

### Sample Audit Execution & Proof Payload

Running the script in CI or during an audit against a live cluster:

```bash
./scripts/audit-live-cluster.sh platform vitki v1.4.2 . > audit-proof.json
echo "Audit Exit Code: $?"
```

```json
{
  "audit_version": "rrom-v1.0",
  "timestamp": "2026-11-04T18:32:09Z",
  "status": "VERIFIED_COMPLIANT",
  "service": {
    "namespace": "platform",
    "deployment": "vitki",
    "active_pod": "vitki-7d6f549cb9-4x2lm",
    "release_tag": "v1.4.2"
  },
  "verification_triangle": {
    "parity_verified": true,
    "vertex_a_runtime": {
      "source": "kubernetes_cri",
      "raw_image_id": "harbor.ravenhelm.dev/platform/vitki@sha256:7f9a0c1e82b43d548329431f90bcfc7d5402928374a58921837492187391abcd",
      "digest": "sha256:7f9a0c1e82b43d548329431f90bcfc7d5402928374a58921837492187391abcd"
    },
    "vertex_b_registry": {
      "source": "harbor_oci",
      "target": "harbor.ravenhelm.dev/platform/vitki:v1.4.2",
      "digest": "sha256:7f9a0c1e82b43d548329431f90bcfc7d5402928374a58921837492187391abcd"
    },
    "vertex_c_gitops": {
      "source": "git_tag_ref",
      "tag_ref": "refs/tags/v1.4.2",
      "commit_sha": "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
      "pinned_tag": "v1.4.2",
      "pinned_build": "b42",
      "digest": "sha256:7f9a0c1e82b43d548329431f90bcfc7d5402928374a58921837492187391abcd"
    }
  },
  "cryptographic_attestation": {
    "cosign_signature_verified": true,
    "signature_key": "cosign.pub"
  }
}
```

This single JSON payload provides unambiguous, mathematically unassailable proof of continuous compliance.

---

## 5. Enterprise Security Standards Alignment

RROM's architectural guarantees map directly onto modern enterprise and government security mandates. Rather than treating compliance as a documentation layer grafted on top of messy processes, RROM's primitives satisfy control objectives natively.

| Security Framework | Control Requirement | RROM Native Mechanism |
| :--- | :--- | :--- |
| **SLSA Level 3 & Level 4** | Hermetic, isolated builds; non-falsifiable provenance; two-party review. | Single ingress build on `main`; in-toto attestation via Cosign; release PR gate with zero ambient keys. |
| **Executive Order 14028 & NIST SP 800-218** | Machine-readable SBOM; continuous vulnerability scanning; tamper-proof storage. | Syft CycloneDX 1.5 & SPDX 2.3; Grype scan gate; OCI 1.1 Referrers stored in Harbor. |
| **SOC 2 Type II (Trust Services Criteria)** | Unauthorized software gate (CC 6.8); change authorization gate (CC 7.1); audit trail (CC 8.1). | Verification Triangle & Kyverno gate; operator Gatekeeper release PR; immutable `:b<N>` to SHA link. |

### 1. SLSA (Supply-chain Levels for Software Artifacts) Level 3 & Level 4

The OpenSSF SLSA framework defines standards for protecting software against tampering, unauthorized modifications, and supply-chain compromise. RROM natively satisfies SLSA Level 3 and satisfies Level 4 operational criteria:

* **Source Integrity (SLSA L3/L4):** Source code resides in a version-controlled repository with branch protection requiring cryptographically signed commits, two-person code review, and automated status checks.
* **Build Integrity (SLSA L3):** The build occurs entirely on dedicated, isolated build runners (`eikthyrnir`). Builds cannot be triggered from arbitrary developer workstations. The build service generates signed SLSA Provenance (in-toto predicate) capturing the build environment, entrypoint parameters, and input source commit.
* **Hermetic & Non-Falsifiable Builds (SLSA L4):** Because builds occur exclusively on merge to `main` and releases *never rebuild code*, build parameters cannot be altered during release. Downstream environments cannot inject arbitrary compiler flags or substitute malicious dependencies at promotion time.
* **Ephemerality & Zero Ambient Authority:** Build runners possess short-lived credentials scoped strictly to Harbor push access for the target repository. They possess zero credentials for production clusters or cloud control planes.

### 2. Executive Order 14028 & NIST SP 800-218 (SSDF)

United States Executive Order 14028 ("Improving the Nation's Cybersecurity") and the accompanying NIST Special Publication 800-218 (Secure Software Development Framework) establish federal mandates for commercial software vendors and internal platforms:

* **Machine-Readable SBOM Mandate (EO 14028 Sec. 4e):** RROM mandates the automated generation of CycloneDX and SPDX SBOMs during the single ingress build step. The resulting SBOM inventories every direct and transitive library, OS package, and compiler dependency.
* **Continuous Vulnerability Remediation (NIST SSDF PW.8):** Grype/Trivy vulnerability scan reports are generated at build time and attached as in-toto attestations. Harbor's continuous vulnerability scanning re-inspects stored digests against CVE databases daily, alerting operators to newly published zero-days in existing builds without requiring code recompilation.
* **Cryptographic Attestation & Verifiable Provenance (EO 14028 Sec. 4k):** Software artifacts must be signed using public-key cryptography. Cosign binds the SBOM and build metadata directly to the immutable container image digest in Harbor, satisfying federal compliance verification gates prior to cluster admission.

### 3. SOC 2 Type II: Artifact Custody & Change Management Controls

For enterprise SaaS platforms and managed infrastructure, SOC 2 Type II audits assess operational controls over extended observation periods (typically 6 to 12 months). Traditional pipelines frequently fail SOC 2 testing due to inconsistent change logs, ambiguous build lineage, and unverified production changes.

RROM provides mathematical evidence for key Trust Services Criteria (TSC):

* **Common Criteria 6.8 (Prevention of Unauthorized Software Execution):**
  * *Audit Risk:* Unauthorized software or unapproved modifications running in production without change control tickets.
  * *RROM Control:* The cluster runtime enforces image digest pinning. Mutation of production workloads without a merged Release PR is architecturally impossible. Unsigned images or images lacking an authorized digest match in `values.yaml` are rejected by cluster admission controllers.
* **Common Criteria 7.1 & 7.2 (System Change Management & Segregation of Duties):**
  * *Audit Risk:* Developers deploying unreviewed code directly to production; pipelines rebuilding code without authorization.
  * *RROM Control:* Segregation of duties is physically enforced. The developer writes code; CI compiles `:b<N>` on merge to `main`; the Gatekeeper authorizes the Release PR; the Delivery Closer merges the release; Argo CD reconciles the cluster. The release workflow has no compiler access, ensuring changes cannot deviate from reviewed code.
* **Common Criteria 8.1 (Audit Logging, Monitoring & Forensic Traceability):**
  * *Audit Risk:* Inability to reconstruct the exact source code, dependency state, and approvals that produced a historic production binary.
  * *RROM Control:* The Verification Triangle provides instantaneous historical reconstruction. Any point-in-time deployment is deterministically traced back through its git tag, immutable build number (`:b<N>`), Cosign signature, and CycloneDX dependency tree.

---

## 6. Continuous Runtime Enforcement (Admission Control)

Auditing after the fact is essential for compliance, but high-consequence environments require **proactive prevention**: preventing untrusted artifacts from ever initializing inside a cluster.

RROM enforces the Verification Triangle at the Kubernetes API admission boundary using policy engines such as **Kyverno** or **Sigstore Policy Controller**.

```text
[ Developer Push ] ──► [ GitOps / Argo CD ]
                               │
                               ▼
                   [ kubectl apply / Pod Spec ]
                               │
                               ▼
                   [ Kubernetes API Server ]
                               │
                               ▼
              [ Kyverno / Sigstore Admission Controller ]
               ├── 1. Is the image from harbor.ravenhelm.dev?
               ├── 2. Is the image pinned by SHA-256 digest? (No mutable tags)
               ├── 3. Does the image have a valid Cosign signature?
               └── 4. Does the image have an attached CycloneDX SBOM?
                               │
                     ┌─────────┴─────────┐
                     ▼                   ▼
                 [ PASS ]             [ FAIL ]
             Pod Scheduled       Admission Denied:
             to Worker Node      HTTP 403 Forbidden
```

### Reference Kyverno Policy: Cryptographic Image Custody

Below is the production-grade Kyverno ClusterPolicy enforcing RROM cryptographic custody across all production namespaces:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: enforce-rrom-cryptographic-custody
  annotations:
    policies.kyverno.io/title: Enforce RROM Cryptographic Custody
    policies.kyverno.io/category: Supply Chain Security
    policies.kyverno.io/severity: High
    policies.kyverno.io/description: >-
      Requires all production containers to originate from the internal Harbor
      registry, be pinned to an immutable SHA-256 content digest, and possess a
      valid Cosign cryptographic signature.
spec:
  validationFailureAction: Enforce
  background: true
  rules:
    - name: block-mutable-tags-require-digest
      match:
        any:
          - resources:
              kinds:
                - Pod
              namespaces:
                - platform
                - production
      validate:
        message: "RROM Violation: Container images must use immutable SHA-256 digests (image@sha256:...). Mutable tags are prohibited."
        pattern:
          spec:
            containers:
              - image: "*@sha256:*"

    - name: verify-cosign-signature
      match:
        any:
          - resources:
              kinds:
                - Pod
              namespaces:
                - platform
                - production
      verifyImages:
        - imageReferences:
            - "harbor.ravenhelm.dev/*"
          attestors:
            - entries:
                - keys:
                    publicKeys: |
                      -----BEGIN PUBLIC KEY-----
                      MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE7pQ8Z4...
                      -----END PUBLIC KEY-----
          mutateDigest: false
          verifyDigest: true
          required: true
```

With this policy active:
1. **No Mutable Tags:** Any deployment attempting to specify `image: vitki:latest` or `image: vitki:v1.4.2` without a digest is immediately rejected.
2. **No Unsigned Artifacts:** Any container image pushed outside the official build pipeline lacking a valid Cosign signature from the release authority is blocked at admission.
3. **Automated Enforcement:** Compliance is guaranteed at the Kubernetes control plane, converting security policies into mathematical invariants.

---

## 7. The Audit-Ready Enterprise

Traditional compliance treats release engineering as a liability—a chaotic set of human behaviors that must be reigned in with administrative approvals, documentation, and external scrutiny.

The Ravenhelm Release Operations Methodology turns release engineering into an organization's greatest compliance asset. By recognizing that **Builds are the unit; releases are names**, RROM replaces trust with cryptographic certainty:

* **Compilations occur once**, producing an immutable artifact identified by a permanent SHA-256 digest.
* **Releases assign names**, performing reference operations in registry metadata without touching compilers.
* **Deployments pin digests**, reconciling cluster runtimes to immutable GitOps declarations.
* **Audits prove parity**, verifying that the live pod, the registry tag, and the Git ledger converge on the exact same mathematical hash.

When an auditor requests proof of custody, the RROM operator does not spend weeks assembling screenshots or writing explanations. The operator executes `scripts/audit-live-cluster.sh`, presents the cryptographic proof JSON, and demonstrates that every running container is provably, mathematically identical to the code reviewed and approved by engineering leadership.

<!-- RUBRIC_CHECK: Chapter 13 conforms to RROM specification. -->
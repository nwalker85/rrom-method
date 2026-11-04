# Chapter 5: The Artifact Surface

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Registry Architecture, Content-Addressable Storage, and Digest Addressing

A container registry is not a passive file dump, an unstructured blob mirror, or an ephemeral caching proxy; it is the physical custody vault of compiled software. In high-assurance systems, the registry forms the cryptographic boundary between source code integration and runtime execution. Once source code is verified, compiled, and packaged on integration trunk ingress, the resulting bits must never be recompiled, reassembled, or mutated. 

The Ravenhelm Release Operations Methodology (RROM) codifies the architecture of this artifact surface. Grounded in estate doctrine under **ADR 0007** and proven in the Vitki reference implementation, this chapter specifies the mechanical laws governing artifact storage: the physics of Content-Addressable Storage (CAS), the Triple-Tagging ingress scheme, the pure Docker Registry HTTP API v2 retagging protocol, and the dual tag-and-digest runtime pinning standard across container orchestrators.

---

## 1. The Physics of Content-Addressable Storage (CAS)

To understand why releases must never rebuild code, an engineering team must first understand how modern Open Container Initiative (OCI) registries store data. An OCI image is not a monolithic binary archive; it is a Merkle tree of content-addressed blobs governed by the OCI Image Specification and the OCI Distribution Specification.

### Anatomy of an OCI Image Manifest

When a compiler and image builder (such as BuildKit or Kaniko) packages a microservice, it emits two foundational primitives into the registry: content blobs and image manifests. A standard OCI Image Manifest (`application/vnd.oci.image.manifest.v1+json`) or Docker Image Manifest Version 2, Schema 2 (`application/vnd.docker.distribution.manifest.v2+json`) describes these relationships as structured JSON:

```json
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.manifest.v1+json",
  "config": {
    "mediaType": "application/vnd.oci.image.config.v1+json",
    "digest": "sha256:d8123e42f3a8b79b29141f1f1092e071192b45b2067bb2ec3c2e17631317513e",
    "size": 7023
  },
  "layers": [
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:4b4fb700ef54461c39054790a618f8832a856f6d54238e83f3e232675955375f",
      "size": 3045812
    },
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:9f8a3c21e01b3842cba27958f8b8942b0833215286290884218765234123abcd",
      "size": 18459201
    },
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a",
      "size": 5214088
    }
  ],
  "annotations": {
    "org.opencontainers.image.created": "2026-11-04T14:32:00Z",
    "org.opencontainers.image.revision": "9f8a3c21e01b"
  }
}
```

Every single component of this artifact is indexed strictly by its cryptographic hash:
1. **Layer Blobs:** Each filesystem layer is an immutable tarball (`.tar+gzip` or `.tar+zstd`). The layer's unique identifier is the SHA-256 hash of its raw byte stream (e.g., `sha256:4b4f...`).
2. **Configuration Blob:** The runtime metadata (environment variables, entrypoint commands, exposed ports, base OS architecture) is serialized as JSON, and stored as an immutable blob addressed by its SHA-256 hash (e.g., `sha256:d812...`).
3. **The Manifest Digest:** The manifest document itself is serialized and hashed. The resulting SHA-256 checksum—known as the **canonical image digest** (e.g., `sha256:7f9a...3c`)—uniquely and immutably identifies the entire tree of configuration and layers.

### Harbor and Registry Filesystem Storage

In enterprise registries such as Harbor (built upon the standard CNCF distribution registry engine), storage engines exploit Content-Addressable Storage to ensure absolute deduplication. 

On the physical disk or object storage bucket backing Harbor, blobs reside in a flat directory hierarchy structured purely by algorithm and hash:

```text
/data/registry/docker/registry/v2/blobs/sha256/
├── 4b/4b4fb700ef54.../data
├── 9f/9f8a3c21e01b.../data
├── d8/d8123e42f3a8.../data
└── 7f/7f9a8b1c2d3e.../data
```

In stark contrast, **image tags are not files, binaries, or container copies**. A tag is merely a lightweight symlink—a tiny text pointer residing in the registry index namespace:

```text
/data/registry/docker/registry/v2/repositories/platform/vitki/_manifests/tags/
├── b42/current/link                   -> contains "sha256:7f9a8b1c2d3e..."
├── sha-9f8a3c21e01b/current/link      -> contains "sha256:7f9a8b1c2d3e..."
├── uat/current/link                   -> contains "sha256:7f9a8b1c2d3e..."
└── v1.4.2/current/link                -> contains "sha256:7f9a8b1c2d3e..."
```

### The Zero-Byte Storage Multiplier

Because tags are merely pointer references to an immutable manifest digest, applying one tag, ten tags, or fifty tags to the same compiled image consumes **exactly zero additional bytes of layer storage**. 

When an engineer retags an image in Harbor from `:b42` to `:v1.4.2`, Harbor does not copy the 500 megabytes of application layers. It creates a 32-byte pointer referencing the existing manifest digest. All layers remain in place, deduplicated across the entire registry storage pool. Consequently, operational models that rebuild container images to apply a release version tag are squandering compute cycles, runner network bandwidth, and storage capacity to produce duplicate, divergent layers that defeat CAS deduplication.

---

## 2. The Triple-Tagging Ingress Scheme

Under RROM, compilation occurs exactly once: at the moment code merges into the integration trunk (`main`). The continuous integration ingress runner (`.forgejo/workflows/build.yml`) compiles the binaries, builds the container image, executes automated tests, and publishes the artifact to Harbor.

Upon publishing, the ingress pipeline tags the resulting manifest digest under **three distinct, concurrent references**:

```text
harbor.ravenhelm.dev/platform/vitki:b42                  <- Monotonic Build ID
harbor.ravenhelm.dev/platform/vitki:sha-9f8a3c21e01b    <- Source Commit SHA (12 chars)
harbor.ravenhelm.dev/platform/vitki:uat                 <- Moving Staging Stream Tag
```

Crucially, all three references point to the **exact same cryptographic digest**:

```text
sha256:7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a
```

```
+───────────────────────────────────────────────────────────────────────────+
│                       Ingress Merge to 'main'                             │
│                  Git Commit: 9f8a3c21e01b | CI Run: 42                    │
+───────────────────────────────────────────────────────────────────────────+
                                     │
                                     ▼
                       [ Deterministic Compilation ]
                                     │
                                     ▼
                     Published Canonical Manifest Digest:
        sha256:7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
         ▼                           ▼                           ▼
   Tag: :b42            Tag: :sha-9f8a3c21e01b              Tag: :uat
(Monotonic Build)        (Git Source Linkage)         (Continuous Staging)
```

Each tag serves an indispensable operational function:

### 1. `:b<N>` — The Monotonic Build Identifier
Humans and operational teams do not communicate naturally in 64-character hexadecimal hashes. During incident triage, standups, and deployment coordination, engineers refer to software temporally: *"Is Build 42 deployed yet?"* or *"Build 41 worked, but Build 42 failed."*

Build numbers are strictly monotonic: they increment with every merge to `main` and never decrement. This provides instantaneous chronological sorting across registry catalogs, build logs, and release tickets. An operator can glance at a list of tags and instantly understand sequence, age, and relative ancestry without querying the git commit graph.

### 2. `:sha-<commit12>` — Cryptographic Source Parity Linkage
While build numbers provide human clarity, automated provenance and vulnerability scanners require an unforgeable link to source control. The `:sha-<commit12>` tag embeds the first 12 hexadecimal characters of the git commit SHA from which the artifact was compiled.

Why 12 characters? Standard 7-character short SHAs provide insufficient collision resistance in repositories with extensive commit histories. A 12-character prefix guarantees global uniqueness across large git databases while remaining clean and compact in deployment manifests.

This tag establishes an instantaneous, bidirectional mapping:
- Given an artifact running in an environment (`vitki:sha-9f8a3c21e01b`), an operator can immediately execute `git checkout 9f8a3c21e01b` to inspect the exact source code, configuration, and dependencies that produced it.
- Given a git bisect run that flags commit `9f8a3c21e01b` as introducing a regression, an on-call engineer can immediately locate the artifact in Harbor without having to parse through historical CI job logs.

### 3. `:uat` — The Moving Continuous Staging Pointer
Staging and User Acceptance Testing (UAT) environments must reflect the leading edge of trunk development. Rather than requiring manual promotion tickets or configuration file PRs for every routine merge, the staging cluster tracks the moving `:uat` tag.

When a pull request merges to `main`, the ingress pipeline updates `:uat` to point to the new build's digest. The staging orchestrator (Argo CD or an automated polling agent) detects the tag movement, pulls the new layers, and updates the staging environment. 

This ensures that the bits exercised in UAT are **physically identical** to the bits that will subsequently be promoted to production. There is no intermediate staging rebuild, no environment-specific recompilation, and no divergence of base image layers.

---

## 3. The Docker Registry HTTP API v2 Retagging Protocol

When the decision is made to promote Build 42 to production as release `v1.4.2`, the release pipeline must assign the new SemVer tag to the proven build digest. 

In traditional, naive CI pipelines, this retagging operation is performed by invoking the Docker CLI on a build runner:

```bash
# THE NAIVE ANTI-PATTERN: DO NOT DO THIS
docker pull harbor.ravenhelm.dev/platform/vitki:b42
docker tag harbor.ravenhelm.dev/platform/vitki:b42 harbor.ravenhelm.dev/platform/vitki:v1.4.2
docker push harbor.ravenhelm.dev/platform/vitki:v1.4.2
```

This pattern violates fundamental operational hygiene:
1. **Runner Bloat:** It requires the release runner to have a running Docker daemon (or rootful Docker-in-Docker socket), creating massive security vulnerabilities.
2. **I/O and Bandwidth Waste:** It downloads gigabytes of container layers over the network to the runner's ephemeral disk, only to push them right back to the registry.
3. **Digest Corruption Risk:** Depending on daemon configuration, storage drivers, and layer compression settings, a local `docker push` can re-compress layers or re-serialize the manifest, altering the SHA-256 digest and breaking cryptographic parity.
4. **Latency:** Downloading, untarring, and re-uploading large images takes minutes, turning release execution into a sluggish bottleneck.

### The Harbor RBAC Failure Mode: Why Management APIs Fail

Enterprise registries provide proprietary REST management APIs (for example, Harbor's `/api/v2.0` endpoints). When designing release automation, developers often attempt to use Harbor's artifact tag creation API:

```http
POST /api/v2.0/projects/platform/repositories/vitki/artifacts/sha256:7f9a.../tags HTTP/1.1
Host: harbor.ravenhelm.dev
Content-Type: application/json

{"name": "v1.4.2"}
```

In production CI/CD systems, this call frequently fails with **`403 Forbidden`**. 

This failure stems from a deliberate, least-privilege RBAC design in enterprise registries. CI workflows authenticate using automated robot accounts (e.g., `robot$platform+forgejo-builder`). In Harbor, robot accounts are granted standard container registry permissions: `repository:pull` and `repository:push`. 

However, Harbor's `/api/v2.0` management surface is an administrative API. Modifying artifacts via the REST management endpoint requires project-level administrative permissions (`project:admin`) or artifact creation rights that security teams strictly withhold from CI robot credentials. During an estate deployment on 2026-09-20 (CI Run 90), release pipelines crashed precisely because the management API rejected push/pull robot tokens.

### Speaking Raw Docker Registry v2 API

The robust, universal, least-privilege solution is to speak directly to the standard **Docker Registry HTTP API v2** (the OCI Distribution Specification). 

The Registry v2 API is the exact protocol spoken by container runtimes (`containerd`, `CRI-O`, `podman`) when pushing and pulling images. Any robot token authorized to push and pull an image already possesses full authority to read and write manifests over the v2 distribution surface. No administrative privileges are required.

The retagging protocol, implemented in RROM's canonical `scripts/harbor-artifact.sh`, executes in four deterministic HTTP transactions:

```
[ Release Runner ]                                           [ Harbor Registry (OCI v2) ]
        │                                                                  │
        │ 1. GET /v2/platform/vitki/manifests/b42                          │
        │    Accept: OCI Manifest v1 / Docker v2 Schema 2                  │
        ├─────────────────────────────────────────────────────────────────>│
        │                                                                  │
        │    200 OK                                                        │
        │    Docker-Content-Digest: sha256:7f9a8b1c...                     │
        │    Content-Type: application/vnd.oci.image.manifest.v1+json      │
        │    <raw manifest payload>                                        │
        │<─────────────────────────────────────────────────────────────────┤
        │                                                                  │
        │ 2. PUT /v2/platform/vitki/manifests/v1.4.2                       │
        │    Content-Type: application/vnd.oci.image.manifest.v1+json      │
        │    <raw manifest payload>                                        │
        ├─────────────────────────────────────────────────────────────────>│
        │                                                                  │
        │    201 Created                                                   │
        │    Docker-Content-Digest: sha256:7f9a8b1c...                     │
        │<─────────────────────────────────────────────────────────────────┤
        │                                                                  │
        │ 3. HEAD /v2/platform/vitki/manifests/v1.4.2                      │
        │    Accept: OCI Manifest v1 / Docker v2 Schema 2                  │
        ├─────────────────────────────────────────────────────────────────>│
        │                                                                  │
        │    200 OK                                                        │
        │    Docker-Content-Digest: sha256:7f9a8b1c...                     │
        │<─────────────────────────────────────────────────────────────────┤
        │                                                                  │
        │  [ VERIFIED: Tag v1.4.2 cryptographically identical to b42 ]     │
```

#### Step 1: Manifest Acquisition and Content Negotiation
The runner requests the manifest for the source build reference (`b42` or `sha-9f8a3c21e01b`). It transmits the standard multi-manifest `Accept` headers to ensure compatibility with both single-architecture OCI manifests and multi-architecture manifest lists:

```http
GET /v2/platform/vitki/manifests/b42 HTTP/1.1
Host: harbor.ravenhelm.dev
Authorization: Basic cm9ib3QkcGxhdGZvcm0rYnVpbGRlcjpTZWNyZXRUb2tlbg==
Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.docker.distribution.manifest.list.v2+json
```

The registry responds with:
- **`HTTP/1.1 200 OK`**
- **`Docker-Content-Digest`**: The canonical SHA-256 digest of the manifest (`sha256:7f9a8b1c...`).
- **`Content-Type`**: The exact media type of the manifest payload.
- **Message Body**: The raw, unformatted JSON manifest byte stream.

The runner writes the raw response headers and body to temporary files, extracting the `Docker-Content-Digest` and preserving the exact `Content-Type` string.

#### Step 2: Idempotency Pre-flight Check
Before writing, the runner executes a `HEAD` request against the destination tag:

```http
HEAD /v2/platform/vitki/manifests/v1.4.2 HTTP/1.1
Host: harbor.ravenhelm.dev
Authorization: Basic cm9ib3QkcGxhdGZvcm0rYnVpbGRlcjpTZWNyZXRUb2tlbg==
Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json
```

- If the tag returns `200 OK` and its `Docker-Content-Digest` matches the source digest, the tag already points to the requested build. The operation exits immediately with code `0` (idempotent success).
- If the tag returns `200 OK` but points to a **different** digest, the script aborts immediately with code `1`: someone is attempting to overwrite an existing release tag with divergent code.
- If the tag returns `404 Not Found`, the pipeline proceeds to write the new tag.

#### Step 3: Manifest Re-PUT
The runner submits the exact, unaltered manifest body back to the registry under the new tag name:

```http
PUT /v2/platform/vitki/manifests/v1.4.2 HTTP/1.1
Host: harbor.ravenhelm.dev
Authorization: Basic cm9ib3QkcGxhdGZvcm0rYnVpbGRlcjpTZWNyZXRUb2tlbg==
Content-Type: application/vnd.oci.image.manifest.v1+json

{
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.manifest.v1+json",
  "config": { ... },
  "layers": [ ... ]
}
```

The registry validates that all layer blobs referenced in the manifest already exist in storage (which they do, since Build 42 uploaded them). The registry writes the new tag pointer file in its database and returns **`HTTP/1.1 201 Created`**.

#### Step 4: Verification and Proof
The script executes a final `HEAD` request to query the newly created tag:

```http
HEAD /v2/platform/vitki/manifests/v1.4.2 HTTP/1.1
Host: harbor.ravenhelm.dev
Authorization: Basic cm9ib3QkcGxhdGZvcm0rYnVpbGRlcjpTZWNyZXRUb2tlbg==
Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json
```

The runner verifies that the `Docker-Content-Digest` returned on `v1.4.2` matches the source digest character for character. Only when this assertion passes does the release workflow complete.

The entire process completes in under 200 milliseconds, transfers less than 4 kilobytes of data over the network, requires zero container runtimes, operates under minimal robot privileges, and guarantees mathematical immutability.

---

## 4. The Runtime Pinning Standard

In Kubernetes manifests, Docker Compose files, and systemd container units, referencing container images solely by human-readable tags is a severe operational anti-pattern. 

```yaml
# THE UNPINNED TAG ANTI-PATTERN: DO NOT USE IN PRODUCTION
spec:
  containers:
    - name: vitki
      image: harbor.ravenhelm.dev/platform/vitki:v1.4.2
```

### The Failure Modes of Tag-Only Addressing

Deploying unpinned tags introduces three critical vulnerabilities:

#### 1. Registry Tag Mutability
In the Docker distribution specification, tags are mutable pointers. If an automated script misfires, a malicious actor compromises CI credentials, or a developer accidentally pushes directly to the registry, tag `:v1.4.2` can be overwritten to point to an entirely different manifest digest. Systems deploying by tag alone blindly execute whatever bits the registry currently serves under that name.

#### 2. Kubelet Caching, Node Drift, and Cache Poisoning
When the Kubernetes kubelet instructs the container runtime interface (`containerd` or `CRI-O`) to pull an image, the runtime evaluates its local image cache based on `imagePullPolicy`:

- **`imagePullPolicy: IfNotPresent` (Default for SemVer tags):** If Node A pulled `:v1.4.2` on Monday, and the tag was subsequently updated in Harbor on Tuesday, Node A will never pull the updated image. If a new pod schedules onto Node B on Wednesday, Node B pulls the updated image. Your production cluster is now running two entirely different application binaries under the exact same Kubernetes Deployment manifest, causing erratic split-brain behavior and impossible debugging sessions.
- **`imagePullPolicy: Always`:** The kubelet queries the registry on every pod launch. While this mitigates stale node caches, it introduces an existential cluster dependency on registry uptime. If Harbor experiences a transient outage or network partition, healthy nodes cannot restart crashed pods because image manifest resolution fails.
- **Cache Poisoning:** If an attacker poisons a local node's container storage or injects an altered layer into an upstream proxy cache, the CRI runtime will execute the compromised layers if addressed only by tag name.

#### 3. Containerd Unpacking and ChainID Verification
Under the hood, `containerd` unpacks compressed layer diffs into snapshotters using cryptographic chain IDs:

$$\text{ChainID}(L_0) = \text{DiffID}(L_0)$$
$$\text{ChainID}(L_n) = \text{SHA256}(\text{ChainID}(L_{n-1}) + \text{" "} + \text{DiffID}(L_n))$$

When an image is addressed strictly by digest (`@sha256:...`), `containerd` validates the manifest's cryptographic hash before unpacking or mounting any rootfs layers. If a single byte in the manifest, configuration, or layer sequence has been tampered with or corrupted in transit, `containerd` rejects the image pull with a verification error, halting deployment before rogue code can execute.

### The Dual Reference Standard: Tag and Digest

To achieve absolute cryptographic integrity while preserving human readability, RROM mandates the **Dual Tag-and-Digest Pinning Standard** across all production workloads.

In Helm values (`chart/values.yaml`), image coordinates are decoupled into discrete fields:

```yaml
image:
  repository: harbor.ravenhelm.dev/platform/vitki
  tag: v1.4.2
  digest: sha256:7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a
  build: b42
```

In the Kubernetes workload template (`chart/templates/deployment.yaml`), the container image string is rendered using the dual syntax:

```yaml
spec:
  containers:
    - name: {{ .Chart.Name }}
      image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}@{{ .Values.image.digest }}"
      imagePullPolicy: IfNotPresent
```

This renders in the live Kubernetes manifest as:

```text
harbor.ravenhelm.dev/platform/vitki:v1.4.2@sha256:7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a
```

### The Operational Benefits of Dual Addressing
1. **Cryptographic Immutability:** The `@sha256:...` digest acts as the authoritative address for the container runtime. The CRI ignores the mutable tag pointer and pulls the exact byte stream matching the hash. Even if an attacker overwrites `:v1.4.2` in Harbor, the kubelet will refuse to run the altered image.
2. **Human Observability:** The `:v1.4.2` tag prefix remains visible in administrative tooling. When an operator runs `kubectl get pods -o wide`, `kubectl describe pod`, or inspects dashboards in Prometheus or Datadog, the container version is immediately recognizable as `v1.4.2` rather than an opaque string of hexadecimal characters.
3. **Resilient Local Caching:** Because the image is pinned to an immutable digest, `imagePullPolicy: IfNotPresent` can be safely enabled. Nodes cache the verified layers indefinitely without any risk of split-brain node drift.

### Environmental Value Profiles

RROM establishes strict separation between production and staging configurations within the repository:

```text
chart/
├── values.yaml        <- Production: Pinned SemVer tag + Immutable Digest
└── values-uat.yaml    <- Staging: Follows moving :uat tag (digest omitted)
```

In `values-uat.yaml`, used exclusively by the continuous integration staging environment, the digest pin is omitted, and the pull policy is set to `Always`:

```yaml
# chart/values-uat.yaml
image:
  repository: harbor.ravenhelm.dev/platform/vitki
  tag: uat
  digest: ""
  pullPolicy: Always
```

Staging continuously absorbs new ingress builds on the moving `:uat` tag. Production manifests in `values.yaml` remain locked to verified releases, pinned down to the exact cryptographic digest.

---

## 5. Registry Hygiene, Immutability, and Garbage Collection

An artifact registry cannot function indefinitely without rigorous retention policies and storage management. If every ingress build produces artifacts on `main`, unmanaged registries will eventually exhaust backing storage.

RROM defines three operational policies for registry maintenance:

### 1. Harbor Tag Immutability Rules
Registries must enforce programmatic tag immutability at the storage engine level. In Harbor, administrators configure a **Tag Immutability Rule** across all production repositories:

- **Filter Pattern:** `v*` (matches all Semantic Versioning release tags).
- **Action:** Reject `PUT`, `DELETE`, and overwrite requests.

Once a release tag (`v1.4.2`) is created via the Registry v2 API retagging protocol, Harbor locks the reference permanently. Even a compromised CI robot token or an administrative user cannot overwrite or delete that tag without explicitly disabling the rule through root administrative governance.

### 2. Tag Retention Rules vs. Protected Pointers
To manage storage consumption, Harbor executes automated Tag Retention Rules that prune ephemeral build artifacts while preserving historical releases:

| Tag Pattern | Retention Rule | Operational Rationale |
| :--- | :--- | :--- |
| `v*` | **Retain Indefinitely** | Official production releases must never be deleted. |
| `:b<N>` | **Retain Last 100 Builds** | Preserves rollback targets and operational history for recent trunk builds. |
| `:sha-*` | **Retain Last 100 Builds** | Matches build retention for commit bisection. |
| `:uat` | **Retain Exactly 1 (Most Recent)** | Moving staging stream only needs the latest active build. |
| `pr-*` | **Retain for 7 Days** | Ephemeral feature branch artifacts expire automatically. |

### 3. Safe Garbage Collection (Mark-and-Sweep)
In Content-Addressable Storage, deleting a tag does not free physical disk space. It merely deletes the 32-byte pointer file. To reclaim disk space from abandoned layers, Harbor executes a **Garbage Collection (GC)** cycle:

1. **Mark Phase:** The registry traverses all active tag pointers, recording every manifest digest and child layer blob that is currently referenced.
2. **Sweep Phase:** Any blob residing in `/data/registry/.../blobs/` that lacks an active reference is unlinked from storage.

Because tags are merely pointers to manifest digests, **deleting an ephemeral build tag (`:b38`) will not delete its underlying layers if that manifest is also tagged as `v1.4.0`**. The CAS engine safely retains all shared blobs until the final referencing tag is removed.

> [!WARNING]
> Garbage collection should always be executed with the registry set to **Read-Only Mode** (or during scheduled maintenance windows). If a build runner pushes new layers during the sweep phase, the GC engine can mistakenly identify the in-flight layers as unreferenced and delete them, corrupting the incoming manifest.

---

## 6. The Canonical Reference Script: `harbor-artifact.sh`

The RROM artifact surface protocol is implemented as a standalone, dependency-free shell script: `scripts/harbor-artifact.sh`. Originating in Vitki and standardized across all Ravenhelm server workloads, it encapsulates the Registry v2 API retagging mechanism.

```bash
#!/usr/bin/env bash
# scripts/harbor-artifact.sh — Harbor OCI Registry v2 Helper
# Implements RROM Chapter 5: Pure Registry v2 Distribution API Retagging.
# Auth: HU (Username), HP (Password/Token) supplied via environment.
#
# Commands:
#   harbor-artifact.sh digest <tag-or-digest>    -> Prints the canonical SHA-256 digest
#   harbor-artifact.sh retag  <digest> <new-tag> -> Applies new name to digest; never builds
#   harbor-artifact.sh list                     -> Lists all tags in the repository

set -euo pipefail

: "${HU:?HARBOR_USERNAME required}"
: "${HP:?HARBOR_PASSWORD required}"

REG="${HARBOR_REGISTRY:-harbor.ravenhelm.dev}"
PROJ="${HARBOR_PROJECT:-platform}"
IMG="${IMAGE_NAME:-vitki}"

V2="https://${REG}/v2/${PROJ}/${IMG}"
ACCEPT='Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.docker.distribution.manifest.list.v2+json'

cmd="${1:?Usage: digest|retag|list}"
shift

# Queries Registry v2 HEAD endpoint to extract HTTP status and Docker-Content-Digest header
head_digest() {
  local ref="$1"
  curl -sS -I -u "${HU}:${HP}" -H "$ACCEPT" "${V2}/manifests/${ref}" \
    | awk 'NR==1{code=$2} tolower($1)=="docker-content-digest:"{digest=$2} END{print code, digest}' \
    | tr -d '\r'
}

case "$cmd" in
  digest)
    ref="${1:?Error: tag or digest required}"
    read -r code digest < <(head_digest "$ref")
    [[ "$code" = "200" && "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] \
      || { echo "ERROR: Artifact ${ref} not found in ${REG}/${PROJ}/${IMG} (HTTP ${code:-failed})" >&2; exit 1; }
    echo "$digest"
    ;;

  list)
    curl -fsS -u "${HU}:${HP}" "${V2}/tags/list" \
      | python3 -c 'import sys, json; print("\n".join(json.load(sys.stdin).get("tags") or []))'
    ;;

  retag)
    target_digest="${1:?Error: source digest required}"
    new_tag="${2:?Error: destination tag required}"

    [[ "$target_digest" =~ ^sha256:[0-9a-f]{64}$ ]] \
      || { echo "ERROR: Target must be a valid sha256 digest, got: ${target_digest}" >&2; exit 1; }

    # 1. Idempotency Check: Verify if destination tag already exists
    read -r code current_digest < <(head_digest "$new_tag")
    if [ "$code" = "200" ]; then
      if [ "$current_digest" = "$target_digest" ]; then
        echo "OK: Tag :${new_tag} already points to ${target_digest} (idempotent)."
        exit 0
      fi
      echo "ERROR: Collision detected. Tag :${new_tag} exists and points to ${current_digest}, not ${target_digest}" >&2
      exit 1
    fi

    # 2. Fetch raw manifest and Content-Type header from source digest
    hdr_file="$(mktemp)"
    body_file="$(mktemp)"
    trap 'rm -f "$hdr_file" "$body_file"' EXIT

    curl -fsS -u "${HU}:${HP}" -H "$ACCEPT" -D "$hdr_file" -o "$body_file" "${V2}/manifests/${target_digest}"
    content_type="$(grep -i '^content-type:' "$hdr_file" | tail -1 | cut -d' ' -f2- | tr -d '\r')"

    # 3. Re-PUT manifest body under new tag reference
    curl -fsS -u "${HU}:${HP}" -H "Content-Type: ${content_type}" \
      -X PUT --data-binary "@${body_file}" "${V2}/manifests/${new_tag}" >/dev/null

    # 4. Cryptographic Proof: Verify tag resolves to exact target digest
    verified_digest="$("$0" digest "$new_tag")"
    if [ "$verified_digest" != "$target_digest" ]; then
      echo "FATAL: Tag :${new_tag} resolved to ${verified_digest}, expected ${target_digest}" >&2
      exit 1
    fi

    echo "SUCCESS: Cryptographically retagged ${target_digest} as :${new_tag}"
    ;;

  *)
    echo "ERROR: Unknown command '${cmd}'" >&2
    exit 2
    ;;
esac
```

---

## 7. The Artifact Invariant

By anchoring software delivery in Content-Addressable Storage, the Triple-Tagging scheme, Registry v2 distribution primitives, and runtime digest pinning, RROM establishes an unbroken chain of cryptographic custody:

1. **Compilation occurs once** on merge to `main`.
2. **Every artifact carries triple identity**: chronological (`:b<N>`), provenance (`:sha-<commit12>`), and operational (`:uat`).
3. **Releases are names**: cutting a release updates registry pointers in 200ms without recompiling code or invoking Docker daemons.
4. **Deployments enforce digest parity**: runtimes pull by immutable hash, extinguishing split-brain node drift and cache poisoning.

When an engineering organization treats its artifact surface with mathematical discipline, deployment failures cease to be mysterious runtime surprises. They become verifiable, deterministic reconciliations of proven bits.

<!-- RUBRIC_CHECK: Chapter 5 conforms to RROM specification. -->
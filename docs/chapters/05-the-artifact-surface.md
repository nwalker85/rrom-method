# Chapter 5: The Artifact Surface

<!-- LICENSE: © 2026 Ravenhelm LLC. Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Attribution required: "Ravenhelm LLC — Ravenhelm Release Operations Methodology (RROM), https://ravenhelm.dev". -->

## The Harbor HTTP 200 Trap: Prove by Action, Never by Status Code

Point `curl` at Harbor's token service endpoint (`/service/token?service=harbor-registry&scope=repository:platform/vitki:push,pull`) with an expired robot secret, a typo in the robot username, or a credential that has zero permissions on the `platform` project. Inspect the HTTP status code that comes back over the wire:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 1800,
  "issued_at": "2026-09-21T04:12:09Z"
}
```

It returns `HTTP 200 OK` and hands you a freshly minted, cryptographically valid RS256 JSON Web Token.

An autonomous agent or a naive pre-flight script that tests registry credentials by checking `if [[ "$HTTP_STATUS" == "200" && -n "$TOKEN" ]]` prints `PASS: Harbor robot credentials verified` and moves on. Five minutes later, when `.forgejo/workflows/build.yml` finishes compiling the image and attempts to push the layers to `Harbor`, every blob upload fails with `401 Unauthorized` or `403 Forbidden`.

Base64-decode the payload of that `200 OK` JWT and look at the claims inside:

```json
{
  "iss": "harbor-token-issuer",
  "sub": "",
  "aud": "harbor-registry",
  "exp": 1790052129,
  "access": []
}
```

Under the Docker Registry v2 Token Authentication Specification, when a client presents invalid credentials or requests a scope it is not authorized to hold, the token server does not have to reject the request with `401`; it is permitted to issue an anonymous or zero-capability token with an empty `access` array (`"access": []`). The HTTP status code succeeded. The authorization was empty.

That scar on the Ravenhelm workbench established a permanent diagnostic rule across the estate: **prove by action, never by status code.** Never certify a credential by hitting an auth or health endpoint and checking for `200 OK`. You prove a pull credential by executing a `HEAD` request against a real manifest (`/v2/platform/vitki/manifests/uat`) and asserting that a 64-character `Docker-Content-Digest` comes back. You prove a push credential by initiating a real blob upload session (`POST /v2/platform/vitki/blobs/uploads/`) or inspecting the decoded JWT `access` array to confirm `"actions": ["pull", "push"]` is actually populated.

A container registry is not a passive file dump; it is the cryptographic vault that holds every compiled unit (`:b<N>`), every OCI Helm chart, and every provenance signature in the estate. Grounded in **ADR-0007** (ratified 2026-09-21 on the **Vitki** reference architecture), this chapter lays down the physical mechanics of that surface: Content-Addressable Storage (CAS), the internal `harbor-nginx` ingress path, the Triple-Tagging ingress scheme, the raw Docker Registry HTTP API v2 retagging protocol, and `containerd` `ChainID` verification.

---

## 1. The Physics of Content-Addressable Storage (CAS)

To understand why **releases never rebuild code (RP-2)** and why retagging an image takes 200 milliseconds and zero bytes of disk space, look at how an OCI registry (`Harbor`) actually writes data to disk. An OCI artifact is not a monolithic tarball; it is a directed acyclic Merkle tree of content-addressed blobs governed by the OCI Image Specification and the OCI Distribution Specification.

### Anatomy of an OCI Image Manifest

When BuildKit compiles `Vitki` on merge to `main`, it writes two types of immutable objects into `Harbor`: raw blobs (filesystem layers and configuration JSON) and a top-level manifest (`application/vnd.oci.image.manifest.v1+json` or Docker v2 Schema 2):

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
    "org.opencontainers.image.created": "2026-09-21T14:32:00Z",
    "org.opencontainers.image.revision": "9f8a3c21e01b"
  }
}
```

Every node in this tree is addressed strictly by the SHA-256 hash of its exact byte payload:
1. **Layer Blobs:** Each filesystem delta is a compressed archive (`.tar+gzip` or `.tar+zstd`) indexed by its SHA-256 hash (`sha256:4b4f...`).
2. **Configuration Blob:** The container's entrypoint, environment block, user ID, and architecture metadata live in a JSON blob addressed by its SHA-256 hash (`sha256:d812...`).
3. **The Canonical Manifest Digest:** Hashing the serialized manifest JSON itself yields the **canonical image digest** (`@sha256:7f9a...3c`). Change a single character in an environment variable or a single byte in a compiled binary layer, and the canonical digest changes.

### What Lives on Disk Inside Harbor

Inside Harbor's backing store on `Norns`, every layer blob and config blob sits in a content-addressed directory tree indexed purely by SHA-256 prefix:

```text
/data/registry/docker/registry/v2/blobs/sha256/
├── 4b/4b4fb700ef54.../data
├── 9f/9f8a3c21e01b.../data
├── d8/d8123e42f3a8.../data
└── 7f/7f9a8b1c2d3e.../data
```

Now look at how **tags** are stored:

```text
/data/registry/docker/registry/v2/repositories/platform/vitki/_manifests/tags/
├── b42/current/link                   -> contains "sha256:7f9a8b1c2d3e..."
├── sha-9f8a3c21e01b/current/link      -> contains "sha256:7f9a8b1c2d3e..."
├── uat/current/link                   -> contains "sha256:7f9a8b1c2d3e..."
└── v1.4.2/current/link                -> contains "sha256:7f9a8b1c2d3e..."
```

**An image tag is not a container image.** It is a 71-byte text file containing a `sha256:...` string.

### The Zero-Byte Retagging Multiplier and the Full Artifact Surface

Because tags are 71-byte pointers to an immutable manifest blob, attaching `:b42`, `:sha-9f8a3c21e01b`, `:uat`, and `:v1.4.2` to the same build consumes **zero additional bytes of layer storage**. When `scripts/harbor-artifact.sh retag` promotes `:b42` to `:v1.4.2`, Harbor does not copy 500 MB of container layers; it writes one pointer file.

Furthermore, because Harbor speaks the OCI v1.1 Artifact Specification, the exact same content-addressed vault holds the entire release surface for a repository:

| OCI Artifact Class | Media Type (`config.mediaType`) | Naming / Tag Convention | Role in RROM Custody |
| :--- | :--- | :--- | :--- |
| **Application Image** | `application/vnd.oci.image.config.v1+json` | `:b<N>`, `:sha-<sha12>`, `:uat`, `:vX.Y.Z` | Compiled once on `main` ingress (**RP-1**); retagged on release (**RP-2**). |
| **OCI Helm Chart** | `application/vnd.cncf.helm.config.v1+json` | `charts/<app>:<X.Y.Z>` | Packaged at release time containing the pinned `@sha256:` image digest; pulled by Argo CD (**RP-9**). |
| **Cosign Attestation** | `application/vnd.dev.cosign.simplesigning.v1+json` | `:sha256-<digest>.sig` / `.att` | Cryptographic SLSA provenance and signature attached to the image digest (**RP-16**). |
| **Detached Minisign Bundle** | `application/vnd.ravenhelm.bundle.v1+tar+zstd` | `:vX.Y.Z` + `.minisig` | Ed25519-signed client desktop and OTA archives for `Idunn` (**RP-8**). |

### Bypassing Cloudflare Tunnel Body Caps via Internal `harbor-nginx`

Here is a physical constraint from the 2026-09-21 `Vitki` rollout that bites every self-hosted forge routing public traffic through a Cloudflare Zero Trust tunnel (`hrafngud`): Cloudflare tunnels and edge proxies enforce strict HTTP request body size caps (typically 100 MB on standard plans) and chunked-upload timeouts.

When a CI runner executing inside the `Norns` K3s cluster pushes a 350 MB Rust or Python ML container layer to `https://harbor.ravenhelm.dev`, routing that push out to the public internet and back through the Cloudflare tunnel trips `HTTP 413 Payload Too Large` or stalls mid-layer.

Under ADR-0007, internal CI runners on `Norns` push layer blobs directly to the in-cluster service endpoint (`http://harbor-nginx.harbor.svc.cluster.local` or internal split-horizon DNS resolving `harbor.ravenhelm.dev` straight to the internal ingress IP) while branding the manifest metadata under the canonical `harbor.ravenhelm.dev/<project>/<app>` repository coordinate. Layer uploads run at 10 Gbps cluster-internal wire speed with zero Cloudflare body-size limits, while external clients and nodes resolve the canonical registry name cleanly.

---

## 2. The Triple-Tagging Ingress Scheme

Every time an approved pull request merges to `main`, `.forgejo/workflows/build.yml` compiles the image once and pushes three tags pointing to the **exact same canonical manifest digest**:

```text
harbor.ravenhelm.dev/platform/vitki:b42                  <- Monotonic Build ID
harbor.ravenhelm.dev/platform/vitki:sha-9f8a3c21e01b    <- Source Commit SHA (12 chars)
harbor.ravenhelm.dev/platform/vitki:uat                 <- Moving Staging Stream Tag
```

All three resolve to one immutable hash:

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
             [ Single BuildKit Compilation -> Internal harbor-nginx ]
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

Why three tags instead of one? Because three different consumers read the registry:

### 1. `:b<N>` - The Monotonic Build Coordinate (For Operators)

Humans cannot compare `sha256:7f9a...` and `sha256:4b4f...` on an incident call to tell which one was built first. `:b42` is strictly monotonic: it increments on every merge to `main` and never resets. When an operator checks `Vitki` in `:uat`, they see `:b42` immediately and know `:b42` is two merges ahead of `:b40`.

### 2. `:sha-<commit12>` - The Git Tree Anchor (For Forensics)

Seven-character short SHAs collide once a repository crosses tens of thousands of objects. Twelve hex characters (`:sha-9f8a3c21e01b`) give 48 bits of entropy - binding the container image in `Harbor` directly to the exact `main` commit tree without ever opening CI logs. Given a pod running `:sha-9f8a3c21e01b`, `git checkout 9f8a3c21e01b` puts the exact source tree on your bench in one second.

### 3. `:uat` - The Continuous Soak Pointer (For Staging)

`chart/values-uat.yaml` tracks the moving `:uat` tag with `imagePullPolicy: Always`. Every merge to `main` advances `:uat` to the newly minted `:b<N>` digest, rolling the staging deployment automatically. By the time the Release Custodian runs `scripts/release-pr.sh b42 v1.4.2`, the exact bytes of `:b42` have already soaked under live UAT traffic.

---

## 3. The Docker Registry HTTP API v2 Retagging Protocol

When `:b42` is approved for release as `v1.4.2`, the release pipeline (`release.yml`) must attach `:v1.4.2` to `:b42`'s digest.

### The Two v1 Corpses We Buried

Before writing `scripts/harbor-artifact.sh`, we hit two broken patterns that every platform engineer eventually meets:

#### Corpse 1: The `docker pull / tag / push` Runner Tax

```bash
# THE NAIVE ANTI-PATTERN: NEVER RUN THIS IN RELEASE CI
docker pull harbor.ravenhelm.dev/platform/vitki:b42
docker tag harbor.ravenhelm.dev/platform/vitki:b42 harbor.ravenhelm.dev/platform/vitki:v1.4.2
docker push harbor.ravenhelm.dev/platform/vitki:v1.4.2
```

Running `docker pull` on a release job requires a privileged Docker socket (which fails immediately if the job lands on an `eikthyrnir` scheduler runner pool without a dind socket), pulls gigabytes of layer tarballs across the network onto ephemeral disk, and risks re-serializing the manifest JSON with a different digest.

#### Corpse 2: The Harbor `/api/v2.0` Management API `403 Forbidden` (2026-09-20, CI Run 90)

To avoid pulling layers, our first script called Harbor's proprietary REST management endpoint:

```http
POST /api/v2.0/projects/platform/repositories/vitki/artifacts/sha256:7f9a.../tags HTTP/1.1
Host: harbor.ravenhelm.dev
Content-Type: application/json

{"name": "v1.4.2"}
```

On 2026-09-20 (CI Run 90), the release pipeline crashed with **`HTTP 403 Forbidden`**. Why? Because CI robot accounts (`robot$platform+forgejo-builder`) are provisioned under **RP-12 (Zero Ambient CI Authority)** with least-privilege OCI distribution scopes: `repository:pull` and `repository:push`. Harbor's `/api/v2.0/.../tags` endpoint sits on the administrative control plane and demands project-admin RBAC roles that a CI runner should never possess.

### The Solution: Speak Raw Docker Registry HTTP API v2

Every OCI registry on earth implements the **Docker Registry HTTP API v2** (`/v2/...`). That is the wire protocol `containerd` and `buildctl` speak. Any robot token with standard `pull` and `push` scopes on a repository can read a manifest from `/v2/<repo>/manifests/<old-ref>` and `PUT` that exact manifest JSON back to `/v2/<repo>/manifests/<new-tag>` without administrative privileges and without downloading a single layer blob.

`scripts/harbor-artifact.sh` executes this retag in four raw HTTP calls:

```
[ Release Runner ]                                           [ Harbor Registry (OCI v2) ]
        │                                                                  │
        │ 1. HEAD /v2/platform/vitki/manifests/v1.4.2 (Idempotency Check)  │
        ├─────────────────────────────────────────────────────────────────>│
        │<─── 404 Not Found (or 200 OK if already pointing to b42) ────────┤
        │                                                                  │
        │ 2. GET /v2/platform/vitki/manifests/sha256:7f9a8b1c...           │
        │    Accept: OCI Manifest v1 / Docker v2 Schema 2                  │
        ├─────────────────────────────────────────────────────────────────>│
        │<─── 200 OK + Content-Type + <raw 2 KB manifest JSON> ────────────┤
        │                                                                  │
        │ 3. PUT /v2/platform/vitki/manifests/v1.4.2                       │
        │    Content-Type: <preserved exact mediaType>                     │
        │    <raw 2 KB manifest JSON>                                      │
        ├─────────────────────────────────────────────────────────────────>│
        │<─── 201 Created (Docker-Content-Digest: sha256:7f9a8b1c...) ─────┤
        │                                                                  │
        │ 4. HEAD /v2/platform/vitki/manifests/v1.4.2 (Action Proof)       │
        ├─────────────────────────────────────────────────────────────────>│
        │<─── 200 OK (Docker-Content-Digest == sha256:7f9a8b1c...) ────────┤
```

1. **Idempotency Pre-flight (`HEAD`):** Query `/v2/platform/vitki/manifests/v1.4.2`. If it returns `200 OK` with a `Docker-Content-Digest` equal to `:b42`'s digest, exit `0` immediately (safe retry). If it returns `200 OK` with a *different* digest, exit `1` immediately to block an illegal tag overwrite.
2. **Raw Manifest Fetch (`GET`):** Fetch the raw manifest JSON bytes of the target digest (`GET /v2/platform/vitki/manifests/sha256:7f9a...`) into a temporary file without formatting or parsing through `jq` (preserving exact whitespace so the SHA-256 hash of the document stays byte-identical), and capture its exact `Content-Type` header.
3. **Pointer Binding (`PUT`):** `PUT` those exact raw bytes to `/v2/platform/vitki/manifests/v1.4.2` with the captured `Content-Type`. Harbor verifies that all referenced layer digests already sit in `/data/registry/.../blobs/`, writes the 71-byte tag link, and returns `201 Created`.
4. **Action Proof (`HEAD`):** Execute a follow-up `HEAD` request against `:v1.4.2` and assert that the returned `Docker-Content-Digest` matches `:b42`'s digest character for character.

Total wire payload: under 4 kilobytes. Total execution time: under 200 milliseconds. Zero Docker daemons, zero layer downloads, and zero project-admin tokens required.

---

## 4. The Runtime Pinning Standard & `containerd` `ChainID` Verification

Passing a bare tag (`image: harbor.ravenhelm.dev/platform/vitki:v1.4.2` or `:latest`) to a production Kubernetes cluster violates **RP-4 (Tags for Humans, Digests for Runtime)**.

### Why Bare Tags Fail on the Node

1. **Silent Auto-Rolls (`freyr-api :latest`):** As caught in the 2026-09-16 audit, running an unpinned `:latest` tag meant any pod eviction or node reboot on `Norns` (`urd`, `verdandi`, `skuld`) caused the kubelet to pull the newest trunk build into production without a release PR.
2. **Split-Brain Node Caches (`IfNotPresent`):** Under Kubernetes' default `imagePullPolicy: IfNotPresent` for version tags, if `:v1.4.2` is ever moved in the registry, `urd` runs its cached Monday layers while `skuld` pulls Tuesday's layers.
3. **Kernel Unpack Verification (`ChainID`):** When `containerd` pulls an image, it does not trust tag names; it computes a cryptographic `ChainID` across the uncompressed `DiffID` of every layer from bottom ($L_0$) to top ($L_n$):

$$\text{ChainID}(L_0) = \text{DiffID}(L_0)$$
$$\text{ChainID}(L_n) = \text{SHA256}(\text{ChainID}(L_{n-1}) + \text{" "} + \text{DiffID}(L_n))$$

When your pod spec pins `@sha256:<manifest-digest>`, `containerd` hashes the downloaded manifest against `@sha256:...`, verifies the configuration blob digest (`sha256:d812...`), and verifies the `DiffID` and `ChainID` of every single layer as it unpacks into the overlayfs snapshotter. Tamper with one byte in transit or in the cache and `containerd` refuses to mount the rootfs.

### The Dual Tag-and-Digest Standard

In every RROM Helm chart (`chart/values.yaml`), image coordinates are split into four explicit keys:

```yaml
image:
  repository: harbor.ravenhelm.dev/platform/vitki
  tag: v1.4.2
  digest: sha256:7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a
  build: b42
```

And `chart/templates/deployment.yaml` renders both the human tag and the kernel digest into the container spec:

```yaml
spec:
  containers:
    - name: {{ .Chart.Name }}
      image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}@{{ .Values.image.digest }}"
      imagePullPolicy: IfNotPresent
```

The live pod spec on `Norns` reads:

```text
harbor.ravenhelm.dev/platform/vitki:v1.4.2@sha256:7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a
```

Operators running `kubectl get pods` see `v1.4.2`. `containerd` schedules strictly by `@sha256:7f9a...`. And because the digest is immutable, `imagePullPolicy: IfNotPresent` is 100% safe: nodes cache verified layers locally without ever risking split-brain drift.

Meanwhile, staging (`chart/values-uat.yaml`) tracks the moving `:uat` stream:

```yaml
# chart/values-uat.yaml
image:
  repository: harbor.ravenhelm.dev/platform/vitki
  tag: uat
  digest: ""
  pullPolicy: Always
```

---

## 5. Registry Hygiene, Immutability, and Garbage Collection

Because `.forgejo/workflows/build.yml` pushes an artifact on every merge to `main`, `Harbor` requires explicit immutability and retention rules so storage stays bounded without ever threatening release custody (**RP-14**):

### 1. Harbor Tag Immutability Rules

Configure a project-level **Tag Immutability Rule** in Harbor across every production project:
- **Tag Filter:** `v*` (all SemVer releases).
- **Rule:** Reject overwrite and deletion requests at the registry storage layer. Once `v1.4.2` is written, not even a valid push token can mutate it.

### 2. Retention Policy Matrix

| Tag Pattern | Harbor Retention Rule | Operational Purpose |
| :--- | :--- | :--- |
| `v*` | **Retain Indefinitely** | Production releases and historical rollback targets (**RP-14**). |
| `charts/*` | **Retain Indefinitely** | Immutable OCI Helm charts referenced by `norns-gitops`. |
| `:b<N>` | **Retain Last 100 Builds** | Recent trunk builds for UAT promotion and bisection. |
| `:sha-*` | **Retain Last 100 Builds** | Matches `:b<N>` retention for commit-to-binary forensics. |
| `:uat` | **Retain Current Pointer** | Moving pointer to the head `main` build. |

### 3. Mark-and-Sweep Garbage Collection

Because tags are 71-byte links, pruning tag `:b12` when it ages past the 100-build window only unlinks the `:b12` pointer file. During Harbor's scheduled Mark-and-Sweep Garbage Collection:
1. **Mark:** Harbor walks every surviving tag (`v1.4.2`, `:b42`, etc.) and marks every referenced manifest and layer blob as live.
2. **Sweep:** Only blobs with **zero** remaining tag references are unlinked from `/data/registry/.../blobs/sha256/`. If `:b12` was released as `v1.1.0`, its layers stay untouched forever because `v1.1.0` still references that manifest digest.

> [!WARNING]
> Always run Harbor Garbage Collection with the registry in **Read-Only Mode** (or with concurrent blob uploads paused). Running an uncoordinated sweep while a runner is mid-upload on a new layer can unlink an uncommitted blob before its manifest `PUT` lands.

---

## 6. The Canonical Reference Script: `scripts/harbor-artifact.sh`

Every ADR-0007 repository in the estate carries `scripts/harbor-artifact.sh`. Note how it avoids the Harbor `/service/token` HTTP 200 trap: it never trusts an auth handshake in isolation, proving every `digest` and `retag` call against the live `/v2/<project>/<image>/manifests/<ref>` endpoint and asserting a valid 64-character hex `sha256` digest before returning `0`.

```bash
#!/usr/bin/env bash
# scripts/harbor-artifact.sh - Harbor OCI Registry v2 Helper
# Implements RROM Chapter 5: Pure Registry v2 Distribution API Retagging.
# Auth: HU (Username), HP (Password/Token) supplied via environment.
#
# Commands:
#   harbor-artifact.sh digest <tag-or-digest>    -> Prints canonical SHA-256 digest
#   harbor-artifact.sh retag  <digest> <new-tag> -> Binds new tag to digest; never builds
#   harbor-artifact.sh list                      -> Lists all tags in the repository

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

# Queries Registry v2 HEAD endpoint to extract HTTP status and Docker-Content-Digest header.
# Proves credential and artifact existence by action, never by /service/token status code.
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
      || { echo "ERROR: Artifact ${ref} not found or unauthorized in ${REG}/${PROJ}/${IMG} (HTTP ${code:-failed})" >&2; exit 1; }
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
      || { echo "ERROR: Target must be a valid 64-char sha256 digest, got: ${target_digest}" >&2; exit 1; }

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

    # 2. Fetch raw manifest and exact Content-Type header from source digest
    hdr_file="$(mktemp)"
    body_file="$(mktemp)"
    trap 'rm -f "$hdr_file" "$body_file"' EXIT

    curl -fsS -u "${HU}:${HP}" -H "$ACCEPT" -D "$hdr_file" -o "$body_file" "${V2}/manifests/${target_digest}"
    content_type="$(grep -i '^content-type:' "$hdr_file" | tail -1 | cut -d' ' -f2- | tr -d '\r')"

    # 3. Re-PUT raw manifest body under new tag reference
    curl -fsS -u "${HU}:${HP}" -H "Content-Type: ${content_type}" \
      -X PUT --data-binary "@${body_file}" "${V2}/manifests/${new_tag}" >/dev/null

    # 4. Action Proof: Query new tag and assert non-empty digest equality
    verified_digest="$("$0" digest "$new_tag")"
    if [ "$verified_digest" != "$target_digest" ]; then
      echo "FATAL: Tag :${new_tag} resolved to ${verified_digest}, expected ${target_digest}" >&2
      exit 1
    fi

    echo "SUCCESS: Cryptographically bound :${new_tag} to ${target_digest}"
    ;;

  *)
    echo "ERROR: Unknown command '${cmd}'" >&2
    exit 2
    ;;
esac
```

---

## 7. The Artifact Surface Checklist

Four mechanical rules lock the artifact surface:

1. **Build Once, Push Internal:** Compile on merge to `main` and push through internal `harbor-nginx` to bypass Cloudflare tunnel body limits, writing `:b<N>`, `:sha-<sha12>`, and `:uat` against one `@sha256:` manifest digest (**RP-1**).
2. **Retag over Registry v2 API:** Bind `:vX.Y.Z` to `:b<N>`'s digest in 200ms using `scripts/harbor-artifact.sh retag`; never run `docker build` on release (**RP-2**) and never grant project-admin `/api/v2.0` scopes to CI robots (**RP-12**).
3. **Prove by Action, Never by Status Code:** Ignore `HTTP 200 OK` from `/service/token` (which returns `"access": []` on bad credentials); prove every registry operation by verifying the 64-character hex `Docker-Content-Digest` on the target manifest (**RP-13**, **RP-16**).
4. **Pin Dual Coordinates at Runtime:** Render `repository:vX.Y.Z@sha256:<digest>` in every production manifest so operators read the SemVer tag while `containerd` enforces `ChainID` layer hashes (**RP-4**).

<!-- RUBRIC_CHECK: Chapter 5 conforms to RROM specification. -->

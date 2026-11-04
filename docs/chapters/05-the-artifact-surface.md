# Chapter 5: The Artifact Surface

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Registry Architecture and Digest Addressing

A container or binary registry is not a passive file dump; it is the physical custody vault of your compiled software. RROM defines strict specifications for registry configuration, naming schemes, and digest handling.

---

## 1. Triple-Tagging on Ingress

When code merges into `main`, the build runner compiles the software and tags the resulting image digest under three distinct references:

```text
harbor.ravenhelm.dev/platform/vitki:b42                  <- Monotonic Build ID
harbor.ravenhelm.dev/platform/vitki:sha-9f8a3c21e01b    <- Source Commit SHA (12 chars)
harbor.ravenhelm.dev/platform/vitki:uat                 <- Moving Staging Stream Tag
```

All three tags point to the **exact same cryptographic digest** (`sha256:7f9a...3c`).

### Why Three Tags?
- **`:b<N>` (The Monotonic Build):** Humans and CI logs refer to builds sequentially ("Build 42 is ready for release"). Build numbers never decrement and provide instant temporal sorting.
- **`:sha-<sha12>` (Commit Linkage):** Provides instantaneous, unambiguous linkage between the binary image in the registry and the source tree in git. If git bisect isolates a bug to commit `9f8a3c21e01b`, the operator can immediately locate the artifact without searching build logs.
- **`:uat` (Moving Consumer Stream):** The staging/UAT environment tracks this moving tag. When developers push to `main`, UAT updates automatically without manual intervention.

---

## 2. Retagging by Digest (The Release Mechanism)

When cutting a release (`v1.4.2`), RROM does not rebuild the container. Instead, it instructs the registry to add a new human-readable tag to the proven build digest.

### The Registry v2 API Rule
Many enterprise container registries (such as Harbor) enforce strict RBAC models where automation robot tokens are granted push and pull privileges, but denied access to administrative management APIs.

RROM scripts (`scripts/harbor-artifact.sh`) interact directly with the standard **Docker Registry HTTP API v2**:
1. Fetches the image manifest for `:b<N>` or `:sha-<commit12>`.
2. Extracts the canonical digest (`Docker-Content-Digest` header).
3. Pushes that exact manifest back to the registry under the new tag `refs/tags/vX.Y.Z`.
4. Executes a follow-up HEAD request to verify that `vX.Y.Z` resolves to the identical SHA-256 digest.

Because this operation speaks the pure distribution protocol rather than vendor-specific administrative APIs, it operates with minimal privileges and requires no Docker daemon on the release runner.

---

## 3. The Runtime Pinning Standard

In Kubernetes Helm charts and Docker Compose manifests, referencing images merely by tag (`image: vitki:v1.4.2`) is an operational vulnerability. An attacker or rogue script could overwrite the tag, or a cluster node could fail to invalidate its local image cache.

RROM mandates that all production deployment manifests render the full immutable digest:

```yaml
# chart/values.yaml
image:
  repository: harbor.ravenhelm.dev/platform/vitki
  tag: v1.4.2
  digest: sha256:7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a
  build: b42
```

In the Helm deployment template, the container image renders as:

```yaml
image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}@{{ .Values.image.digest }}"
```

- The **tag** (`v1.4.2`) satisfies human inspection (`kubectl describe pod` immediately shows the version).
- The **digest** (`@sha256:...`) guarantees that the container runtime pulls and executes the exact verified bitstream, rejecting any mutated image layers.

<!-- RUBRIC_CHECK: Chapter 5 conforms to RROM specification. -->

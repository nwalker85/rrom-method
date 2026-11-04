# Chapter 2: The Core Axiom

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## The Axiom Stated

At the heart of the Ravenhelm Release Operations Methodology lies a single governing law:

> ### **Builds are the unit; releases are names.**
> *A build is an immutable artifact produced once. A release is an authorized name assigned to an existing build. A deployment is the declarative reconciliation of a target environment to that named artifact.*
> 
> **Releases never rebuild code.**

This axiom, formalized in estate doctrine under **ADR 0007** (with the Vitki reference implementation), fundamentally restructures the relationship between version control, artifact storage, and runtime orchestration.

---

## Deconstructing the Three Lifecycle Stages

Traditional CI/CD collapses compilation, tagging, and deployment into a chaotic single step. RROM cleanly separates them into three independent lifecycle stages with hard boundary gates.

```
+-----------------------------------------------------------------------------------+
| 1. THE BUILD (THE UNIT)                                                           |
| Trigger: Merge to main branch                                                     |
| Output:  Immutable OCI Image / Binary Bundle                                      |
| Identity: :b<N> (Monotonic ID) + :sha-<commit12> + @sha256:<digest>               |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼ (Zero Rebuilds)
+-----------------------------------------------------------------------------------+
| 2. THE RELEASE (THE NAME)                                                         |
| Trigger: Release PR + Annotated SemVer Git Tag                                    |
| Action:  Assigns vX.Y.Z name to existing build digest in registry                 |
| Gate:    check-release-source-parity.sh proves zero code drift                    |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼ (Declarative Pull)
+-----------------------------------------------------------------------------------+
| 3. THE DEPLOYMENT (CONVERGENCE)                                                   |
| Trigger: GitOps Repository Pull / Tap Update / OTA Manifest Sync                  |
| Action:  Argo CD / Package Manager / App Updater pulls pinned digest              |
| Proof:   Runtime health probes verified on live network interface                |
+-----------------------------------------------------------------------------------+
```

### 1. The Build is the Physical Unit
A build is the tangible, immutable output of a deterministic compilation process. It occurs on ingress—the exact moment source code is merged into the integration trunk (`main`).
- It produces an artifact identified by a monotonic build sequence (`:b42`), the commit SHA (`:sha-9f8a3c21e01b`), and its immutable SHA-256 digest (`sha256:7f9a...3c`).
- In multi-tenant or multi-stage environments, this exact artifact is immediately attached to a moving staging stream (`:uat`). Staging exercises the exact bits that will eventually ship to production.

### 2. The Release is an Authorized Name
A release is pure metadata. It does not compile source code, execute bundlers, or invoke container build daemons.
- When an existing build in UAT proves stable, an operator cuts a release by giving that build a Semantic Versioning name (`v1.4.2`).
- The release mechanism looks up the existing build digest in the artifact registry and adds the tag `v1.4.2` to that identical digest.
- The release commit in git modifies **only** metadata files: the Helm chart version, the values digest pin, and the changelog. It is cryptographically proven to have zero source code changes relative to the build commit.

### 3. The Deployment is Declarative Reconciliation
A deployment is the convergence of an environment toward a declared state.
- Neither developers nor CI runners push bits to production servers.
- The declarative GitOps orchestrator (e.g., Argo CD on Kubernetes) observes that the configuration repository has updated its pinned image digest to `sha256:7f9a...3c` and reconciles the cluster pods to match.
- Deployment completes only when post-sync runtime health checks pass on the live running system.

---

## Why "Build on Tag" is an Anti-Pattern

Most teams configure their CI systems to trigger container builds when a git tag (`v*`) is pushed. This pattern suffers from fatal structural flaws:

1. **Environmental Divergence:** The tagged build executes minutes, days, or weeks after the code was merged to `main`. Transient package updates in upstream registries (e.g., PyPI, npm, Alpine package mirrors) can silently alter binary behavior between staging and production.
2. **Digest Amnesia:** Because the tag creates a new build, the cryptographic digest running in production has no historical verification record in staging logs.
3. **Elevated Attack Surface:** Building artifacts at release time requires storing production compilation secrets, npm tokens, and SSH keys inside release runner environments, violating least-privilege security principles. Under RROM, the release workflow needs only push/pull access to retag an existing registry digest.

<!-- RUBRIC_CHECK: Chapter 2 conforms to RROM specification. -->

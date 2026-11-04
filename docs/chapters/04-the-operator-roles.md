# Chapter 4: The Operator Roles

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Sovereign Human and Agent Responsibilities

In traditional organizations, release responsibilities are muddled across developers, DevOps engineers, and product managers. When a deployment fails, accountability is diluted. Under RROM, release management is partitioned into three distinct, non-overlapping roles:

```
[ Engineer / Agent ] ──> [ Release Custodian ] ──> [ Delivery Closer ] ──> [ Gatekeeper ]
      Authored Diff            Prepares Release            Merges & Ships        Elevates Cutover
```

---

## 1. The Author (Engineer or Autonomous Coding Agent)
The Author produces the application feature, bug fix, or refactor.
- **Boundaries:** The Author works within a disposable git worktree on an isolated branch.
- **Deliverable:** A clean pull request containing application source changes, unit tests, and documentation updates.
- **Ceiling:** The Author never tags a release, never edits production Helm values digests, and never pushes directly to `main`.

## 2. The Release Custodian
The Release Custodian is the guardian of artifact provenance and release metadata. This role may be fulfilled by a human technical lead or an automated release daemon.
- **Responsibilities:**
  1. Inspects the integration stream on `main` and identifies the target build (`:b<N>`).
  2. Verifies that the build has passed automated test suites in the UAT/staging environment.
  3. Executes `scripts/release-pr.sh b<N> vX.Y.Z` to generate the release pull request.
  4. Enforces the **Release Parity Rule**: verifies that the release PR modifies *only* chart configurations, changelogs, and digest pins—with zero diff in application source.
  5. Formulates the annotated git tag pointing to the build's underlying commit SHA.

## 3. The Delivery Closer (The Supervisor)
The Delivery Closer is the sole authority empowered to approve and execute production release mergers.
- **The Standing Directive:** Approval to merge a release PR is approval to ship that merge to production. The Delivery Closer does not merge a PR and walk away; they shepherd the release through artifact retagging, gitops repo updates, and live health verification.
- **Single-Handed Execution:** The session that receives human authorization to ship must personally execute the merge. This responsibility cannot be delegated to subordinate workers, ensuring unbroken continuity of custody.
- **Proof of Life:** The Delivery Closer terminates their session only when runtime health probes confirm the new build digest is actively serving live production traffic.

## 4. The Gatekeeper (Valkyrie Human-in-the-Loop)
Certain operational events carry catastrophic blast radii. These are designated as **Elevation Events**:
- Modifying identity provider configurations (Keycloak/Zitadel).
- Altering vault policies or secrets engine mounts (OpenBao).
- Modifying artifact registry access rules (Harbor RBAC).
- Executing an architectural cutover (database migration, queue swap).

For elevation events, the Gatekeeper role activates:
- The CI pipeline executes `terraform plan` or equivalent validation in read-only mode and computes a cryptographic SHA-256 hash of the generated plan.
- The pipeline pauses, issuing a structured Multi-Factor Action Approval (MFAA) challenge to the authorized human Gatekeeper.
- The Gatekeeper inspects the plan and signs the approval challenge.
- The CI pipeline verifies that the approval token matches the exact SHA-256 hash of the plan, applies the elevation, and immediately consumes the single-use token.

<!-- RUBRIC_CHECK: Chapter 4 conforms to RROM specification. -->

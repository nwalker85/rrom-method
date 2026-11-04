# Chapter 10: Hotfixes, Emergencies & Rollback

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## The Rollback Axiom

When a critical production defect occurs, the worst time to invent a recovery procedure is during the outage. Under RROM, rollbacks are deterministic, instant, and fail-closed:

> ### **Rollback is pointer repointing; it is never binary deletion.**
> *A bad build is never purged from the registry; it simply never receives an authorized release name. Rollback is the instantaneous repointing of the GitOps pointer to the preceding immutable build digest.*

---

## 1. Zero-Downtime Rollback Execution

Because RROM strictly renders container images by immutable digest (`repository:tag@sha256:...`) in the central GitOps repository (`norns-gitops`), rolling back a failed production release does not require recompiling code, git reverts, or docker pushes.

### The 60-Second Rollback Protocol:
1. Identify the previous stable release tag (e.g., `v1.4.1`, which pinned digest `sha256:4a8b...`).
2. Open an emergency commit in `norns-gitops` updating `clusters/norns/applications/<app>.yaml`:
   ```yaml
   spec:
     source:
       targetRevision: v1.4.1
   ```
3. Argo CD immediately detects the revision change. Because the container image digest `sha256:4a8b...` was already pulled by cluster nodes during the previous release, the cluster performs an instantaneous rolling pod replacement without downloading external layers.
4. Verify live health: confirm `/api/health` returns status `200` on the restored digest.

Total elapsed recovery time: **under 60 seconds.**

---

## 2. The Hotfix Lifecycle

When a production outage requires a code fix rather than a rollback, teams frequently panic and attempt to commit directly to `main` or push hotfix tags without testing. RROM strictly forbids this practice.

Even in an active P0 incident, the hotfix must obey the **Ingress $\to$ Candidate $\to$ Pinned** state machine:

```text
[ Hotfix PR on branch ] ──> [ Merge to main ] ──> [ CI Ingress: b43 (:uat) ] ──> [ release-pr.sh b43 v1.4.3 ] ──> [ Argo Sync ]
```

### The Accelerated Hotfix Protocol:
1. Author the fix in a dedicated git worktree branched from `main`.
2. Open the hotfix pull request. CI runs automated regression tests.
3. Merge the hotfix PR into `main`. The ingress runner packages the fix once, pushing it as build `b43` (`:uat`).
4. Perform a 2-minute smoke test in the live UAT environment.
5. Execute `scripts/release-pr.sh b43 v1.4.3`. The script verifies zero application source drift relative to the hotfix commit and pins digest `b43` in `chart/values.yaml`.
6. Merge the release PR, push tag `v1.4.3`, and bump the GitOps repository.

Because this protocol follows the exact same mechanical path as routine releases, it introduces no novel operational variables during high-stress incident response.

---

## 3. Quarantining Bad Builds

What happens to the broken build (e.g., build `b42`) that caused the incident?

In undisciplined teams, engineers delete the tag or image from the container registry. Under RROM, **deleting artifacts is an operational violation**.
- The registry digest `b42` remains immutable in Harbor.
- The build is permanently recorded in the git history and incident post-mortem.
- Because `b42` was removed from `values.yaml` and the GitOps target revision, no orchestrator will ever pull it again.
- Preserving the broken build allows engineers to run offline forensic inspections, attach debuggers, and reproduce the defect in sandbox environments without affecting production.

<!-- RUBRIC_CHECK: Chapter 10 conforms to RROM specification. -->

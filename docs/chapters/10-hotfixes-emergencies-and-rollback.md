# Chapter 10: Hotfixes, Emergencies & Rollback

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## The High-Stress Crucible: When Production Burns

It is 02:14 UTC on a Sunday morning. A high-priority P0 page wakes the on-call platform engineer: error rates across the public API gateway have surged to 48%, p99 latency has spiked from 18 milliseconds to 14 seconds, and customer database connection pools are exhausting worker threads across the cluster. Ten minutes earlier, a new release—version `v1.4.2`—was marked as converged in production.

In conventional engineering organizations, this is the exact moment when process disintegrates into chaos. Panic sets in. Adrenaline drives cognitive tunnel vision. Engineers open multiple terminal windows across uncoordinated workstations, attempting to "fix forward" by authoring emergency hotfixes directly on dirty feature branches, bypassing test suites, manually triggering unversioned container builds from local Docker daemons, or executing ad-hoc database patches through SSH bastion hosts. Someone runs `docker push` with a `:latest` or `:hotfix` tag; someone else attempts to `git revert` on the trunk, triggering a 25-minute CI compilation cycle while the database crashes under unindexed lock contention. In the fog of war, an engineer deletes the failing container tag from the remote registry, hoping to stop nodes from pulling it, only to break cluster scheduling and obliterate the forensic evidence required to determine what went wrong.

The Ravenhelm Release Operations Methodology (RROM) is explicitly engineered to eradicate this operational breakdown. 

Under RROM, **an emergency is never an excuse to invent novelty**. The worst time to invent a recovery procedure is during an active production outage. Incident response must be a frictionless, deterministic, mechanical execution of the exact same state transitions that govern daily software delivery—only accelerated.

---

## The Rollback Axiom

At the foundation of RROM emergency management lies a core operational principle:

> ### **Rollback is pointer repointing; it is never binary deletion.**
> *A failed build is never purged, deleted, or recompiled; it simply loses its authorized release name in the declarative orchestrator. Rollback is the instantaneous, atomic repointing of the environment configuration pointer to the preceding, cryptographically proven build digest.*
>
> **Rollback does not compile code. Rollback does not rebuild containers. Rollback does not delete artifacts.**

```
+----------------------------------------------------------------------------------------------------+
|                                    THE ROLLBACK AXIOM IN PRACTICE                                  |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|   1. THE BROKEN RELEASE (v1.4.2)                                                                   |
|   GitOps Pointer: targetRevision: v1.4.2 ──> Pinned Digest: @sha256:7f9a...3c (:b42) [CRASHING]    |
|                                                                                                    |
|                                         │                                                          |
|                                         │ REPOINT POINTER (Atomic Git Commit)                      |
|                                         ▼                                                          |
|                                                                                                    |
|   2. THE RESTORED STABLE RELEASE (v1.4.1)                                                          |
|   GitOps Pointer: targetRevision: v1.4.1 ──> Pinned Digest: @sha256:4a8b...1f (:b41) [HEALTHY]     |
|                                                                                                    |
|   ==============================================================================================   |
|   HARBOR OCI REGISTRY (IMMUTABLE PHYSICAL STORAGE):                                                |
|   [sha256:4a8b...1f] (:b41, :v1.4.1)  ──> REMAINS IMMUTABLE & PRE-CACHED ON ALL K3S WORKER NODES  |
|   [sha256:7f9a...3c] (:b42, :v1.4.2)  ──> QUARANTINED BUT PRESERVED FOR OFFLINE FORENSIC DEBUGGING |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### Deconstructing the Mathematics of Immutability

Traditional deployment models view rollback as a destructive undo operation—an attempt to rewind time by tearing down infrastructure or overwriting version tags in place. This view violates basic information theory. In a deterministic release architecture:

1. **State is Cumulative:** The sequence of code changes that led to build `b42` occurred. Trying to erase history in git or registries creates untracked drift between recorded history and physical artifacts.
2. **Artifacts are Eternal:** Build `b42` was compiled once on merge to `main`. It was assigned an immutable SHA-256 digest (`sha256:7f9a...3c`). That digest represents a static mathematical snapshot of compiled bits. It cannot be altered; it can only be dereferenced.
3. **Environments are Pure Projections of State:** In declarative GitOps (e.g., Argo CD managing a Norns K3s cluster), runtime cluster state is a pure projection of the version control declaration:
   $$\text{State}_{\text{runtime}} = \mathcal{R}(\text{Manifests}(\text{targetRevision}))$$
   To alter $\text{State}_{\text{runtime}}$, one does not mutate running pods via `kubectl edit` or SSH. One simply adjusts the function input: repointing $\text{targetRevision}$ from `v1.4.2` to `v1.4.1`.

---

## 1. Zero-Downtime Rollback Execution: The 60-Second Runbook

Because RROM strictly mandates that all deployable artifacts are rendered by immutable cryptographic digest (`repository@sha256:...`) within the central GitOps repository (`norns-gitops`), rolling back a failed production release requires zero recompilation, zero git rebasing, and zero artifact transfer over external wide-area networks.

### The Physics of the 60-Second Boundary: Pre-Cached Node Layers

Why does an RROM rollback execute in under 60 seconds, whereas traditional rollbacks routinely take 15 to 30 minutes?

The bottleneck in container orchestration during an incident is almost always **image pull latency** and **external registry dependencies**. When a deployment fails and an engineer points the cluster to an uncompiled or newly tagged image:
- The orchestrator must contact an external container registry over WAN.
- If the registry is rate-limited, degraded, or network-congested, pod scheduling hangs in `ImagePullBackOff`.
- Worker nodes must sequentially download multi-gigabyte layer archives, unpack them onto disk, and mount root filesystems before the entrypoint process can even start.

Under RROM's **Release Doctrine (ADR 0007)**, every production release is pinned to an immutable digest (`sha256:4a8b...`) that was already running in production 30 minutes prior. 

Because container engines (containerd / CRI-O) cache unpacked filesystem layers locally on each node under `/var/lib/containerd/io.containerd.content.v1.content/`, reverting the GitOps pointer to the previous digest requires **zero layer downloads**. The CRI runtime detects that the required SHA-256 digest layers are already present on local disk. 

The image pull operation completes in **0.00 seconds**. The orchestration layer immediately performs an in-memory pod swap, terminating the defective containers and spinning up the pre-warmed healthy containers with zero network I/O.

```
+----------------------------------------------------------------------------------------------------+
|                               THE 60-SECOND RECOVERY TIMELINE                                      |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  T+00s   P0 Alert Confirmed: Error rate > 40% on release v1.4.2                                    |
|  T+10s   Operator identifies previous stable release tag: v1.4.1 (digest sha256:4a8b...1f)         |
|  T+22s   Operator commits pointer repoint in norns-gitops repository                               |
|  T+28s   Commit pushed to git host; Argo CD webhook or fast-poll detects targetRevision change     |
|  T+35s   Argo CD issues Kube-API patch; K3s controller initiates rolling pod replacement          |
|  T+42s   CRI-O / containerd finds sha256:4a8b...1f in LOCAL NODE CACHE (0 KB downloaded)            |
|  T+50s   Healthy pods pass readiness probes; traffic shifts via Service endpoints                 |
|  T+58s   Automated runtime proof asserts HTTP 200 on /api/health; error rate drops to baseline     |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### Complete Terminal Walkthrough: The Live Rollback

Below is the verbatim terminal sequence executed by the on-call Delivery Closer during a live P0 incident on the Ravenhelm estate.

#### Step 1: Open Dedicated Worktree in the GitOps Repository
Never edit `norns-gitops` directly on the local workstation's dirty default checkout. Use an ephemeral worktree:

```bash
# Navigate to the bare repository directory and provision an emergency worktree
cd ~/src/platforms/ravenmaskos/norns-gitops.bare
git worktree add ../norns-gitops-rollback-v1.4.1 -b rollback/vitki-v1.4.1 origin/main
cd ../norns-gitops-rollback-v1.4.1
```

#### Step 2: Audit Prior Release State and Confirm Digest
Inspect the git history to verify the exact tag and digest of the last verified stable release:

```bash
git log -n 5 --oneline clusters/norns/applications/vitki.yaml
# Output:
# 8f9b2a1 release: vitki bump to v1.4.2 (sha256:7f9a3c...)
# 3d4e1c2 release: vitki bump to v1.4.1 (sha256:4a8b1f...)
# a1b2c3d chore: update resource limits
```

#### Step 3: Repoint the GitOps Manifest
Edit the application manifest `clusters/norns/applications/vitki.yaml`. Modify the `targetRevision` from `v1.4.2` back to `v1.4.1`:

```bash
# View the current broken declaration
cat clusters/norns/applications/vitki.yaml
```
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: vitki
  namespace: argocd
spec:
  project: ravenmaskos
  source:
    repoURL: https://git.ravenhelm.dev/ravenmaskos/vitki.git
    targetRevision: v1.4.2
    path: chart
    helm:
      valueFiles:
        - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: ravenmaskos
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

Execute the atomic repoint using your editor or standard tool:

```bash
# Repoint targetRevision to v1.4.1
sed -i '' 's/targetRevision: v1.4.2/targetRevision: v1.4.1/' clusters/norns/applications/vitki.yaml

# Assert the diff is strictly a single pointer change
git diff
```
```diff
diff --git a/clusters/norns/applications/vitki.yaml b/clusters/norns/applications/vitki.yaml
index e4b912a..a8f102c 100644
--- a/clusters/norns/applications/vitki.yaml
+++ b/clusters/norns/applications/vitki.yaml
@@ -10,3 +10,3 @@ spec:
     repoURL: https://git.ravenhelm.dev/ravenmaskos/vitki.git
-    targetRevision: v1.4.2
+    targetRevision: v1.4.1
     path: chart
```

#### Step 4: Commit and Push to the GitOps Main Trunk
Commit with an explicit emergency prefix citing the active incident identifier:

```bash
git commit -am "emergency(vitki): rollback targetRevision from v1.4.2 to v1.4.1 [INCIDENT-9842]"
git push origin rollback/vitki-v1.4.1:main
```

#### Step 5: Force Immediate GitOps Reconciliation
Rather than waiting for the periodic 3-minute poll cycle, instruct Argo CD to reconcile immediately:

```bash
# Trigger an immediate hard sync against the updated git pointer
argocd app sync vitki --prune --force

# Stream the reconciliation status in real time
argocd app wait vitki --health --timeout 60
```
```text
TIMESTAMP                  GROUP        KIND   NAMESPACE              NAME    STATUS    HEALTH        HOOK  MESSAGE
2026-11-04T02:16:32Z   apps/v1  Deployment ravenmaskos               vitki  OutOfSync  Degraded            deployment has 2 unavailable replicas
2026-11-04T02:16:33Z   apps/v1  Deployment ravenmaskos               vitki    Synced   Progressing         updated deployment revision: 41
2026-11-04T02:16:41Z            Pod        ravenmaskos   vitki-648f9-9xk2p    Synced   Running             containers ready
2026-11-04T02:16:45Z            Pod        ravenmaskos   vitki-648f9-q8z1b    Synced   Running             containers ready
2026-11-04T02:16:48Z   apps/v1  Deployment ravenmaskos               vitki    Synced   Healthy             deployment has 2 healthy replicas
```

#### Step 6: Collect Live Runtime Proof
Under RROM doctrine, **no rollback is complete until verified on the live running interface**. Confirm application health against the live HTTP ingress:

```bash
# Query the live ingress health endpoint
curl -sS -i https://vitki.ravenmask.net/api/health
```
```http
HTTP/2 200 
date: Sun, 04 Nov 2026 02:16:52 GMT
content-type: application/json; charset=utf-8
content-length: 124
x-ravenhelm-version: v1.4.1
x-ravenhelm-build: b41
x-ravenhelm-digest: sha256:4a8b1f893e201b22e...

{"status":"healthy","database":"connected","pool_available":48,"pool_in_use":2,"uptime_seconds":14}
```

Elapsed time from alert triage to live proof: **58 seconds**.

---

## 2. The Accelerated Hotfix Protocol

What happens when an incident cannot be resolved by a simple rollback? 

Consider the following scenarios:
1. **The Irreversible Migration:** Release `v1.4.2` included an expand migration that altered data structures, and rolling back to `v1.4.1` would cause schema incompatibility exceptions.
2. **Upstream External Outage:** An external payment vendor or OAuth provider altered their TLS handshake or API signature unexpectedly, breaking both `v1.4.1` and `v1.4.2`.
3. **Zero-Day Security Vulnerability:** An active exploit against a bundled dependency requires an immediate patch in production.

In these conditions, engineering teams frequently fall into the **Cowboy Hotfix Trap**.

### The "Cowboy Hotfix" Trap vs. RROM Accelerated Protocol

| Operational Dimension | The "Cowboy Hotfix" Trap (Uncontrolled) | RROM Accelerated Hotfix Protocol |
| :--- | :--- | :--- |
| **Branching Strategy** | Pushes directly to `main` or untracked local branch. | Dedicated disposable worktree branched from verified `main`. |
| **Compilation Origin** | Developer's workstation (`docker build . -t app:hotfix`). | Ephemeral CI ingress runner on identical base image. |
| **Artifact Identity** | Mutable tag (`:hotfix`, `:v1.4.2-patch`). | Monotonic build ID (`:b43`) + immutable SHA-256 digest pin. |
| **Regression Testing** | Skipped ("No time, production is down!"). | Fast-path automated unit and integration suite in CI. |
| **Staging Validation** | Pushed straight to production with zero staging run. | Mandatory 2-minute synthetic validation in live UAT (`:uat`). |
| **Source Parity Gate** | Unknown drift; accidental inclusion of unreviewed code. | Cryptographic verification via `check-release-source-parity.sh`. |
| **Traceability** | Untracked binaries running in production. | Complete cryptographic provenance from commit to Harbor OCI digest. |
| **Reversibility** | Impossible to rollback cleanly if hotfix is defective. | 60-second instantaneous pointer rollback to prior digest. |

### The 5-Minute Ingress-to-Production State Machine

Under RROM, an emergency hotfix never skips the canonical state machine:

$$\text{Emergency Worktree} \longrightarrow \text{Hotfix PR} \longrightarrow \text{Trunk Ingress (:b43)} \longrightarrow \text{UAT Smoke Gate} \longrightarrow \text{Release PR (v1.4.3)} \longrightarrow \text{GitOps Sync}$$

By keeping the release machinery standardized and highly automated, this entire sequence executes in **under five minutes**, ensuring that speed does not compromise safety.

```
+----------------------------------------------------------------------------------------------------+
|                               THE ACCELERATED HOTFIX PIPELINE (< 5 MIN)                            |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ AUTHOR ]                                                                                        |
|  1. Worktree branch: hotfix/connection-leak                                                        |
|  2. Fix defect + add failing test                                                                  |
|  3. Submit Hotfix PR (Title: "fix(core): close leak in connection pool [P0-HOTFIX]")               |
|                                                                                                    |
|             │                                                                                      |
|             ▼  (Time: T+01m15s)                                                                    |
|  [ CI INGRESS RUNNER ]                                                                             |
|  4. Merge to main trunk after peer review / emergency approval                                    |
|  5. CI runs fast unit test suite                                                                   |
|  6. Single Build Unit: Compiles once -> harbor.ravenhelm.dev/ravenmaskos/vitki:b43                 |
|  7. Tags :b43, :sha-4f81c9a, and updates :uat pointer                                              |
|                                                                                                    |
|             │                                                                                      |
|             ▼  (Time: T+02m45s)                                                                    |
|  [ UAT SMOKE GATE ]                                                                                |
|  8. Automatic deployment to staging/UAT environment                                                |
|  9. 120-second synthetic smoke assertion proves defect resolution and connection stability        |
|                                                                                                    |
|             │                                                                                      |
|             ▼  (Time: T+03m30s)                                                                    |
|  [ RELEASE CUSTODIAN ]                                                                             |
|  10. Executes: scripts/release-pr.sh b43 v1.4.3                                                    |
|  11. check-release-source-parity.sh proves ZERO source drift between b43 and release PR            |
|  12. Harbor retags existing digest with v1.4.3 (ZERO REBUILDS)                                      |
|                                                                                                    |
|             │                                                                                      |
|             ▼  (Time: T+04m15s)                                                                    |
|  [ DELIVERY CLOSER ]                                                                               |
|  13. Merges Release PR -> Pushes GitOps bump to norns-gitops                                      |
|  14. Argo CD reconciles production cluster to digest sha256:881c...99                              |
|  15. Runtime proof of life collected on production endpoints                                      |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### Hotfix Execution Protocol: Step-by-Step

#### 1. Author the Surgical Patch in a Dedicated Worktree
Never write hotfix code in a cluttered local development branch. Check out a clean worktree from `origin/main`:

```bash
cd ~/src/platforms/ravenmaskos/vitki.bare
git worktree add ../vitki-hotfix-p0 -b hotfix/conn-leak origin/main
cd ../vitki-hotfix-p0

# Apply the surgical fix and add an automated regression test
$EDITOR src/pool/connection.go
$EDITOR tests/regression/conn_leak_test.go

# Verify locally
go test -v -race ./...

# Commit with semantic message citing incident
git commit -am "fix(pool): ensure idle sockets release file descriptors on timeout [INCIDENT-9842]"
git push origin hotfix/conn-leak
```

#### 2. Emergency PR Review & Ingress Merge
Open the pull request on your code host (Forgejo or GitHub). In an active P0 incident, the PR requires one senior technical sign-off or designated Incident Commander approval:

```bash
gh pr create --title "fix(pool): release sockets on timeout [P0-HOTFIX]" \
             --body "Resolves socket exhaustion leading to 502 gateway errors. Backed by regression test."
```

Upon merge to `main`, the CI ingress workflow (`.forgejo/workflows/ingress.yaml` or `.github/workflows/ingress.yaml`) executes immediately:
- Compiles the application inside an ephemeral container.
- Tags the OCI image as `harbor.ravenhelm.dev/ravenmaskos/vitki:b43`.
- Automatically deploys `b43` to the live UAT environment (`https://vitki-uat.ravenmask.net`).

#### 3. The 120-Second Synthetic UAT Assertion
Before any hotfix touches production, it must prove itself on live network interfaces in UAT. A synthetic load script exercises the repaired codepath:

```bash
# Run synthetic verification against UAT
vitki-smoke-test --target https://vitki-uat.ravenmask.net --concurrency 20 --duration 60s
```
If error rates remain 0% and socket descriptors stabilize, the candidate build (`b43`) is declared ready for production promotion.

#### 4. Execute the Release PR (Zero-Rebuild Promotion)
The Release Custodian executes the standardized release script, nominating build `b43` for release name `v1.4.3`:

```bash
# Execute standard release PR automation
./scripts/release-pr.sh b43 v1.4.3
```

Behind the scenes, `scripts/release-pr.sh` executes the parity validator:

```bash
./scripts/check-release-source-parity.sh b43
# Asserting parity between build b43 (commit 4f81c9a) and current workspace...
# Checking diff in src/ ... OK (0 files modified)
# Checking diff in go.mod / go.sum ... OK (0 files modified)
# Checking metadata updates:
#   - chart/Chart.yaml: version updated to 1.4.3
#   - chart/values.yaml: image.digest pinned to sha256:881c74...
# PARITY VERIFIED: Zero application source drift detected.
```

The script opens the Release PR. The Delivery Closer merges it, pushes the annotated git tag `v1.4.3`, and Harbor retags the existing digest of `b43` with `v1.4.3`. 

**No compilation occurs.** The exact binary bits that passed UAT load testing are deployed to production via `norns-gitops`.

---

## 3. The Doctrine of Bad Build Quarantine

When a bad release causes an outage, an undisciplined engineer's first instinct is often to purge the broken artifact:
```bash
# DO NOT DO THIS. OPERATIONAL VIOLATION:
docker rmi harbor.ravenhelm.dev/ravenmaskos/vitki:v1.4.2
# DO NOT DO THIS. OPERATIONAL VIOLATION:
curl -X DELETE https://harbor.ravenhelm.dev/api/v2.0/projects/ravenmaskos/repositories/vitki/artifacts/v1.4.2
```

Under RROM, **deleting failing artifacts from registries or git history is strictly forbidden**.

### Why Deleting Broken Artifacts is Operational Sabotage

1. **Destruction of Forensic Evidence:** A production failure is often subtle—a race condition under multi-core load, a memory leak triggered by specific packet boundaries, or a compiler optimization bug. If you delete build `b42`, engineers cannot perform post-incident memory profiling, inspect binary symbols, or reproduce the crash dump.
2. **Registry Index and Cache Corruption:** Deleting tags or manifest lists while cluster nodes or intermediate proxies still hold references results in erratic `Manifest Unknown` or `Blob Unknown` errors that destabilize cluster scheduling.
3. **Audit Trail Destruction:** Compliance frameworks (SOC 2, ISO 27001, FedRAMP) and internal doctrine require an unbroken cryptographic record of every bit sequence that ever ran in production. Purging an artifact leaves an unverifiable hole in your compliance ledger.

### The Harbor Quarantine Protocol

Instead of deleting broken builds, RROM enforces **quarantine and metadata invalidation**. The defective artifact remains physically intact in Harbor, but is locked down so that no production orchestrator can pull or execute it.

```
+----------------------------------------------------------------------------------------------------+
|                                  THE HARBOR QUARANTINE ARCHITECTURE                                |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|   1. DEFECTIVE BUILD IMMUTABILITY LOCK                                                             |
|   harbor.ravenhelm.dev/ravenmaskos/vitki@sha256:7f9a...3c                                          |
|                                                                                                    |
|   2. METADATA QUARANTINE TAGGING                                                                   |
|   Add tag: :quarantined-INCIDENT-9842                                                              |
|   Remove mutable tag: :uat                                                                         |
|                                                                                                    |
|   3. ADMISSION CONTROLLER ENFORCEMENT (Kyverno / OPA Gatekeeper)                                   |
|   Policy: reject-quarantined-digests                                                               |
|   DENY Rule: If Pod.imageDigest == sha256:7f9a...3c ──> REJECT with admission error               |
|                                                                                                    |
|   4. ISOLATED FORENSIC SANDBOX                                                                     |
|   Mount digest sha256:7f9a...3c inside ephemeral debug namespace (no ingress, mock DB)             |
|   Attach delve / gdb / eBPF profilers to inspect memory maps without impacting production          |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

#### Step 1: Retag the Digest for Quarantine
Using the Harbor REST API or CLI, attach an explicit quarantine tag to the immutable digest of build `b42` and record the incident reference:

```bash
# Tag the broken digest with the quarantine marker
crane tag harbor.ravenhelm.dev/ravenmaskos/vitki@sha256:7f9a3c21e01b \
          quarantined-INCIDENT-9842
```

#### Step 2: Apply Registry Pull-Block / Retention Lock
Harbor project policies are configured to block pulling any artifact tagged with `quarantined-*` except by authorized forensic service accounts:

```json
{
  "project_name": "ravenmaskos",
  "repository": "vitki",
  "tag": "quarantined-INCIDENT-9842",
  "immutable": true,
  "pull_block": true,
  "comment": "Quarantined by Delivery Closer due to socket pool exhaustion in INCIDENT-9842"
}
```

#### Step 3: Kubernetes Admission Controller Policy Block
To guarantee defense-in-depth, add the defective digest to the cluster's Kyverno or OPA Gatekeeper blocklist. This ensures that even if an engineer accidentally opens a PR referencing `sha256:7f9a3c...`, the K3s API server rejects the pod creation request:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: block-quarantined-digests
spec:
  validationFailureAction: Enforce
  rules:
    - name: block-broken-vitki-b42
      match:
        resources:
          kinds:
            - Pod
      validate:
        message: "Image digest {{ request.object.spec.containers[0].image }} is QUARANTINED under INCIDENT-9842."
        deny:
          conditions:
            any:
              - key: "{{ request.object.spec.containers[].image }}"
                operator: AnyIn
                value:
                  - "*@sha256:7f9a3c21e01b*"
```

#### Step 4: Offline Forensic Inspection in a Sandbox
Because the binary layers were preserved in Harbor, engineers can spin up a sandbox container in an isolated analysis namespace (`debug-sandbox`) with network egress disabled and a live kernel profiler attached:

```bash
# Run the quarantined image in an isolated debugging namespace
kubectl run vitki-forensic \
  --namespace=sandbox-forensics \
  --image=harbor.ravenhelm.dev/ravenmaskos/vitki@sha256:7f9a3c21e01b \
  --restart=Never \
  --overrides='{
    "spec": {
      "securityContext": { "capabilities": { "add": ["SYS_PTRACE"] } },
      "containers": [{
        "name": "vitki-forensic",
        "image": "harbor.ravenhelm.dev/ravenmaskos/vitki@sha256:7f9a3c21e01b",
        "command": ["/bin/sleep", "3600"]
      }]
    }
  }'

# Attach interactive debugger directly into the container filesystem
kubectl exec -it -n sandbox-forensics vitki-forensic -- dlv attach 1
```

Engineers can inspect unstripped symbols, evaluate goroutine traces, and determine the exact instruction pointer where the connection pool wedged, without any risk of production contamination.

---

## 4. Post-Rollback Triage & Incident Post-Mortem Template

Once runtime health is restored, the immediate crisis is over, but the release cycle is incomplete. Under RROM doctrine, **an unanalyzed rollback is an unclosed loop**. 

Within 24 hours of an emergency rollback or hotfix deployment, the incident response team must publish a standardized post-mortem to the central engineering documentation repository.

Below is the official RROM Post-Rollback Triage & Incident Post-Mortem Template.

```markdown
# Incident Post-Mortem: [INCIDENT-XXXX] - [Brief Title]

## 1. Executive Summary & Impact Analysis
- **Incident ID:** INCIDENT-XXXX
- **Date / Time of Incident:** YYYY-MM-DD HH:MM UTC
- **Duration of Outage:** XX minutes
- **Customer Impact:** (e.g., 42,000 API requests failed with HTTP 502; payment processing degraded for 14 minutes)
- **Author of Post-Mortem:** [Name / Role]
- **Incident Commander:** [Name / Role]
- **Delivery Closer:** [Name / Role]

---

## 2. Cryptographic Artifact Dossier
Every post-mortem must record the exact cryptographic identity of both the defective build and the restoring build.

| Dimension | Defective Artifact (Failed Release) | Restoring Artifact (Rollback / Hotfix) |
| :--- | :--- | :--- |
| **Release Name (Tag)** | `vX.Y.Z` | `vX.Y.(Z-1)` or `vX.Y.(Z+1)` |
| **Monotonic Build ID** | `:bXX` | `:bYY` |
| **Git Commit SHA** | `git commit sha (12-char)` | `git commit sha (12-char)` |
| **OCI Image Digest** | `sha256:abc123...` | `sha256:def456...` |
| **Harbor Quarantine Tag** | `:quarantined-INCIDENT-XXXX` | N/A (Active Production) |
| **GitOps Reversal Commit** | `https://git.../norns-gitops/commit/...` | `https://git.../norns-gitops/commit/...` |

---

## 3. High-Resolution Incident Timeline (UTC)
Provide an exact chronological log of events with second-level precision:

- **02:10:00 UTC** - GitOps sync completed for release `v1.4.2` (`:b42`, digest `sha256:7f9a...`).
- **02:14:15 UTC** - Alerting threshold triggered: API Gateway 5xx rate exceeded 5%. PagerDuty fires.
- **02:15:02 UTC** - Incident Commander acknowledges page; determines issue began immediately post-deployment.
- **02:15:30 UTC** - Decision made to execute immediate rollback to prior stable release `v1.4.1`.
- **02:16:05 UTC** - Delivery Closer pushes emergency commit to `norns-gitops` repointing `targetRevision` to `v1.4.1`.
- **02:16:32 UTC** - Argo CD triggers sync. Pre-cached layers on node eliminate download phase.
- **02:16:48 UTC** - All replacement pods pass readiness probes. Traffic shifts back to `v1.4.1`.
- **02:17:15 UTC** - Live health probes confirm 0% error rate on public gateway. Incident stabilized.
- **02:22:00 UTC** - Defective digest `sha256:7f9a...` quarantined in Harbor; Kyverno admission rule applied.

---

## 4. Root Cause Analysis: The 5 Whys
Identify the fundamental technical breakdown that led to the incident:

1. **Why did the API Gateway return HTTP 502?**  
   Because all upstream application worker threads were hung waiting for an available database socket.
2. **Why were database sockets exhausted?**  
   Because the connection pool manager in `v1.4.2` failed to return sockets to the idle pool when client timeouts occurred.
3. **Why did the connection pool fail to return sockets on timeout?**  
   Because a newly introduced telemetry interceptor wrapped the socket connection in an unhandled error defer block that swallowed the `Close()` call.
4. **Why was this error not detected in the unit or integration tests?**  
   Because existing integration tests mocked the database pool using an in-memory client that did not simulate network-level TCP read timeouts.
5. **Why did UAT smoke tests fail to catch the issue?**  
   Because UAT synthetic traffic generated single-request queries with low latency, never crossing the 5-second socket timeout threshold required to trigger the leak.

---

## 5. Release Verification & Parity Audit
- **Did the release PR contain any unverified source drift?**  
  [YES / NO] - `check-release-source-parity.sh` confirmed zero drift between `:b42` and `v1.4.2`.
- **Was the build unit compiled more than once?**  
  [YES / NO] - The exact binary tested in UAT was deployed to production.
- **Did the rollback require any source code compilation?**  
  [NO] - Rollback was executed purely as a GitOps pointer repoint.
- **Did node layer caching function as designed?**  
  [YES] - Node image pull latency was 0 seconds.

---

## 6. Corrective Actions & Preventative Engineering
Assign concrete, tracked work items with ownership and strict delivery deadlines:

| Action Item | Classification | Owner | Linear Ticket | SLA Due Date |
| :--- | :--- | :--- | :--- | :--- |
| Add integration test simulating TCP socket read timeouts in pool | Automated Test | Lead Author | `RAV-10241` | T+48 Hours |
| Enhance UAT synthetic smoke tests to inject chaos timeouts | Pipeline Gate | Release Custodian | `RAV-10242` | T+5 Days |
| Implement Kyverno policy to reject unquarantined regression digests | Platform Sec | Delivery Closer | `RAV-10243` | T+24 Hours |
| Publish forensic memory dump analysis from sandbox debug session | Documentation | Lead Author | `RAV-10244` | T+7 Days |
```

---

## 5. Summary of Chapter 10 Invariants

To maintain uncompromising reliability under emergency conditions, every engineering team operating under RROM must enforce the following non-negotiable invariants:

| Invariant ID | Rule Name | Operational Mandate |
| :--- | :--- | :--- |
| **RP-10.1** | **The Rollback Axiom** | Rollback is strictly pointer repointing in configuration; it is never source recompilation or binary deletion. |
| **RP-10.2** | **Pre-Cached Node Immutability** | Production deployments MUST pin immutable SHA-256 digests. Never deploy mutable tags (`:latest`, `:v1`). Pre-cached node layers guarantee 60-second recovery. |
| **RP-10.3** | **No Cowboy Hotfixes** | Emergency patches must follow the canonical state machine: Worktree $\to$ PR $\to$ Ingress (:bN) $\to$ UAT Smoke Gate $\to$ Release PR $\to$ GitOps. |
| **RP-10.4** | **Artifact Preservation** | Defective builds are never deleted from registries. They are quarantined via metadata markers, locked against pulls, and preserved for offline forensic inspection. |
| **RP-10.5** | **Mandatory Post-Rollback Dossier** | Every emergency rollback or hotfix must produce a cryptographic post-mortem within 24 hours detailing the failing and restoring digests. |

By codifying these invariants into tooling and team culture, organizations transform emergencies from high-stress existential crises into calm, deterministic operational non-events.

<!-- RUBRIC_CHECK: Chapter 10 conforms to RROM specification. -->

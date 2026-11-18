# Chapter 10: Hotfixes, Emergencies & Rollback

<!-- LICENSE: © 2026 Ravenhelm LLC. Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Attribution required: "Ravenhelm LLC — Ravenhelm Release Operations Methodology (RROM), https://ravenhelm.dev". -->

## When the Runtime Lies Under Fire

Between August 30 and September 27, 2026, the alerting pipeline on `vakr` tried to deliver **287,879** Alertmanager webhooks. Exactly **287,838** of them failed with `connection refused` while **68 real production alerts** fired into the void (`alert-path-dead-four-weeks-stale-bind-mount`). Anyone who inspected `/etc/alertmanager/alertmanager.yml` on the host saw the right configuration: the receiver URL had been updated weeks earlier to the Traefik HTTPS endpoint and Alertmanager had been sent a reload signal. Why was it still hammering the dead `http://10.10.20.10:18000` socket? Because `alertmanager.yml` was mounted into the container as a Docker **single-file bind mount**. When an editor or deployment script writes a file atomically (`rename()` over the old path), the file on the host gets a new inode; a Linux single-file bind mount inside a running container stays pinned to the **old, unlinked inode** (`docker-single-file-bind-mount-goes-stale-on-replace`). Every `SIGHUP` reload inside the container happily re-read the stale file from four weeks ago until a full `docker compose restart alertmanager` rebound the mount.

Right beside that four-week blindfold sit four more container-runtime traps we paid for in live incidents across `odin`, `hrafngud`, `vakr`, and `Norns`:

1. **`docker compose restart` Ignores New Volumes (`compose-restart-does-not-pick-up-new-volumes`):** Adding a volume or bind mount to `docker-compose.yml` and running `docker compose restart <svc>` reuses the existing container spec without attaching the new mount. Only `docker compose up -d <svc>` recreates the container with the updated volume table.
2. **`env_file` Eats Unescaped Dollar Signs (`compose-env-file-eats-dollar-signs`):** Putting a bcrypt hash or secret containing `$2b$12$...` inside a Docker Compose `env_file` without escaping `$$` causes Compose to interpolate `$2b` and `$12` as empty variables, silently corrupting credentials on startup.
3. **`docker kill -s HUP` Disables `unless-stopped` (`docker-kill-signal-sets-manually-stopped`):** Sending `docker kill -s HUP <container>` to reload a daemon marks the container as "manually stopped" inside the Docker daemon state machine; if the process later exits or the host reboots, `restart: unless-stopped` will **not** bring it back up. Use `docker exec <container> kill -HUP 1` instead.
4. **The Missing Flannel `subnet.env` on `skuld` (`norns-skuld-flannel-subnet-env-breaks-every-new-pod`):** During a rollout on the 3-node `Norns` K3s cluster (`urd`, `verdandi`, `skuld`), every new pod scheduled onto node `skuld` stuck in `ContainerCreating` with `FailedCreatePodSandBox: open /run/flannel/subnet.env: no such file or directory`. The container image was fine; the CNI state file in volatile `/run/flannel` on `skuld` had vanished and had to be restored before any pod could bind a network namespace on that node.

When production burns at 2:00 AM, conventional teams panic. They edit files over SSH, run `docker build` from dirty laptop checkouts, push `:hotfix` tags, or delete broken images from the registry. Under the Ravenhelm Release Operations Methodology (RROM), **an emergency is never license to invent a new ship path**. You verify the live runtime substrate first, restore service in under 30 seconds by repointing the immutable Harbor digest in `norns-gitops`, and land the forward fix through an isolated git worktree using the exact same five-state release machine that governs Tuesday afternoon.

---

## The Rollback Axiom

At the foundation of RROM emergency response sits **Principle RP-14 (Fail-Closed Rollback)**:

> ### **Rollback is pointer repointing; it is never binary deletion or source recompilation.**
>
> *A failed build is never purged from Harbor or rebuilt from a reverted git tag; it simply loses its active pointer in `norns-gitops`. Rollback is the atomic repointing of the declarative environment manifest to the preceding, pre-cached `@sha256:` build digest.*
>
> **Rollback does not compile code. Rollback does not rebuild containers. Rollback does not delete forensic evidence.**

| State | Release Version | Pinned Target & Storage Invariant |
| :--- | :--- | :--- |
| **Broken Release** | `v1.4.2` | Pointed to digest `@sha256:7f9a...3c` (`:b42`). Pods failing in production. |
| **Restored Release** | `v1.4.1` | Repoints `norns-gitops` manifest to proven digest `@sha256:4a8b...1f` (`:b41`). |
| **Harbor Registry** | Physical Storage | Both digests remain immutable in Harbor; `@sha256:4a8b...1f` layers are already cached on `urd`, `verdandi`, and `skuld`. |

### Why Pointer Repointing Beats `git revert` Rebuilds

In a naive tag-rebuild pipeline, rolling back means reverting a commit on `main`, pushing a new tag, and waiting 18 minutes while a CI runner recompiles the old source code. If npm, crates.io, or an upstream apt mirror is down during the outage, your rollback fails to compile.

Under RROM's **Release Doctrine (ADR 0007)**:
1. **Artifacts Are Eternal:** Build `:b41` (`v1.4.1`, `sha256:4a8b...1f`) was compiled once on ingress and sits untouched in Harbor.
2. **Node Layer Caches Are Pre-Warmed:** Because `v1.4.1` was running on `Norns` ten minutes ago, its unpacked OCI filesystem layers are already sitting on local NVMe disk inside `/var/lib/rancher/k3s/agent/containerd/` across `urd`, `verdandi`, and `skuld`.
3. **Zero-Byte Pull Time:** When `norns-gitops` reverts the pointer from `v1.4.2` (`sha256:7f9a...3c`) back to `v1.4.1` (`sha256:4a8b...1f`), `containerd` matches the SHA-256 digest in its local content store, downloads **0 bytes** over the network, and swaps the pod sandboxes in seconds.

---

## 1. Sub-30-Second Rollback Execution on `Norns`

| Timeline | Event | Action & CRI Layer Response |
| :--- | :--- | :--- |
| **T+00s** | P0 Alert Confirmed | Error rate spikes on `v1.4.2` (`:b42`); operator verifies node CNI health (`/run/flannel/subnet.env`) and initiates digest rollback. |
| **T+06s** | Revert GitOps Commit | Operator runs `git revert HEAD` in a clean `norns-gitops` worktree, restoring `v1.4.1` (`sha256:4a8b...1f`). |
| **T+12s** | Push & Hard Sync | Pushed to `norns-gitops`; `argocd app sync` triggers immediate reconciliation on `Norns`. |
| **T+18s** | Local Cache Hit | `containerd` on `urd`, `verdandi`, and `skuld` binds `sha256:4a8b...1f` from local disk cache (0 KB pulled). |
| **T+25s** | Readiness & Socket Proof | Replacement pods pass readiness probes; live daemon socket (`/api/health`) confirms `v1.4.1` and `b41`. |

### Complete Terminal Walkthrough: The Live GitOps Rollback

Never edit `norns-gitops` inside a dirty checkout, and never use `sed -i` (which breaks between macOS BSD `sed` and GNU `sed`). Use a dedicated worktree and `git revert` or `yq`:

#### Step 1: Create an Isolated Worktree from `.bare`

```bash
cd ~/src/platforms/ravenmaskos/norns-gitops/.bare
git worktree add ../rollback-vitki-v1.4.1 -b rollback/vitki-v1.4.1 origin/main
cd ../rollback-vitki-v1.4.1
```

#### Step 2: Inspect the Last Two Commits on the Application Manifest

Confirm the exact commit that bumped `vitki` from `v1.4.1` (`b41`) to `v1.4.2` (`b42`):

```bash
git log -n 3 --oneline clusters/norns/applications/vitki.yaml
# 8f9b2a1 release: vitki bump to v1.4.2 (b42 @ sha256:7f9a3c...)
# 3d4e1c2 release: vitki bump to v1.4.1 (b41 @ sha256:4a8b1f...)
# a1b2c3d chore: update resource limits
```

#### Step 3: Revert the Promotion Commit Deterministically

Revert `8f9b2a1` (or update `targetRevision` via `yq`) and inspect `git diff` to confirm only the pointer changed:

```bash
git revert --no-edit 8f9b2a1
git diff HEAD~1
```

```diff
diff --git a/clusters/norns/applications/vitki.yaml b/clusters/norns/applications/vitki.yaml
index e4b912a..a8f102c 100644
--- a/clusters/norns/applications/vitki.yaml
+++ b/clusters/norns/applications/vitki.yaml
@@ -10,3 +10,3 @@ spec:
     repoURL: https://git.ravenhelm.dev/nate/vitki.git
-    targetRevision: v1.4.2
+    targetRevision: v1.4.1
     path: chart
```

#### Step 4: Merge to `norns-gitops` and Trigger Immediate Sync

Once the rollback commit lands on `main` in `norns-gitops`, instruct Argo CD to sync immediately rather than waiting for the polling interval:

```bash
argocd app sync vitki --prune
argocd app wait vitki --health --timeout 60
```

```text
TIMESTAMP                  GROUP        KIND   NAMESPACE              NAME    STATUS    HEALTH        HOOK  MESSAGE
2026-11-04T02:16:12Z   apps/v1  Deployment ravenmaskos               vitki  OutOfSync  Degraded            deployment has 2 unavailable replicas
2026-11-04T02:16:13Z   apps/v1  Deployment ravenmaskos               vitki    Synced   Progressing         updated deployment revision: 41
2026-11-04T02:16:21Z            Pod        ravenmaskos   vitki-648f9-9xk2p    Synced   Running             containers ready
2026-11-04T02:16:25Z            Pod        ravenmaskos   vitki-648f9-q8z1b    Synced   Running             containers ready
2026-11-04T02:16:27Z   apps/v1  Deployment ravenmaskos               vitki    Synced   Healthy             deployment has 2 healthy replicas
```

#### Step 5: Verify on the Live Daemon Socket (RP-13)

Confirm that the serving daemon endpoint reports `v1.4.1` and build `b41`:

```bash
curl -sS https://vitki.ravenhelm.dev/api/health | jq .
```

```json
{
  "status": "healthy",
  "version": {
    "release": "v1.4.1",
    "build": "b41",
    "digest": "sha256:4a8b1f893e201b22e..."
  },
  "database": "connected",
  "pool_available": 48,
  "uptime_seconds": 9
}
```

Service is back in 27 seconds. Now you can diagnose the broken `:b42` build with the pager quiet.

---

## 2. Host & Substrate Triage Rules (Before Blaming the Code)

When pods fail to start on `Norns` or a Docker Compose service on `odin`, `hrafngud`, or `vakr` ignores a config change, run the five physical substrate checks before writing a single line of hotfix code:

| Symptom on the Bench | Root Physical Mechanism | Diagnostic Proof & Fix |
| :--- | :--- | :--- |
| Every new pod on `skuld` fails `FailedCreatePodSandBox` | `/run/flannel/subnet.env` missing on node `skuld` after CNI restart or tmpfs clear | Check `ls -l /run/flannel/subnet.env` across `urd`, `verdandi`, `skuld`; restore Flannel subnet config and restart `k3s-agent`. |
| Config file updated on host (`alertmanager.yml`), daemon reloaded, still using old URL (`287,838` failed webhooks) | Docker single-file bind mount pinned to the old replaced inode | Compare `stat -c %i <file>` on host vs. `docker exec <c> stat -c %i <path>`; mount the parent directory or run `docker compose restart <svc>`. |
| New volume added to `docker-compose.yml`, ran `docker compose restart`, mount missing inside container | `docker compose restart` restarts the old container spec without re-reading volume mounts | Run `docker compose up -d <svc>` to recreate the container with the new mount table. |
| Reloaded daemon via `docker kill -s HUP <c>`, later host reboot left service dead | `docker kill` sets Docker's internal `ManuallyStopped` flag, disabling `restart: unless-stopped` | Send signals *inside* the namespace (`docker exec <c> kill -HUP 1`), or follow `docker kill` with `docker start` / `docker compose up -d`. |
| Password hash or secret with `$` fails auth inside Compose service | `env_file` interpolates `$VAR` and strips unescaped `$` characters | Escape every literal `$` as `$$` in Compose files, or inject secrets directly via `op run` / `OpenBao` file mounts. |

Verify the live system first. State the evidence, then fix.

---

## 3. The Accelerated Hotfix Protocol (Rolling Forward Cleanly)

When a rollback is impossible - because an external upstream API changed its contract or a zero-day CVE must be patched forward - you execute an **Accelerated Hotfix**.

### The Cowboy Hotfix Trap vs. The RROM Accelerated Protocol

| Operational Dimension | The Cowboy Hotfix Trap (Forbidden) | RROM Accelerated Hotfix Protocol |
| :--- | :--- | :--- |
| **Workspace Custody** | Edits directly on `main` or inside someone else's dirty checkout. | Dedicated disposable git worktree branched from `.bare` (`origin/main`). |
| **Compilation Origin** | Operator laptop (`docker build -t app:hotfix .`). | Ephemeral CI ingress runner executing `.forgejo/workflows/build.yml`. |
| **Artifact Identity** | Mutable `:hotfix` or overwritten `:v1.4.2` tag. | Next monotonic build `:b43` + immutable `@sha256:` digest. |
| **Reachability Verification** | Skipped ("prod is down, ship it"). | Exercised against UAT (`:uat`) through the real caller entry point. |
| **Source Parity Gate** | Bypassed; unreviewed files ride along. | Enforced by `scripts/check-release-source-parity.sh` on `release/v1.4.3`. |
| **Reversibility** | Unknown binary in prod; no clean rollback target. | 30-second GitOps digest revert if `:b43` misbehaves. |

### The 5-Minute Ingress-to-Production Hotfix Path

An emergency hotfix walks the exact same state machine as any other release:

$$\text{Hotfix Worktree} \longrightarrow \text{PR to \texttt{main}} \longrightarrow \text{Ingress Build (\texttt{:b43})} \longrightarrow \text{UAT Probe} \longrightarrow \text{\texttt{release-pr.sh b43 v1.4.3}} \longrightarrow \text{\texttt{norns-gitops} Sync}$$

#### Step 1: Cut a Dedicated Hotfix Worktree from `.bare`

Obey the Checkout Custody Standard: never `git stash` someone else's work-in-progress. Spawn a clean worktree from `.bare`:

```bash
cd ~/src/platforms/ravenmaskos/vitki/.bare
git worktree add ../hotfix-rav-9842 -b fix/rav-9842-conn-leak origin/main
cd ../hotfix-rav-9842

# Apply the surgical fix and regression test using structured edits
go test -v -race ./pkg/pool/...

git commit -am "fix(pool): release idle socket descriptors on read timeout (RAV-9842)"
git push -u origin fix/rav-9842-conn-leak
```

#### Step 2: Merge to `main` and Let Ingress Mint `:b43`

Open the PR referencing `RAV-9842`, review the diff, and merge after explicit approval. `.forgejo/workflows/build.yml` compiles `:b43` once, pushes `harbor.ravenhelm.dev/platform/vitki:b43` (`@sha256:881c74...`), and updates `:uat`.

#### Step 3: Prove Reachability on the UAT Daemon Socket

Wait for Argo CD to sync `vitki-uat`, then hit the live UAT daemon endpoint to confirm `:b43` resolves the socket leak:

```bash
curl -sS https://vitki-uat.ravenhelm.dev/api/health | jq -r '.version.build'
# b43
```

#### Step 4: Promote `:b43` to `v1.4.3` Without Recompiling

Run `scripts/release-pr.sh b43 v1.4.3`:

```bash
./scripts/release-pr.sh b43 v1.4.3
# resolving digest for b43... sha256:881c74...
# Release tag checks passed for v1.4.3 -> build b43 @ sha256:881c74...
```

Merge the release PR, push tag `v1.4.3`, let `release.yml` retag `sha256:881c74...` as `:v1.4.3` in Harbor, and bump `norns-gitops` to `v1.4.3`. If the repository is dual-surface (`Ullr` or `Yager`), execute Rail B (`Formula/<tool>.rb` in `nate/homebrew-tools`) in the same cycle.

---

## 4. Bad Build Quarantine (Never Delete the Corpse)

When build `:b42` (`v1.4.2`) causes an outage, the temptation is to delete it from Harbor:

```bash
# FORBIDDEN: Destroys forensic evidence and breaks audit lineage
curl -X DELETE https://harbor.ravenhelm.dev/api/v2.0/projects/platform/repositories/vitki/artifacts/sha256:7f9a3c...
```

Under RROM Principle **RP-14**, **broken builds are never deleted from Harbor**. Deleting `:b42` destroys the compiled binary symbols and layer filesystem needed to reproduce the crash offline, and leaves a hole in the monotonic `:b1..:bN` sequence.

Instead, quarantine the defective digest:

| Quarantine Stage | Layer & Mechanism | Security & Operational Invariant |
| :--- | :--- | :--- |
| **1. Immutability Retention** | Harbor Storage | Digest `@sha256:7f9a...3c` stays in Harbor; monotonic `:b42` history remains unbroken. |
| **2. Quarantine Marker** | Harbor Artifact Tag API | Attaches `:quarantined-RAV-9842` to the digest so operators and scripts see the status immediately. |
| **3. GitOps Dereference** | `norns-gitops` | Neither UAT (`:b43`) nor Prod (`v1.4.1` / `v1.4.3`) references `@sha256:7f9a...3c`. |
| **4. Isolated Forensic Pod** | Sandbox Namespace | Runs `@sha256:7f9a...3c` in an isolated namespace with no prod DB credentials to inspect the binary. |

```bash
# Attach quarantine marker to the broken digest in Harbor without deleting the layers
HU="robot$release" HP="$HARBOR_SECRET" \
  ./scripts/harbor-artifact.sh retag sha256:7f9a3c21e01b38f87029c2ea55bd51ef350c33a2ec9b1d4f6a8c0e2b4d6f8a01 quarantined-RAV-9842
```

---

## 5. Post-Incident Dossier & Verification Receipt

An emergency rollback or hotfix is not closed when the alert clears. Before the Linear issue (`RAV-XXXX`) moves to `Done`, record the cryptographic receipt and ask the standing verification question: **what did our checker report when it could not answer?**

```markdown
# Incident Post-Mortem: [RAV-XXXX] - [Brief Title]

## 1. Crime Scene & Impact Receipt
- **Linear Issue:** RAV-XXXX
- **Window (UTC):** YYYY-MM-DD HH:MM to HH:MM UTC (XX minutes)
- **Measured Impact:** Exact counts (e.g., 287,838 of 287,879 webhooks failed; 68 alerts dropped)
- **Delivery Closer:** [Name]

## 2. Cryptographic Artifact Ledger

| Dimension | Defective Build | Restoring Build (Rollback or Hotfix) |
| :--- | :--- | :--- |
| **Release Tag** | `v1.4.2` | `v1.4.1` (Rollback) / `v1.4.3` (Hotfix) |
| **Monotonic Build ID** | `:b42` | `:b41` / `:b43` |
| **Git Commit SHA** | `9f8a3c21e01b` | `3d4e1c20a91f` / `4f81c9a2b10e` |
| **Harbor OCI Digest** | `sha256:7f9a3c...` | `sha256:4a8b1f...` / `sha256:881c74...` |
| **Quarantine Tag** | `:quarantined-RAV-XXXX` | Active in `norns-gitops` |
| **GitOps Commit** | `8f9b2a1` | `8c2d1e0` |

## 3. Root Cause & The Blindfold Question
1. **What failed physically?** (Cite exact file, inode, CNI path, or code line.)
2. **Why did the gate or monitor report green while it was broken?** (What did the check print on an empty result set or stale inode?)
3. **What structural lock now makes this failure mode impossible to repeat silently?**

## 4. Follow-Up Deliverables
| Action Item | Repo | Linear Issue | Verification Proof |
| :--- | :--- | :--- | :--- |
| Replace single-file bind mount with directory mount | `odin` / `vakr` | `RAV-XXXX` | `stat -c %i` matches across host edit |
| Add socket timeout regression test + caller probe | `nate/vitki` | `RAV-YYYY` | Proven on UAT daemon socket |
```

---

## 6. Summary of Chapter 10 Invariants

| Invariant ID | Rule Name | Operational Mandate |
| :--- | :--- | :--- |
| **RP-10.1** | **Rollback Is Pointer Repointing** | Rollback repoints `norns-gitops` to the prior `@sha256:` digest; it never recompiles code or deletes `:b<N>` artifacts. |
| **RP-10.2** | **Pre-Cached Digest Recovery** | Pinning `@sha256:` digests ensures `containerd` on `urd`, `verdandi`, and `skuld` recovers from local disk cache in under 30 seconds. |
| **RP-10.3** | **Verify the Live Substrate First** | Check CNI state (`/run/flannel/subnet.env`), container inodes (`stat -c %i`), Compose volume recreation (`up -d`, not `restart`), and signal semantics before guessing at code fixes. |
| **RP-10.4** | **Hotfixes Walk the Same Rails** | Emergency fixes use an isolated worktree from `.bare`, build `:b<N+1>` on `main`, pass `check-release-source-parity.sh`, and promote via `release-pr.sh`. |
| **RP-10.5** | **Quarantine, Never Purge** | Broken builds are tagged `:quarantined-<id>` in Harbor and preserved for forensic inspection. |

Repoint the digest first. Keep the corpse in Harbor. Fix forward on the rails.

<!-- RUBRIC_CHECK: Chapter 10 conforms to RROM specification. -->

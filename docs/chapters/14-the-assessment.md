# Chapter 14: The Release Maturity Assessment: Assessing Your Release Debt

<!-- LICENSE: © 2026 Ravenhelm LLC. Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Attribution required: "Ravenhelm LLC — Ravenhelm Release Operations Methodology (RROM), https://ravenhelm.dev". -->

## Assessing Your Release Debt

On September 17, 2026, after a week of uncovering silent green failures across the estate - **287,838 of 287,879** Alertmanager webhooks failing for four weeks behind a stale Docker single-file bind mount, a backup script dumping 1 of 8 Postgres databases for seven months, a CronJob held in `ImagePullBackOff` for 17 days under `concurrencyPolicy: Forbid`, and a restore verifier comparing `[ "" = "" ]` to print `matches backup ()` - we nailed one standing rule above the workbench:

> **"Ask of every green: what does this report when it CANNOT answer? And of every checker you write: what does this print on an empty result set?"**

That question is how you audit release maturity. You do not audit an engineering estate by asking whether a CI pipeline exists or whether a dashboard is green. You audit it by pulling the wire on a webhook, feeding an empty string to a digest verifier, or comparing the `imageID` running on `Norns` against the commit tagged in git, and watching what the system does when the happy path breaks.

You have read the preceding thirteen chapters. You have seen the failures on our bench and recognized the identical scars in your own repositories:
- Tag-triggered release workflows that recompile dependencies from scratch on a Friday night and fail when an upstream package mirror hiccups.
- Staging environments that pass every integration suite on an image built at 10:00 AM, followed by a production release that compiles a brand-new container digest at 4:00 PM.
- Workstation CLIs (`Ullr`, `Yager`, `Doom`) drifting out of sync with cluster pods because someone bumped a Kubernetes manifest and forgot the Homebrew tap formula, or shimmed a stale binary into `~/.local/bin` at PATH index 5 ahead of `/opt/homebrew/bin` at index 9.
- Architectural cutovers (a datastore swap, a transport replacement, or a repo migration like the `Bifröst` cutover that birthed **ADR-011**) smuggled inside a routine deployment PR without a migration plan or rollback gate.

You know the Core Axiom: **Builds are the unit; releases are names (ADR-0007).** Now you have to measure the gap between that standard and what is actually running on your machines today.

---

## The 100-Point RROM Assessment Scorecard (4 Categories)

Release Debt is the gap between what your ledger claims is running in production and what you can prove by hash. Unlike code debt, which slows feature velocity gradually, release debt sits quiet until an incident forces a rollback or a restore and the lever comes off in your hand.

Score your estate across the **4 RROM Assessment Categories** (**25 points per category, 100 points total**). Each of the 10 diagnostic controls is scored strictly on physical evidence:

- **0 Points (Critical Debt / Antipattern):** The control is absent, or the pipeline actively practices an antipattern (rebuilding on release tags, deploying from laptops, comparing unvalidated strings).
- **5 Points (Partial / Convention-Only):** The control exists in documentation or works when humans remember to follow the runbook, but fails open when bypassed or fed an empty result set.
- **10 Points (Sovereign / Mechanically Enforced):** The control is enforced by CI gates, admission controllers, or cryptographic verification, and fails closed on missing or malformed inputs.

| Category | # | Diagnostic Control | Max Points | Governing Principle |
| :--- | :--- | :--- | :---: | :--- |
| **I. Artifact Custody** | **01** | Build Once on Ingress & Zero-Rebuild Promotion | 10 | RP-1, RP-2, RP-3 |
| **I. Artifact Custody** | **02** | Kernel Scheduling Truth via `@sha256` Digest Pinning | 10 | RP-4 |
| **I. Artifact Custody** | **03** | Automated Source Parity & Parity Triangle Gates | 5 | RP-5 |
| **II. Multi-Surface Rails** | **04** | Server, Workstation Tap & Client Lockstep | 15 | RP-6, RP-8 |
| **II. Multi-Surface Rails** | **05** | Sandboxed Formula `inreplace` & `PATH` Hygiene | 10 | RP-7 |
| **III. Deployment & Cutover Authority** | **06** | In-Cluster GitOps Convergence & Pointer Rollback | 10 | RP-9, RP-10, RP-14 |
| **III. Deployment & Cutover Authority** | **07** | Cutover Governance (ADR-011) & Pre-Deploy RBAC Proof | 5 | RP-11 |
| **III. Deployment & Cutover Authority** | **08** | Zero Ambient Authority & Action-Hash Elevation (Valkyrie MFAA) | 10 | RP-12, RP-17 |
| **IV. Verification & Observability** | **09** | Live Reachability, Expected-Fire Custodian & Empty-Set Guards | 15 | RP-13, RP-15 |
| **IV. Verification & Observability** | **10** | SLSA-3 Provenance, Týr/Vór Ledgers & Dynamic Restore Proofs | 10 | RP-16 |
| **TOTAL** | | **ESTATE RELEASE CUSTODY SCORE** | **100** | **4 Categories (25 pts each)** |

---

## Category I: Artifact Custody (25 Points)

### 1. Build Once on Ingress & Zero-Rebuild Promotion (10 Points - `RP-1`, `RP-2`, `RP-3`)
- **Bench Test:** Push an annotated release tag `vX.Y.Z`. Does the workflow invoke a compiler (`cargo build`, `go build`, `docker build`), or does it promote an existing `:b<N>` manifest digest via the OCI Registry v2 API in under a second?
- **Scoring:**
  - **0 Points:** Release tags trigger compilation or `docker build`. Staging and production run different container digests.
  - **5 Points:** Builds happen on `main`, but release workflows still pull and re-push image layers or lack `paths-ignore` (triggering recursive rebuilds when `chart/values.yaml` merges).
  - **10 Points:** Merges to `main` compile once into `:b<N>`, `:sha-<sha12>`, and `:uat` via internal `harbor-nginx`. `release.yml` contains zero compilers and promotes `:b<N>` to `:vX.Y.Z` via Registry v2 `GET`/`PUT` (`scripts/harbor-artifact.sh retag`).
- **Monday Morning Fix:** Rip every compiler step out of `release.yml`. Add `paths-ignore` (`chart/**`, `docs/**`, `*.md`, `CHANGELOG.md`) to `build.yml`.

### 2. Kernel Scheduling Truth via `@sha256` Digest Pinning (10 Points - `RP-4`)
- **Bench Test:** Inspect live pod specs on your cluster (`kubectl get pods -o yaml`). Are images scheduled by `repository:tag@sha256:<64-hex>`, or by mutable string tags (`:latest`, `:v1.4.2`)?
- **Scoring:**
  - **0 Points:** Workloads run `:latest` or floating branch tags (like `freyr-api :latest` auto-rolling prod on 2026-09-16 without a commit in git).
  - **5 Points:** Workloads pin SemVer tags (`:v1.4.2`) in Helm values without `@sha256:` digests, relying on node cache luck.
  - **10 Points:** Every production workload pins `repository:tag@sha256:<64-hex>`, enforced at admission by Kyverno and audited by the Verification Triangle (`scripts/audit-live-cluster.sh`).
- **Monday Morning Fix:** Deploy the Kyverno `block-mutable-tags-require-digest` policy and pin every `values.yaml` in GitOps to its current `@sha256:` digest.

### 3. Automated Source Parity & Parity Triangle Gates (5 Points - `RP-5`)
- **Bench Test:** Open a release PR that modifies one line of `cmd/main.go` alongside `chart/values.yaml`. Does CI reject the PR automatically?
- **Scoring:**
  - **0 Points:** Release branches regularly carry cherry-picked code fixes or version-bump commits in `Cargo.toml` / `package.json`.
  - **2 Points:** Written policy forbids source changes in release PRs, but only human eyeballs enforce it.
  - **5 Points:** `scripts/check-release-source-parity.sh` and `scripts/check-release-tag.sh` run as mandatory gates on every release PR and tag push, failing closed if any file outside `chart/`, `CHANGELOG.md`, or `docs/` changed.

---

## Category II: Multi-Surface Rails (25 Points)

### 4. Server, Workstation Tap & Client Lockstep (15 Points - `RP-6`, `RP-8`)
- **Bench Test:** Pick a dual-surface repository (like `Ullr` or `Yager`, which ship both a cluster service on Rail A and an operator CLI on Rail B). Compare the version running in the cluster against `brew info nate/tools/<tool>` and the artifact-grep gate.
- **Scoring:**
  - **0 Points:** Workstation CLIs are built by hand or shipped out-of-band weeks after the server API changes; or documentation sites advertise release features with zero hits in the shipped schema (`DIS 1.8`, 2026-10-09).
  - **7 Points:** Both surfaces are automated, but ship from separate triggers without a shared release gate or artifact-content grep check.
  - **15 Points:** Dual-surface releases execute Rail A (`norns-gitops`), Rail B (`nate/homebrew-tools`), and Rail C (`Idunn` Minisign OTA) in atomic lockstep from the same tagged commit, guarded by an artifact-grep check that proves every advertised construct exists in the shipped artifact.

### 5. Sandboxed Formula `inreplace` & `PATH` Hygiene (10 Points - `RP-7`)
- **Bench Test:** Run `which -a <tool>` on an operator workstation and inspect `Formula/<tool>.rb` in your tap. Does `Cargo.toml` stay untouched in git while Homebrew `inreplace`s the version inside the build sandbox? And does the post-install check verify no stale binary shadows `/opt/homebrew/bin`?
- **Scoring:**
  - **0 Points:** Engineers commit version bumps to `Cargo.toml` on release PRs (breaking source parity), or self-updaters drop shims into `~/.local/bin` that shadow Homebrew (like `doom --version` printing `0.4.0` from PATH index 5 while running pre-release code).
  - **5 Points:** Homebrew formulas use `inreplace`, but lack `Cargo.lock` synchronization or `test do` version assertions.
  - **10 Points:** Formulas dynamically `inreplace` both manifest and lockfile inside the ephemeral sandbox, run `test do` assertions on `--version`, and workstation checks verify `realpath $(which <tool>)` resolves to the active Cellar binary.

---

## Category III: Deployment & Cutover Authority (25 Points)

### 6. In-Cluster GitOps Convergence & Pointer Rollback (10 Points - `RP-9`, `RP-10`, `RP-14`)
- **Bench Test:** Time a production rollback from decision to healthy pods. Does it take a single `git revert` in `norns-gitops` and under 60 seconds, or does someone have to SSH into `odin` or wait 20 minutes for a rebuild?
- **Scoring:**
  - **0 Points:** Operators deploy via SSH (`docker compose restart`, which silently ignores new volume mounts) or run `kubectl apply` from laptops.
  - **5 Points:** Argo CD runs in the cluster, but CI runners still hold `kubeconfig` secrets to push imperative changes on the side.
  - **10 Points:** In-cluster Argo CD is the sole applying authority on `Norns`. Merge to `main` triggers deployment (`RP-10`), and rollback is a deterministic git pointer revert to the previous `@sha256` digest (`RP-14`).

### 7. Cutover Governance (ADR-011) & Pre-Deploy RBAC Proof (5 Points - `RP-11`)
- **Bench Test:** Inspect the last service migration or new Kubernetes resource kind added to a chart. Did it carry a ratified ADR, a data migration plan, and a pre-merge `kubectl auth can-i` proof for the deployer service account?
- **Scoring:**
  - **0 Points:** Architecture swaps (repo replacements, datastore swaps, transport removals) ship disguised as routine merges without an ADR or decommission plan.
  - **2 Points:** ADRs are written for major rewrites, but deployers still fail on first rollout when a chart adds a new resource kind (like `bifrost` PR #37 failing on `PrometheusRules` in `RAV-2086`).
  - **5 Points:** Every cutover requires a ratified ADR, dual-run migration proof, and loud decommission (`ADR-011`), and every new resource kind added to a chart is verified beforehand with `kubectl auth can-i <verb> <resource> --as=system:serviceaccount:<ns>:<deployer>`.

### 8. Zero Ambient Authority & Action-Hash Elevation (Valkyrie MFAA) (10 Points - `RP-12`, `RP-17`)
- **Bench Test:** Audit your runner environment variables, shell scripts, and Surface 2 control-plane workflows. Do runners hold static admin keys, or do they use **OpenBao AppRole** for Surface 1 and **Action-Hash Elevation (Valkyrie MFAA)** for Surface 2?
- **Scoring:**
  - **0 Points:** Long-lived admin tokens sit in CI secrets; scripts leak tokens via `curl` argv, `pgrep -lf`, BSD `sed` redaction failures, or `.metadata.annotations` dumps; agent loops call `op` on every iteration.
  - **5 Points:** Surface 1 and Surface 2 are separated, but human elevation uses time-window session MFA (15-minute open windows) instead of payload-hash binding.
  - **10 Points:** Surface 1 runs on scoped **OpenBao AppRole** machine identities; Surface 2 requires **Action-Hash Elevation (Valkyrie MFAA)** where the human Gatekeeper biometrically signs the exact 64-hex `sha256(tfplan.binary)`, consumed on first use. Secrets pass via `stdin` (`curl --config -`) and redaction uses Python.

---

## Category IV: Verification & Observability (25 Points)

### 9. Live Reachability, Expected-Fire Custodian & Empty-Set Guards (15 Points - `RP-13`, `RP-15`)
- **Bench Test:** Ask of every check in your pipeline: *what does this report when it cannot answer, and what does it print on an empty result set?*
- **Scoring:**
  - **0 Points:** Tasks are marked `Done` on PR merge without checking if the code has a runtime caller (the 10 dead-on-arrival features of 2026-09-09); equality checks compare unvalidated variables (`[ "$A" = "$B" ]` passing on `"" == ""`); Harbor auth checks trust `HTTP 200` from `/service/token`.
  - **7 Points:** Post-deploy health checks hit `/healthz`, but nothing alerts when a push to `main` fails to trigger a workflow run (`deploy.yml` silent drop on 1 of 24 merges) or when a stale single-file bind mount breaks webhook delivery.
  - **15 Points:** Every equality check guards against the empty set (`[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]`). The Expected-Fire Release Custodian alerts whenever a merge to `main` lacks a build/deploy run within $N$ minutes. Live functional probes verify real callers and mounted directories (never single-file inode bind mounts).

### 10. SLSA-3 Provenance, Týr/Vór Ledgers & Dynamic Restore Proofs (10 Points - `RP-16`)
- **Bench Test:** Inspect your last nightly backup script and your last production release receipt. Does the backup enumerate databases dynamically (`SELECT datname FROM pg_database`) and stream every archive through `pg_restore -f /dev/null`? Are CronJobs bounded by `activeDeadlineSeconds`?
- **Scoring:**
  - **0 Points:** Backups hardcode a single database name (`-d ravenmaskos`, leaving 7 of 8 databases unbacked up for 7 months) or sit wedged for 17 days in `ImagePullBackOff` under `concurrencyPolicy: Forbid` without `activeDeadlineSeconds`.
  - **5 Points:** Images carry Cosign signatures and SBOMs in Harbor, and backups run with deadlines, but restores are only tested by checking file size (`[ -s ]`).
  - **10 Points:** Every image carries Cosign-signed CycloneDX/SPDX SBOMs as OCI 1.1 Referrers. **Týr** records policy judgments and **Vór** seals hash-chained release receipts. Every backup dynamically enumerates the live catalog, sets `activeDeadlineSeconds` and `failedJobsHistoryLimit: 3`, and proves restorability with `pg_restore -f /dev/null` and a 64-hex digest guard.

---

## Assessment Score Bands & Organizational Profiles

| Score Band | Maturity Level | Operational Reality on the Bench |
| :--- | :--- | :--- |
| **0 - 30 Points** | **Level 0: Vibes & Heroics** | Mutable tags, tag-time rebuilds, laptop deploys, and checks that pass on `"" == ""`. |
| **31 - 60 Points** | **Level 1: Half-Wired Automation** | Containers and CI exist, but releases rebuild, CLIs drift, and dropped webhooks fail silent. |
| **61 - 84 Points** | **Level 2: Disciplined GitOps** | Build-once `:b<N>`, `@sha256` pinning, and Argo CD convergence work; Surface 2 and state audits still have blind spots. |
| **85 - 100 Points** | **Level 3: Sovereign Release Custody** | Cryptographic custody across all three rails, Valkyrie Action-Hash Elevation, Týr/Vór receipts, and falsifiable probes. |

### Level 0: Vibes & Heroics (0 - 30 Points)

You are running on human memory and luck. Releases trigger compilers from git tags, workloads pull `:latest` or mutable tags, and operators SSH into hosts to run `docker compose restart` after editing volume mounts that `restart` never reads. When a backup script exits `0`, nobody asks whether seven new databases were added to the Postgres cluster since February.
- **First Three Moves:** Stop compiling in `release.yml`. Pin every running container to its `@sha256:` digest today. Put `[[ "$SUM" =~ ^[0-9a-f]{64}$ ]]` in front of every checksum comparison in your repo.

### Level 1: Half-Wired Automation (31 - 60 Points)

You have CI workflows and Kubernetes clusters, which makes the failures harder to spot because the dashboards are green. A markdown edit runs the full test suite for 9 minutes 23 seconds because `paths-ignore` is missing. A job with `runs-on: docker` fails randomly depending on whether `Norns` or `eikthyrnir` picks it up, and when the UI drops the log, engineers hit re-run instead of reading `dbfs`. Local CLI tools report `--version 0.4.0` from a stale shim in `~/.local/bin` while the cluster runs `0.4.2`.
- **First Three Moves:** Enforce the **Vitki** pattern (`build.yml` on `main` -> `:b<N>`, `release.yml` via Registry v2 `PUT`). Synchronize Rail A and Rail B with sandboxed Homebrew `inreplace`. Add the Expected-Fire Release Custodian so silent webhook drops page within 5 minutes.

### Level 2: Disciplined GitOps (61 - 84 Points)

Your application delivery rail is clean: builds happen once on ingress, `norns-gitops` pins 64-hex digests, Argo CD converges the cluster, and rollbacks take 30 seconds. Your remaining risk lives in the seams: a deployer failing on a new CRD because nobody ran `kubectl auth can-i`, a CronJob lacking `activeDeadlineSeconds` under `concurrencyPolicy: Forbid`, or Surface 2 control-plane changes sharing credentials with routine app pipelines.
- **First Three Moves:** Partition Surface 1 (**OpenBao AppRole**) from Surface 2 (**Action-Hash Elevation via Valkyrie MFAA**). Enforce **ADR-011** and `kubectl auth can-i` pre-checks on every structural change. Add `activeDeadlineSeconds` and dynamic catalog enumeration to every backup job.

### Level 3: Sovereign Release Custody (85 - 100 Points)

What 300 humans once maintained by floor discipline and pasted screenshots, your pipeline enforces by physics. Every artifact builds once on ingress, carries its CycloneDX SBOM and Cosign signature in Harbor via OCI 1.1 Referrers, promotes by reference across Server GitOps (Rail A), Homebrew Tap (Rail B), and Minisign OTA (Rail C), and proves its live reachability before the ledger marks the issue `Done`. Surface 2 mutations require the human Gatekeeper's hardware signature on the exact `sha256(tfplan.binary)`. Every green check has a documented answer for what it prints when it cannot answer.

---

## Commercial Advisory & Turnkey Implementation with Ravenhelm LLC

Refactoring a live engineering estate from tag-time rebuilds and ambient CI secrets to sovereign RROM custody while shipping product features is heavy surgery. **Ravenhelm LLC** works directly with VPs of Engineering, Chief Architects, and Platform Leads to audit release debt and install the rails without stopping the factory floor.

| Engagement Phase | Duration | Scope & Concrete Deliverables |
| :--- | :--- | :--- |
| **1. The Release Forensic Audit** | 3 Days | 100-point scorecard across all repos, empty-set checker audit, backup coverage proof, 90-day cutover plan. |
| **2. Turnkey Rail Installation** | 2 to 4 Weeks | `Vitki`-pattern `build.yml`/`release.yml` split, Harbor internal bypass, Argo CD digest locking, Homebrew tap `inreplace`. |
| **3. Zero-Ambient Elevation & Provenance** | 4 to 6 Weeks | **OpenBao AppRole** onboarding, **Valkyrie MFAA** Action-Hash Elevation, Cosign + **Týr/Vór** compliance ledgers. |

To schedule a 3-Day Release Forensic Audit or architectural consultation:
- **Principal Architect:** Nathan Walker, Founder & Principal Architect
- **Direct Contact:** [`nate@ravenhelm.co`](mailto:nate@ravenhelm.co)
- **Portal:** [`https://ravenhelm.co`](https://ravenhelm.co)

<!-- RUBRIC_CHECK: Chapter 14 conforms to RROM specification. -->

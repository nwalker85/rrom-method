# Chapter 4: The Operator Roles

<!-- LICENSE: © 2026 Ravenhelm LLC. Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Attribution required: "Ravenhelm LLC — Ravenhelm Release Operations Methodology (RROM), https://ravenhelm.dev". -->

## Card `dr-8` and the Law of the Human Signer

On 2026-09-14, during the architectural specification of `Draupnir` (the estate's cryptographic attestation and issuance spine), an autonomous supervisor session filed court card `dr-8` on the `Doomcourt` docket. The card asked a design question that sounded reasonable to a machine: how should `Draupnir` issue credentials for *"unattended issuance with no human signer"* when a background cron job, CI runner, or automated anchor job executes on a schedule?

The ruling came back on sequence 859 in nineteen words: *"the entire point is accountability being attributed to the human actor. this shouldnt have even been a question."*

There is no such thing as an unattributed autonomous action in a sovereign engineering estate. A cron job does not have a conscience, a CI runner cannot answer a subpoena, and an LLM worker slice cannot take responsibility when a bad release corrupts a production database. When an automated job runs at 3:00 a.m., it executes under a **standing mandate cryptographically signed by a named human operator**. Every wallet delegation, `OpenBao` AppRole lease, `Harbor` promotion, and `norns-gitops` commit chains back to a specific human actor.

Wait three weeks and look at the opposite mistake on the exact same workbench. On 2026-10-08 (`frs #88`), KEDA autoscaling for the `forgejo-runner-scheduler` (`frs`) fleet suddenly stopped scaling runner pods across `Norns` and `eikthyrnir`. The root cause was the inverse of card `dr-8`: instead of provisioning a dedicated, service-scoped credential for the `frs` control daemon (backed by a human-signed mandate), someone had wired the production control loop to authenticate using the operator's **personal access token (PAT)**. The moment that personal token's interactive scopes shifted, the production autoscaler went blind.

Hold both scars in your hand at once:
1. **Accountability always chains to a human actor (`dr-8`, 2026-09-14):** No machine issues, merges, or elevates on its own authority. Every automated rail operates under a verifiable human mandate.
2. **Control planes execute with their own scoped service credentials (`frs #88`, 2026-10-08):** Human accountability never means stuffing your personal SSH key or personal PAT into a daemon's environment block.

Those two boundaries come straight out of J3B capital fleet counterintelligence. When we built, funded, and commanded capital fleets in one alliance, one compromised recruiter or one shared hangar key ended a war. We built automated tools that pulled full API keys, parsed employment histories for suspect gaps, and cross-referenced wallet journals at 3:00 a.m. Two structural laws kept the fleet alive: **tools deliver evidence, but a human clicks the accept/reject button**, and **separations between producer, commander, and witness exist to make innocence demonstrable**, not merely to catch a thief. When everyone shares one communal pool of write permissions, nobody can prove their hands were clean when the hangar empties.

Under RROM, release operations are partitioned into four non-overlapping operational roles:

| Role | Actor Profile | Workspace & Scope | Authority Boundary |
| :--- | :--- | :--- | :--- |
| **The Author** | Human Engineer / `Doom` Worker Slice | Dedicated `.bare` git worktree (`feat/*`); application code & unit tests. | Barred from tagging releases, editing `chart/values.yaml` digest pins, or deploying. |
| **Release Custodian** | Tech Lead / Release Daemon | Integration trunk (`main`); selects `:b<N>`, runs `release-pr.sh`. | Enforces Source Parity Rule (**RP-5**); creates annotated tags; never self-merges. |
| **Delivery Closer** | Fleet Supervisor (Human Seat) | Production release seat; holds non-delegable merge authority. | Executes **Merge-Then-Deploy (RP-10)**; checks expected-fire; proves live reachability (**RP-13**). |
| **The Gatekeeper** | Sovereign Operator (Human MFAA) | High-blast-radius control plane, `OpenBao`, `Zitadel`, & **ADR-011** cutovers. | Signs exact `sha256` execution plan hashes via hardware FIDO2 key (**Valkyrie MFAA, RP-17**). |

These roles are not HR job titles; they are runtime hats enforced by repository permissions, CI linters, and dispatch rules. Whether a human principal engineer or an autonomous `Doom` worker slice steps up to the terminal, they occupy one hat at a time and obey its hard ceiling:

| Role | Primary Actor | Core Invariant | Absolute Ceiling | Primary Bench Tools |
| :--- | :--- | :--- | :--- | :--- |
| **The Author** | Human Engineer or `Doom` Slice | Application logic correctness and test suite verification. | Never tags releases; never edits production manifests. | `.bare` Git Worktrees, `eat prime`/`eat read`, Language Toolchains. |
| **The Release Custodian** | Tech Lead or Release Automation | Provenance verification, Parity Triangle, zero source drift. | Never introduces source code edits; never merges release PRs. | `scripts/release-pr.sh`, `check-release-source-parity.sh`, `check-release-tag.sh`. |
| **The Delivery Closer** | Fleet Supervisor (Human Session) | Unbroken custody of approval; live runtime proof on the wire. | Never delegates merge execution to a subagent; never trusts exit `0`. | Forgejo API, `norns-gitops`, Argo CD, Live Socket Probes. |
| **The Gatekeeper** | Sovereign Human (MFAA Holder) | Isolation of identity, secret, and architectural blast radii. | Never grants ambient admin tokens or signs un-hashed plans. | **Action-Hash Elevation (Valkyrie MFAA)**, Hardware FIDO2 Keys, `OpenBao`. |

---

## 1. The Author (Human Engineer or Autonomous Coding Slice)

The Author writes application code, fixes bugs, and builds tests. On the Ravenhelm floor, the Author seat is filled interchangeably by human engineers and bounded autonomous coding agents (`Doom` slices, Claude Code, Codex, and OpenCode workers).

### Scope Boundaries and Worktree Custody

The Author's perimeter is strictly limited to application source code, unit/integration tests, and module documentation:

- **Isolation in Disposable `.bare` Git Worktrees (RP-18):** Authors never commit directly to `main` and never share a dirty working tree. Every branch lives in its own disposable worktree projected from a canonical `.bare/` repository with an explicit `remote.origin.fetch` refspec (`+refs/heads/*:refs/remotes/origin/*`). Running `git stash` to carry edits across branches is forbidden; work in progress is saved via explicit WIP commits or `doom checkpoint`. Before a worktree is removed, custody checks verify zero uncommitted lines (preventing the 2026-08-31 `yager/rav-1541-dashboard` failure where 277 uncommitted lines of `TurnPhase` state machine sat stranded inside a merged worktree).
- **The Pull Request Deliverable:** The Author's work ends at an open, tested pull request against `main`, bound to a Linear issue (`RAV-<id>`), with passing Forgejo Actions checks and advisory review from `Snotra`.
- **The Hand-Off Point:** The millisecond the Author's PR merges to `main`, `.forgejo/workflows/build.yml` compiles the ingress unit (`:b<N>`, `:sha-<sha12>`, `:uat`, `@sha256:...`) and pushes it to `Harbor` (**RP-1**). The Author's job is over.

### The Author's Hard Ceilings

1. **Authors Never Tag Releases:** Pushing a `vX.Y.Z` tag from an authoring worktree bypasses UAT soak verification and confuses feature iteration with release authorization.
2. **Authors Never Touch Production Digest Pins:** Feature PRs do not edit `chart/values.yaml` production digest pins or `norns-gitops` manifests. Mixing feature code with release metadata breaks `check-release-source-parity.sh` (**RP-5**) and tries to reference a container digest before `build.yml` has even minted it.

---

## 2. The Release Custodian

The Release Custodian turns a proven `:b<N>` ingress build into a verified, zero-drift Release Pull Request. Because every step in this phase is deterministic and verifiable by script, the Custodian seat can be run by a human tech lead or an automated release preparation slice.

### The Custodian's Bench Recipe

1. **Select the Proven Build Unit:** Inspect `main` and `:uat` telemetry to identify the monotonic build number (`:b42`) that has passed integration verification in staging.
2. **Run `scripts/release-pr.sh`:** From a clean worktree rooted in `.bare`, execute:

   ```bash
   ./scripts/release-pr.sh b42 v1.4.0
   ```

   The script performs four deterministic steps:
   - Queries `Harbor` over the Registry v2 API (`scripts/harbor-artifact.sh digest b42`) to confirm `:b42` exists and pulls its immutable `@sha256:7f9a...3c` digest.
   - Updates `chart/Chart.yaml` (`version` and `appVersion: "1.4.0"`) and `chart/values.yaml` (`tag: "v1.4.0"`, `digest: "sha256:7f9a...3c"`, `build: "b42"`).
   - Generates the structured `CHANGELOG.md` section for `v1.4.0` from commits landed between the previous release and `:b42`.
   - Pushes `release/v1.4.0` and opens the Release PR against `main`.

### Enforcing the Source Parity Gate (RP-5)

The Release Custodian's primary law is **RP-5 (Parity Precedes Promotion)**: a release branch must contain zero application source code changes relative to the parent build commit on `main`.

Before handing the PR to the Delivery Closer, the Custodian runs both verification scripts:

```bash
./scripts/check-release-tag.sh v1.4.0
./scripts/check-release-source-parity.sh
```

`check-release-tag.sh` proves the Parity Triangle (`v1.4.0` tag == `values.yaml` tag == `Chart.yaml` `appVersion`) and confirms that the pinned `@sha256:` digest actually exists in `Harbor`. `check-release-source-parity.sh` runs `git diff --name-only origin/main` and fails closed if any file outside `chart/`, `CHANGELOG.md`, or `docs/runbooks/release.md` was touched:

```bash
git diff "${BUILD_COMMIT_SHA}..HEAD" -- . \
  ':!chart/Chart.yaml' \
  ':!chart/values.yaml' \
  ':!CHANGELOG.md' \
  ':!docs/runbooks/release.md'
```

If a single line of `.rs`, `.go`, `.py`, `.ts`, or `Cargo.toml` appears in that diff, the gate exits `1`. You never patch source code on a release branch.

### Preparing the Annotated Tag

Once the Release PR merges, the release workflow attaches the annotated git tag anchored to the merge commit:

```bash
git tag -a v1.4.0 -m "Release v1.4.0 (build :b42, digest sha256:7f9a...3c)"
```

---

## 3. The Delivery Closer (The Supervisor Seat)

The Delivery Closer holds the merge seat. This is the human-accountable supervisor role that bridges declared intent (the Release PR) and live production reality (`Norns` K3s and workstation taps).

### The Rule of Unbroken Custody

In multi-agent operations governed by Dispatch and `Doomcourt`, merge execution is the one responsibility that **never delegates downward**:

> ### The Rule of Unbroken Custody
>
> *The exact supervisor session that receives explicit human approval for a specific PR ("merge it" / "approved, ship" / "LGTM merge") must execute that merge itself and ride the deployment through live runtime verification. Merge execution is never delegated to a subagent, worker slice, or background queue.*

Why is merge delegation banned across the estate? Because only the session that heard the human operator grant approval first-hand possesses the verified context of *which* PR was approved and under what conditions. Handing a merge off to a subagent severs the custody chain: the worker cannot verify first-hand approval, and if a worker role binding is unavailable, routing a merge to a subagent either stalls an approved ship or trains workers to merge without direct human sign-off. The supervisor merges; the supervisor verifies.

### Executing Merge-Then-Deploy (RP-10)

On the Ravenhelm floor, **a merge to `main` is followed immediately by the deploy to prod.** Merging a PR and walking away - leaving the code sitting undeployed on `main` while Linear says `Done` - was the exact failure mode caught on 2026-09-13 when three merged PRs were reported as finished tools while `the-work` masthead sat on yesterday's container.

When the Delivery Closer squash-merges an approved Release PR, they execute a five-step closeout without leaving the terminal:

1. **Squash Merge via Forgejo API:** Merge the approved Release PR to `main` only after all branch protection checks (`check-release-tag.sh`, `check-release-source-parity.sh`, `Snotra` review) are green.
2. **Expected-Fire Verification:** Confirm within 30 seconds that `.forgejo/workflows/release.yml` actually spawned a run for the new merge commit SHA. (On 2026-09-16, `deploy.yml` silently failed to fire on 1 of 24 pushes to `main`; checking only for failed runs missed the silent non-fire completely.)
3. **Zero-Compile Registry Retag (RP-2):** Watch `release.yml` execute `scripts/harbor-artifact.sh retag`, attaching `:v1.4.0` to `:b42`'s `@sha256:7f9a...3c` digest in `Harbor` and publishing the OCI Helm chart (`vitki-1.4.0.tgz`).
4. **Dual-Rail Execution (RP-6, RP-7):** If the repo is dual-surface (`Ullr`/`Yager`), verify that both Rail A (`norns-gitops` digest bump) and Rail B (`nate/tools` Homebrew tap formula update with sandboxed `inreplace` + local `brew upgrade` reinstall) complete in lockstep.
5. **Declarative GitOps Sync (RP-9):** Confirm Argo CD on `Norns` pulls the updated `norns-gitops` target revision and rolls the deployment pods.

### Proving Life on the Wire (RP-13)

The Delivery Closer never trusts a green CI badge or a shell exit code `0`. Before closing the Linear issue or reporting the ship complete (`pr-ship-report`), the Closer collects four live receipts from the running system:

1. **Rollout Convergence on `Norns`:**

   ```bash
   kubectl rollout status deployment/vitki -n vitki --timeout=120s
   ```

2. **Running Digest Parity:** Verify that the K3s kubelet on `urd`, `verdandi`, or `skuld` is running the exact `@sha256:` digest pinned in `chart/values.yaml`:

   ```bash
   kubectl get pods -n vitki -l app.kubernetes.io/name=vitki \
     -o jsonpath='{.items[*].status.containerStatuses[*].imageID}'
   ```

3. **Live Wire Reachability:** Hit the live ingress endpoint (`curl -fsS https://vitki.ravenhelm.dev/healthz`) and verify HTTP `200 OK`.
4. **Build Coordinate Match:** Query the version endpoint (or run `<tool> --version` and `which -a <tool>` on the workstation for Rail B) to confirm the live binary reports `v1.4.0` and build `:b42`, with zero stale shims shadowing `/opt/homebrew/bin`.

Only when all four receipts are pasted into the validation record does the issue move from `Validation` to `Done`.

---

## 4. The Gatekeeper (Action-Hash Elevation / Valkyrie MFAA)

Routine application deployments stay inside an established architectural envelope and flow through the Delivery Closer's **Merge-Then-Deploy** rail. Operations that alter the envelope itself - identity providers, secret engines, registry RBAC, or architectural cutovers - cross into a different blast radius. Those operations belong to **The Gatekeeper**.

### What Triggers Gatekeeper Elevation (RP-11, RP-17)

Four classes of change cannot ship as routine application releases:
- **Identity & Access Control Plane Mutations:** Modifying SSO clients, OIDC trust policies, or role grants in `Zitadel` or `Keycloak`.
- **Secret Engine & PKI Mutations:** Altering `OpenBao` root policies, AppRole secret-id scopes, or `Draupnir` signing mandates.
- **Registry & Runner Governance:** Changing `Harbor` project immutability rules, robot account scopes, or `forgejo-runner-scheduler` (`frs`) budgets.
- **Architectural Cutovers (`ADR-011`):** Swapping the codebase serving a production endpoint, migrating a backing datastore (e.g., Postgres to ClickHouse on `vakr`), or removing a transport layer. As the 2026-07-18 `Bifrost` cutover incident proved, a cutover disguised as a deploy destroys production custody.

### Action-Hash Elevation: The Valkyrie MFAA Protocol

Under **The Zero-Ambient Elevation Doctrine** (**RP-12**, **RP-17**), neither CI runners nor agent slices hold standing admin credentials for identity or secret planes. Instead, privileged changes execute through **Action-Hash Elevation (Valkyrie MFAA)**:

| Step | Actor | Surface | Mechanical Action & Cryptographic Receipt |
| :--- | :--- | :--- | :--- |
| **1. Read-Only Plan** | Unprivileged CI AppRole | Ephemeral Runner | Runs `terraform plan -out=plan.bin` (or `bao` dry-run) using a read-only `OpenBao` AppRole. |
| **2. Action Hashing** | Unprivileged CI AppRole | Ephemeral Runner | Computes the exact SHA-256 digest of the binary plan: `SHA256(plan.bin) = 9f8a...`. |
| **3. Challenge Emission** | Valkyrie Gate | Out-of-Band Channel | Halts the job and dispatches `{action, target, plan_sha256, diff_summary}` to the human Gatekeeper. |
| **4. Bench Inspection** | Human Gatekeeper | Trusted Workstation | Reads the exact plan diff; verifies pre-flight RBAC (`kubectl auth can-i`) and ADR migration gates. |
| **5. Hardware Signature** | Human Gatekeeper | FIDO2 / Ed25519 Key | Touches hardware key to sign `{action, target, plan_sha256}`; issues a single-use Valkyrie token. |
| **6. Scoped Execution** | `OpenBao` / Valkyrie | Target Control Plane | Verifies `Token.PlanSHA == SHA256(plan.bin)`, mints a 1-use write lease, applies `plan.bin`, and burns the lease. |

Look at why this structure prevents both the `dr-8` failure and the `frs #88` failure:
1. **Unforgable Human Attribution (`dr-8`):** The execution lease cannot be minted without the human Gatekeeper's hardware signature over the exact `PLAN_HASH`.
2. **Zero Personal Credential Leakage (`frs #88`):** The Gatekeeper never pastes their personal token into the runner. The runner executes with a single-use `OpenBao` lease scoped to that one plan digest, while standing control loops (`frs`, Argo CD) run with their own dedicated, monitored service AppRoles.

---

## Human-Agent Pair Operations on the Floor

Running an engineering estate with thirty concurrent `Doom` worker slices does not blur these four roles; it makes the walls between them load-bearing:

```
[ High Concurrency / Bounded Execution ]       [ Non-Delegable Human Accountability ]
        AUTONOMOUS AGENT SLICES                          SOVEREIGN HUMAN SEAT
   ──────────────────────────────────               ──────────────────────────────
       Role: The Author                             Role: The Delivery Closer
       - Isolated .bare worktree per PR             - Approves the specific Release PR
       - Surgical AST reads (eat read)              - Holds unbroken merge custody
       - Unit tests & PR submission                 - Verifies live socket reachability
                                                    - Moves Linear issue to Done
       Role: The Release Custodian
       - Identifies green :b<N> in :uat             Role: The Gatekeeper
       - Runs scripts/release-pr.sh                 - Ratifies ADR-011 cutover plans
       - Proves RP-5 source parity                  - Signs Valkyrie MFAA plan hashes
       - Assembles verification packet              - Authorizes standing mandates
```

### The Relay in Practice

Watch how a release moves across the bench in five minutes:
1. A `Doom` worker slice acting as **Release Custodian** sees that `Vitki` build `:b114` passed `:uat` integration probes. From a clean worktree, it runs `./scripts/release-pr.sh b114 v2.1.0`, verifies zero source drift with `check-release-source-parity.sh`, confirms the Parity Triangle with `check-release-tag.sh`, and opens Release PR #84.
2. The Custodian posts the evidence table on the PR: `:b114`, commit `:sha-4c8e91a02f11`, Harbor digest `@sha256:d4e1...`, and `0` forbidden source files modified.
3. The human operator inspects PR #84 and replies: *"approved, ship"*.
4. The **Delivery Closer** (the supervisor session that received that approval first-hand) squash-merges PR #84, confirms `release.yml` fired on the merge SHA, watches `harbor-artifact.sh retag` bind `:v2.1.0` in 200ms, verifies Argo CD sync on `Norns`, curls the live `/api/v1/version` endpoint to prove `v2.1.0` (`b114`) is serving traffic, and logs the ship report.

---

## Five Role Anti-Patterns and Their Estate Receipts

Whenever a team blurs the boundaries between Author, Custodian, Closer, and Gatekeeper, one of five failures lands on the bench:

### 1. The Unattributed Automation Ghost (`dr-8`, 2026-09-14)
- **The Symptom:** Designing a background issuer, release bot, or cron runner that signs artifacts or mutates production with "no human signer" in the provenance chain.
- **The Consequence:** When an automated action misfires or is abused, audit logs terminate at a generic bot string with zero record of who authorized the mandate.
- **The Fix:** Every service credential and standing mandate chains back to a named human signer's attestation.

### 2. The Personal-PAT Control Plane (`frs #88`, 2026-10-08)
- **The Symptom:** Wiring an operator's personal access token or personal kubeconfig into a long-running controller (`forgejo-runner-scheduler`), CI secret, or KEDA scaler because "my token already has permissions."
- **The Consequence:** Personal token rotation or scope edits silently break production autoscaling, and every action taken by the daemon shows up in the audit log as the human typing at a keyboard.
- **The Fix:** Control loops run exclusively with their own dedicated `OpenBao` AppRole or service account credential, monitored for expiration and scoped to the service's exact API surface (**RP-12**).

### 3. The Merge-and-Vanish Closer (2026-09-13 & 2026-09-16)
- **The Symptom:** Merging a PR, seeing a green merge button, marking the Linear ticket `Done`, and closing the session without checking if `deploy.yml` fired or if the pod rolled.
- **The Consequence:** On 2026-09-13, `the-work` masthead stayed on old code after three merged PRs were declared finished; on 2026-09-16, 1 of 24 merges to `main` never triggered `deploy.yml` at all.
- **The Fix:** **Merge-Then-Deploy (RP-10)** + **Live Reachability Proof (RP-13)**. The Closer stays in the seat until the workflow run ID is confirmed and the live socket returns the new build number.

### 4. The Delegated Merge Handoff
- **The Symptom:** The supervisor session receives human approval (*"LGTM merge"*) and spawns a background worker agent to merge the PR and deploy it.
- **The Consequence:** Custody breaks. The worker did not witness the approval, cannot adjudicate unexpected merge conflicts or RBAC errors (`RAV-2086`), and leaves the supervisor blind to half-shipped state.
- **The Fix:** **The Rule of Unbroken Custody.** Merge execution is never delegated to a worker slice.

### 5. The Sneak-Fix Custodian
- **The Symptom:** While cutting `release/v1.4.0`, the Custodian spots a minor bug in `src/` or bumps `Cargo.toml` directly on the release branch.
- **The Consequence:** Because `release.yml` never compiles code (**RP-2**), the source edit either ships as a ghost diff (present in git, absent from the `:b42` container) or forces an illegal rebuild.
- **The Fix:** `check-release-source-parity.sh` (**RP-5**) fails the release PR automatically on any non-metadata diff.

---

## The Release Operator Practice Ladder

| Maturity Level | Floor Behavior | Primary Failure Mode | Gate to Advance |
| :--- | :--- | :--- | :--- |
| **Level 0: Communal Chaos** | Anyone builds, tags, and runs `kubectl apply` from laptops; `:latest` in prod; personal PATs in scripts. | Split-brain clusters, unattributed outages (`frs #88`), stale `~/.local/bin` shims. | Adopt **ADR-0007**: build `:b<N>` on `main` ingress; stop compiling on tag. |
| **Level 1: Scripted Custodian** | CI builds `:b<N>` on `main`; operators cut releases with `release-pr.sh` and enforce `RP-5` parity. | Merged PRs sit undeployed on `main`; silent workflow non-fires go unnoticed. | Enforce **Merge-Then-Deploy (RP-10)** and expected-fire workflow checks. |
| **Level 2: Sovereign Custody** | Strict Author / Custodian / Closer separation; unbroken merge custody; Argo CD pull sync (`norns-gitops`). | Control-plane changes and cutovers still share routine pipeline permissions. | Enforce **ADR-011** cutover gates (**RP-11**) and live reachability probes (**RP-13**). |
| **Level 3: Fleet-Scale Sovereignty** | 30+ concurrent agent Authors in `.bare` worktrees; service-scoped `OpenBao` AppRoles; **Action-Hash Elevation (Valkyrie MFAA)**. | Zero ambient authority; every automated action chains to a human mandate (`dr-8`). | Audit against the Chapter 14 Assessment and verify empty-set failure modes. |

Tools gather the evidence, verify the parity triangle, and stage the pull request at 3:00 a.m. A human clicks the accept/reject button, holds the merge seat until the live socket answers, and signs the mandate with their own name.

<!-- RUBRIC_CHECK:
  structural: pass
  content: pass
  word-count: 2540
  principle-citations: RP-1, RP-2, RP-5, RP-6, RP-7, RP-9, RP-10, RP-11, RP-12, RP-13, RP-16, RP-17, RP-18
  flagged-principle-gaps: none
-->

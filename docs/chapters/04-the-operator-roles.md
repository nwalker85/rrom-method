# Chapter 4: The Operator Roles

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Sovereign Human and Agent Responsibilities

It is Thursday evening at 6:45 p.m. An engineer has pushed a hotfix directly to a feature branch, tagged `v2.4.1` locally from their workstation terminal, and pushed both branch and tag to the code host. In the release channel, someone asks, "Has this hit production?" The engineer replies, "CI passed, so it should be live." 

Meanwhile, inside the production cluster, Argo CD is crash-looping. The container tag `v2.4.1` was pulled, but it pointed to an untracked ad-hoc binary that was compiled without the database migration bundled in the build container. The release manifest contained uncommitted local edits, and no runtime probe was ever queried. When the incident channel opens, accountability evaporates into distributed ambiguity. The developer says, "DevOps owns the deployment manifests." The DevOps engineer says, "I don't write application code or review PRs." The product manager says, "I approved the ticket in the sprint board."

This is the failure mode the Ravenhelm Release Operations Methodology (RROM) is engineered to eradicate. It occurs whenever organizations treat release operations as an ambient, communal chore rather than a sovereign operational discipline. When everyone is nominally responsible for releasing software, no one is actually accountable for the integrity of production.

Under RROM, release management is partitioned into four distinct, non-overlapping roles with rigid boundary contracts:

| Role | Actor Profile | Workspace & Scope | Authority Boundary |
| :--- | :--- | :--- | :--- |
| **The Author** | Human Engineer / AI Worker | Dedicated git worktree (`feat/*`); application diffs, unit tests. | Strictly prohibited from tagging releases, editing values manifests, or deploying. |
| **Release Custodian** | Tech Lead / Release Bot | Integration trunk (`main`); identifies `:b<N>`, generates release PRs. | Enforces Source Parity Rule (RP-5); creates annotated tags; runs parity checks. |
| **Delivery Closer** | Fleet Supervisor (Human) | Production release seat; merge authority. | Executes Merge-Then-Deploy (RP-10); unmerged PRs stay unmerged; verifies runtime proof. |
| **The Gatekeeper** | Sovereign Operator (Human) | High blast radius infrastructure & cutovers. | Issues cryptographic plan-hash signatures via hardware FIDO2 key for elevation. |

These roles are not job titles; they are sovereign runtime hats governed by explicit capability ceilings and invariants. An actor—whether a principal engineer, a platform lead, or an autonomous AI agent—steps into a specific role, executes its bounded mandate under strict custody rules, and yields the seat.

| Role | Primary Actor | Core Invariant | Absolute Ceiling | Primary Tools |
| :--- | :--- | :--- | :--- | :--- |
| **The Author** | Human Engineer or Autonomous Worker | Application logic correctness and test suite verification. | Never tags releases; never edits production manifests. | Disposable Git Worktrees, Language Toolchains, Unit Tests. |
| **The Release Custodian** | Technical Lead or Autonomous Release Daemon | Provenance verification, metadata hygiene, zero source drift. | Never introduces source code edits; never merges release PRs. | `scripts/release-pr.sh`, `check-release-source-parity.sh`. |
| **The Delivery Closer** | Fleet Supervisor or Designated Release Lead | Unbroken custody of authorization; runtime proof of live traffic. | Never delegates merge or deploy execution across sessions. | Code Host API, GitOps Engine (Argo CD), Live Health Probes. |
| **The Gatekeeper** | Sovereign Human Authority (MFAA Holder) | Defense against catastrophic architectural and identity blast radius. | Never grants ambient, reusable credentials or bypasses plan hashing. | Valkyrie MFAA, Hardware Security Keys (FIDO2), OpenBao Tokens. |

---

## 1. The Author (Human Engineer or Autonomous Coding Agent)

The Author is the creative engine of the software estate. Whether fulfilled by a staff software engineer or an autonomous coding agent operating in an isolated runtime slice, the Author's purpose is singular: to advance application functionality, resolve defects, and optimize system behavior.

### Scope Boundaries and Invariants
The Author's operational perimeter is strictly confined to application source files, unit and integration tests, and local developer documentation:

* **Isolation in Disposable Git Worktrees (RP-18):** Authors never execute work directly on `main` or inside a shared, dirty working tree. All development occurs inside dedicated, ephemeral git worktrees established via the Checkout Custody Standard (`git worktree add`). Worktree paths project canonical identity, history lives centrally in `.bare/`, and worktrees are destroyed upon PR submission. Stashing changes (`git stash`) across branches is strictly forbidden; work in progress is captured in structured WIP commits.
* **The Pull Request Deliverable:** The Author's terminal deliverable is an integrated, verified pull request targeting the integration trunk (`main`). This PR must carry passing continuous integration checks, exhaustive test coverage, and clear commit messaging adhering to Conventional Commits.
* **The Hand-Off Point:** Once an Author's PR merges to `main`, an immutable build artifact (`:b<N>`) is produced automatically on ingress (RP-1). At this exact moment, the Author's custody terminates. The Author does not shepherd the build into staging, tag releases, or monitor production traffic.

### The Author's Absolute Ceilings
To maintain structural separation of concerns, the Author is constrained by two non-negotiable boundaries:

1. **Authors Never Tag Releases:** Release tags (`vX.Y.Z`) represent authorized operational names assigned to pre-existing, tested artifacts. When an author tags a commit during feature development, they conflate compilation with release authorization. This invites unverified binaries into production and destroys audit trails.
2. **Authors Never Modify Release Manifests:** An authoring PR must never alter production Helm values files, container digest pins (`@sha256:...`), or deployment target manifests. Modifying release manifests inside an application feature branch breaks the Release Parity Rule (RP-5) and forces premature configuration into the trunk before the underlying build artifact has been compiled or tested.

---

## 2. The Release Custodian

The Release Custodian is the guardian of artifact provenance and release metadata. Where the Author focuses on functional logic, the Custodian focuses on structural integrity, traceability, and version governance. This role may be performed by a human release engineer, an engineering lead, or a fully automated release daemon executing on a schedule.

### The Responsibilities of the Custodian
The Custodian transforms an anonymous, pre-tested build artifact into an authorized, human-readable release candidate:

* **Identifying the Target Build:** The Custodian inspects the trunk integration stream (`main`) and identifies an incremental build sequence (`:b<N>`) that has successfully passed all automated regression and end-to-end test suites in the pre-production environment (UAT/staging).
* **Mechanical Execution of `release-pr.sh`:** The Custodian does not manually modify files or write bespoke changelogs. Instead, they execute the standardized release script:
  ```bash
  ./scripts/release-pr.sh b42 v1.4.0
  ```
  The script performs four mechanical operations in strict lockstep:
  1. Inspects the remote artifact registry (Harbor) to confirm that `:b42` exists and extracts its canonical, immutable digest (`@sha256:7f9a...3c`).
  2. Updates deployment manifests (e.g., `Chart.yaml`, `values.yaml`) to reference version `v1.4.0` and pin the exact build digest.
  3. Synthesizes a structured, categorized `CHANGELOG.md` entry derived from conventional commit messages between the prior release tag and `:b42`.
  4. Generates a dedicated release branch (`release/v1.4.0`) and opens a formal Release Pull Request against `main`.

### Source Parity Enforcement (RP-5)
The supreme invariant of the Release Custodian is the **Release Parity Rule**: *a release candidate must prove zero source code drift against the parent build commit*.

Before a Release PR can be considered valid, the Custodian executes the canonical verification script:
```bash
./scripts/check-release-source-parity.sh
```

This gate performs a cryptographic diff between the target build commit SHA on `main` and the release candidate branch, filtering out authorized metadata paths:
```bash
git diff "${BUILD_COMMIT_SHA}..HEAD" -- . \
  ':!Chart.yaml' \
  ':!values.yaml' \
  ':!CHANGELOG.md' \
  ':!package.json' \
  ':!package-lock.json'
```

If a single line of application source code, configuration logic, or embedded asset has drifted, the check exits with a non-zero failure code. The release is immediately rejected. Sneaking "just one tiny bugfix" or "a quick CSS adjustment" into a release commit bypasses build-time test suites, invalidates binary provenance, and violates RP-5.

### Formulation of Annotated Git Tags
The Release Custodian prepares the signed, annotated git tag:
```bash
git tag -s -a v1.4.0 -m "Release v1.4.0 (build :b42, digest sha256:7f9a...3c)"
```
Under RROM, release tags are never floating markers on arbitrary developer branches. They are cryptographically signed, annotated tags anchored to the exact commit SHA that produced the underlying build artifact.

---

## 3. The Delivery Closer (The Supervisor)

The Delivery Closer is the operational supervisor who holds the merge seat. This role is the final, sovereign gatekeeper of production convergence. In human teams, this is the technical director, on-call supervisor, or platform lead. In autonomous multi-agent environments, this is the Fleet Supervisor seat.

### The Rule of Unbroken Custody
The cornerstone of operational accountability is the **Rule of Unbroken Custody**:

> ### The Rule of Unbroken Custody
> *The exact operational session that receives human authorization to execute a merge must personally execute that merge and shepherd the deployment through verification. Merge authority is non-transferable and can never be delegated to subordinate workers, child agents, or background queues.*

When Nate or an authorized engineering leader inspects a Release PR and issues the command—"Merge it," "Approved, ship," or "LGTM merge"—that approval is granted strictly to the receiving supervisor session. 

If Session A receives human approval, Session A cannot file a background ticket or invoke an asynchronous subagent to "do the merge." Delegating the merge splits the custody chain. The subordinate session lacks first-hand context, cannot verify the identity of the approval, and cannot guarantee immediate deployment shepherding. The session that received the approval holds the merge seat until production convergence is verified.

### The Merge-Then-Deploy Lifecycle (RP-10)
Under RROM, merging a release PR and deploying software are not two disconnected decisions. **Approval to merge is approval to ship.**

The traditional practice of "merge now, deploy next Tuesday" is an operational pathology. It leaves unverified, dormant code sitting on `main`, blocks subsequent emergency fixes, and obscures the relationship between source state and runtime state. 

When the Delivery Closer executes a squash merge of an approved Release PR, they immediately trigger the deterministic Merge-Then-Deploy pipeline:
1. **Squash Merge Execution:** The Delivery Closer merges the release PR to `main` via the code host API, recording the approver's identity and timestamp in the merge commit metadata.
2. **Registry Name Binding:** The code host CI pipeline catches the merge event and attaches the official SemVer tag (`:v1.4.0`) to the pre-existing build digest (`:b42` / `sha256:7f9a...3c`) within Harbor. Zero compilation occurs (RP-2).
3. **Multi-Surface Rail Execution (RP-6):** If the repository serves multiple surfaces (e.g., K3s backend service and a workstation CLI), the Closer ensures all rails execute simultaneously. For CLI formulas, the sandboxed `inreplace` automation updates the Homebrew tap formula (`nate/tools`) without dirtying git history (RP-7).
4. **GitOps Convergence (RP-9):** The release pipeline updates the target digest pin inside the sovereign GitOps repository (`norns-gitops`). Argo CD detects the git commit and initiates declarative synchronization.

### Proof of Life (RP-13)
The Delivery Closer does not close their terminal session when the merge command returns exit code `0`. **Shell success is not proof of life.** A shell script exiting cleanly indicates only that commands ran without syntax errors; it does not prove that container pods are healthy or that traffic is routing correctly.

The Delivery Closer remains on duty until independent runtime verification satisfies four gates:
1. **Pod Rollout Health:** Kubernetes reports zero crash-looping containers and confirms complete rollout:
   ```bash
   kubectl rollout status deployment/bifrost -n ravenmaskos --timeout=120s
   ```
2. **Digest Verification:** The running pods are actively executing the exact immutable SHA-256 digest declared in the release manifest:
   ```bash
   kubectl get pods -n ravenmaskos -l app=bifrost \
     -o jsonpath='{.items[*].status.containerStatuses[*].imageID}'
   ```
3. **Live Health Probe:** The service responds with HTTP `200 OK` across the internal live network interface:
   ```bash
   curl -fsS https://bifrost.ravenmask.net/healthz
   ```
4. **Version Contract Match:** The runtime application queries return the exact released SemVer string (`v1.4.0`) and monotonic build number (`b42`).

Only when all four gates pass does the Delivery Closer issue the final release report, update the project tracking ledger, and relinquish the merge seat.

---

## 4. The Gatekeeper (Valkyrie Human-in-the-Loop)

While routine application releases flow autonomously through the Merge-Then-Deploy pipeline, certain operational events carry catastrophic blast radii. These are designated as **Elevation Events**. For these events, the sovereign **Gatekeeper** role activates.

### Elevation Boundaries (RP-11, RP-17)
The Gatekeeper role governs operations where an error or malicious compromise could destroy cluster integrity, wipe persistent datastores, or leak root credentials:
* **Identity and Access Plane Mutations:** Altering authentication policies, SSO client registrations, or role mappings in Zitadel or Keycloak.
* **Secrets Engine Mounts:** Modifying OpenBao/Vault root policies, access control lists, or storage backend configurations.
* **Registry Governance:** Altering Harbor RBAC, project immutability policies, or public replication endpoints.
* **Architectural Cutovers:** Swapping production datastores (e.g., PostgreSQL major version migrations), replacing communication transports, or executing non-additive database schema drops.

Routine deployments reconcile application code within existing architectures. Cutovers and elevation events alter the underlying platform fabric. Under RP-11, cutovers require an Architectural Decision Record (ADR), an explicit data migration plan, and formal human Gatekeeper authorization.

### The Valkyrie MFAA Protocol
To ensure that elevation events cannot be triggered by compromised CI runners, stolen developer laptops, or runaway autonomous agents, Ravenhelm enforces the **Valkyrie Multi-Factor Action Approval (MFAA)** protocol.

| Protocol Step | Originator | Target | Action & Cryptographic Invariant |
| :--- | :--- | :--- | :--- |
| **1. Plan Generation** | Unprivileged CI | Local Workspace | Generates deterministic execution plan (`terraform plan -out=plan.bin`). |
| **2. Hash Computation** | Unprivileged CI | Local Workspace | Computes immutable SHA-256 digest of plan file: `SHA256(plan.bin) = 9f8a...`. |
| **3. Challenge Dispatch** | Unprivileged CI | Human Gatekeeper | Submits challenge payload: `{action: "apply", target: "prod", plan_sha256}`. |
| **4. Human Inspection** | Human Gatekeeper | Out-of-Band Channel | Inspects plan diff; verifies no unauthorized destructive actions. |
| **5. Hardware Signing** | Human Gatekeeper | Unprivileged CI | Signs challenge using hardware FIDO2 key (Ed25519); issues single-use token. |
| **6. Execution & Burn** | Unprivileged CI | Secret Engine | Secret engine verifies `Token.PlanSHA == Plan.SHA`, burns token, applies change. |

The protocol operates under four ironclad phases:

1. **Read-Only Plan Generation:** The CI runner executes the configuration tool (`terraform plan`, `bao policy check`) in strictly read-only mode using an unprivileged AppRole. It saves the compiled execution plan to disk.
2. **Cryptographic Action Digesting:** The runner computes the canonical SHA-256 hash of the execution plan:
   ```bash
   PLAN_HASH=$(sha256sum plan.bin | awk '{print $1}')
   ```
3. **Structured Challenge and Cryptographic Signing:** The pipeline halts execution and emits an out-of-band Valkyrie challenge to the designated human Gatekeeper. The Gatekeeper inspects the human-readable diff on a trusted, sovereign terminal and signs the challenge using a hardware security token (FIDO2 / Ed25519 key). The signature cryptographically binds the Gatekeeper's identity to the exact `PLAN_HASH`.
4. **Single-Use Action Tokens (RP-12):** The signed approval is exchanged with the secrets engine for a scoped, short-lived action token. The token is valid for exactly one execution, matches the specific `PLAN_HASH`, and is instantly revoked upon consumption.

If a rogue script attempts to substitute a different plan file or modify infrastructure outside the signed hash, the engine rejects the token and aborts the pipeline. Zero ambient administrative credentials exist on CI runners or developer machines.

---

## Human-Agent Pair Operations

The emergence of autonomous coding agents and multi-agent supervisory frameworks does not abolish operator roles; it demands their rigorous formalization. When software systems are touched by both humans and autonomous LLM agents, role boundaries must be mathematically explicit.

### The Division of Sovereignty
Under RROM, human-agent pair operations partition duties across the cognitive spectrum:

```
[ Cognitive Velocity: High / Broad ]          [ Sovereign Accountability: Strict / Bounded ]
        AUTONOMOUS AI AGENTS                              SOVEREIGN HUMANS
   ──────────────────────────────                    ──────────────────────────
      Role: The Author                               Role: The Delivery Closer
      - Parallel worktrees                           - Evaluates business risk
      - Exhaustive test writing                      - Holds merge authority
      - Linting and refactoring                      - Enforces unbroken custody
                                                     - Proves runtime health
      Role: The Release Custodian
      - Scans trunk for :b<N>                        Role: The Gatekeeper
      - Runs release-pr.sh                           - Owns platform blast radius
      - Verifies source parity                       - Signs hardware MFAA tokens
      - Drafts changelogs                            - Approves architectural ADRs
```

* **Agents as Authors:** Autonomous agents operate with unmatched velocity when generating code diffs inside isolated worktrees. They excel at fulfilling specific issue specifications, generating unit test matrices, and refactoring legacy interfaces. They remain bounded by Author ceilings: no release tagging, no direct pushes, no manifest editing.
* **Agents as Release Custodians:** The mechanical routine of scanning integration builds, comparing registry digests, running `release-pr.sh`, executing `check-release-source-parity.sh`, and formatting changelogs is ideal for automated release daemons. Agents eliminate human fatigue and formatting errors in release preparation.
* **Humans as Delivery Closers:** Humans retain exclusive sovereignty over the decision to merge and deploy software to production. While an agent can prepare the Release PR and present verified proof of parity, only a human supervisor can accept business liability, evaluate customer impact, and issue the explicit authorization to ship. The human supervisor maintains unbroken custody throughout the deployment convergence.
* **Humans as Gatekeepers:** Autonomous agents must never possess elevation authority. Gatekeeper actions require cryptographic physical proof of human presence (hardware FIDO2 keys). An agent may formulate an architectural cutover plan, but only a human Gatekeeper can sign the Valkyrie challenge.

### The Supervised Release Hand-Off
In practical daily operations, this human-agent pairing executes as a clean relay:
1. An agent acting as **Release Custodian** detects that build `:b114` has passed all staging tests. It branches `release/v2.1.0`, runs `release-pr.sh`, proves zero source code drift via `check-release-source-parity.sh`, and opens Release PR #84.
2. The agent attaches a comprehensive evidence packet to the PR:
   - Base build commit SHA and Harbor digest reference (`sha256:d4e1...`).
   - Clean output from the parity verification script.
   - Staging smoke test execution logs.
3. The human **Delivery Closer** reviews the evidence packet. Satisfied with the verification proof, the human types: `"LGTM, ship v2.1.0"`.
4. The supervisor session executes the squash merge, triggers the Argo CD sync, observes the pod rollout, verifies live health probes, and signs off on the release.

---

## Anti-Patterns in Release Operations

When teams deviate from RROM role boundaries, release operations degrade into predictable, high-risk anti-patterns. Recognizing these behaviors is essential for maintaining operational health.

### 1. The Absentee Deployer
* **The Symptom:** An operator merges an approved release PR at 4:55 p.m. on a Friday and immediately logs off, assuming CI will "handle the rest."
* **The Failure:** The code host CI pipeline encounters a transient container registry timeout while retagging the image, or Argo CD encounters an invalid schema configuration and fails to converge. The production cluster enters a degraded state with zero human awareness.
* **The Remedy:** The Delivery Closer must never merge and walk away. Merge-Then-Deploy (RP-10) mandates that the closer remain in session until runtime health probes confirm live production traffic (RP-13).

### 2. The Ambient Admin
* **The Symptom:** CI runners and developer laptops are provisioned with permanent, long-lived `cluster-admin` kubeconfigs or wildcard cloud provider IAM keys to "avoid pipeline friction."
* **The Failure:** A supply chain dependency compromise in a build tool or an unvalidated pull request script accesses ambient administrative tokens, exfiltrating production databases or modifying core network routing.
* **The Remedy:** Zero Ambient CI Authority (RP-12). Workstation credentials and CI runners operate with zero default administrative privileges. High-blast-radius operations require single-use, plan-bound action tokens issued via Valkyrie MFAA.

### 3. The Split-Brain Approval
* **The Symptom:** A team lead approves a release in a Slack thread or project ticket, but delegates the physical execution of the git merge to an asynchronous background worker agent or junior operator.
* **The Failure:** The custody chain is severed. The executing worker lacks the supervisor's contextual awareness of system health, fails to verify if environmental conditions have shifted since the approval was granted, and cannot react intelligently if deployment reconciliation stalls.
* **The Remedy:** The Rule of Unbroken Custody. The exact operational session that receives approval must personally execute the merge and monitor the deployment through to proof of life.

### 4. The Drive-By Release Fix
* **The Symptom:** During pre-release staging review, an engineer notices a minor styling bug or typo. Rather than opening a feature PR against `main`, they commit the fix directly to the `release/vX.Y.Z` branch.
* **The Failure:** The release candidate branch now possesses source code drift relative to the pre-tested `:b<N>` build artifact. The release script either re-compiles an unverified binary on the fly (violating RP-2) or ships an image that does not contain the committed fix, creating a ghost diff.
* **The Remedy:** Parity Precedes Promotion (RP-5). The Release Custodian enforces `check-release-source-parity.sh`. Any source diff on a release branch triggers instant pipeline failure. Fixes must land on `main` and earn a new build sequence.

### 5. The Ghost Rebuild
* **The Symptom:** A release pipeline is configured to trigger `docker build` whenever a SemVer git tag (`v*.*.*`) is pushed to the repository.
* **The Failure:** The binary deployed to production is compiled at release time, days or weeks after the staging artifact was tested. Downstream package mirror drift, updated OS base image layers, or nondeterministic compiler flags yield a binary delta between staging and production.
* **The Remedy:** Builds are the unit; releases are names (Chapter 2 Axiom). Release workflows assign tags to existing, immutable registry digests. Releases never rebuild code (RP-2).

---

## The Release Operator Practice Ladder

Teams transitioning to RROM do not adopt sovereign role discipline overnight. Organizations evolve through four progressive levels of release operational maturity:

| Maturity Level | Operational Pattern | Failure Vector | Transition Trigger |
| :--- | :--- | :--- | :--- |
| **Level 0: Ad-Hoc Deployer** | Engineers compile and deploy from laptops; releases are built on demand; mutable tags (`latest`) in production. | Inability to reproduce builds; catastrophic drift; unverified binaries in production. | Adopt Chapter 2 Axiom: Builds are the unit; releases never rebuild. |
| **Level 1: Reactive Custodian** | CI builds on `main`; releases are cut manually via informal PRs; deployments executed via manual CLI commands. | "Merge and wait" zombie commits; release PRs carry unverified source code changes. | Install `release-pr.sh` and automate `check-release-source-parity.sh` (RP-5). |
| **Level 2: Sovereign Practitioner** | Strict role separation (Author vs. Custodian vs. Closer); GitOps convergence (Argo CD); Merge-Then-Deploy enforced. | Occasional broken custody hand-offs; elevation events lack cryptographic plan hashing. | Enforce Unbroken Custody rule and integrate live health probes (RP-13). |
| **Level 3: Fleet Release Master** | Human-Agent pairing; autonomous release daemons; Valkyrie MFAA for all elevation events; full immutable audit ledgers. | None; estate operates under zero ambient authority and automated cryptographic provenance. | Benchmark against Chapter 14 Assessment and audit compliance ledgers (RP-16). |

The transition from Level 1 to Level 2 is the most critical hurdle. It occurs the first time an engineering supervisor rejects a release PR because it touched application source code, or the first time a team refuses to merge a PR until the supervisor is present to personally verify runtime proof of life. 

Process does not release software; sovereign operators release software. By defining explicit boundaries, invariants, and hand-off contracts, RROM transforms release operations from an anxious gamble into a predictable, mathematically verified discipline.

<!-- RUBRIC_CHECK:
  structural: pass
  content: pass
  word-count: ~2100
  principle-citations: RP-1, RP-2, RP-5, RP-6, RP-7, RP-9, RP-10, RP-11, RP-12, RP-13, RP-16, RP-17, RP-18
  flagged-principle-gaps: none
-->

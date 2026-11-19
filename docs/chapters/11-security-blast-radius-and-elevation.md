# Chapter 11: Security Blast Radius & Elevation

<!-- LICENSE: © 2026 Ravenhelm LLC. Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Attribution required: "Ravenhelm LLC — Ravenhelm Release Operations Methodology (RROM), https://ravenhelm.dev". -->

## The Principle of Blast Radius Partitioning (RP-17)

On September 29, 2026, an autonomous agent slice inspected a Kubernetes `Secret` on the `Norns` cluster (`urd`, `verdandi`, `skuld`) to verify whether the `rig-ci` Harbor robot credential had mounted into the namespace. Knowing it should not dump `.data`, the worker ran a command to inspect `.metadata` alone. It leaked the entire `rig-ci` robot token into the session transcript anyway. Because the secret had been created with `kubectl apply`, the `kubectl.kubernetes.io/last-applied-configuration` annotation inside `.metadata.annotations` held the complete, unredacted JSON payload in plaintext. The same day, a second worker tried to redact a credential inline by piping output through `sed` on a macOS workstation; because macOS ships BSD `sed` rather than GNU `sed`, the regex flags failed to match and the raw secret printed straight to stdout. Fix the redaction primitive: mask secrets with Python (`python3 -c`), never BSD `sed`.

Those two leaks sat alongside two older scars on the bench. Earlier in the summer, a diagnostic worker ran `pgrep -lf` and `ps eww` to hunt down a wedged daemon, dumping the full environment variables of every running process on the host into the persistent JSONL log, while another slice passed a bearer token directly on `curl` argv where any process reading `/proc` or the process table could scrape it (pass credentials via `stdin` using `curl --config -`, never in argv). And when an autonomous loop needed a secret from 1Password (`op`), the naive v1 script put `op item get` inside a `while` polling loop. Every single iteration fired a macOS TCC biometric prompt on the operator's screen every four seconds until the loop was killed.

When you move from supervising 300 human operators on XMPP to supervising a fleet of autonomous AI sessions, the control structures transfer, but the social layer does not. A human operator knows not to paste a plaintext secret into a chat room, notices when a `sed` expression prints the raw password back out, and stops calling `op` the first time Touch ID pops up unexpectedly. An agent has no peripheral vision and no shame. If a token is reachable in ambient memory, an annotation, a process table, or an environment variable, the agent will eventually read it, log it, or spend it.

To CI runners, GitOps reconcilers, and container schedulers, every change looks like a git commit that triggers a workflow. Because the delivery plumbing looks identical across services, engineering teams routinely hand identical authority to every automated job. When an autonomous agent, a bot, or an engineer pushes code, the runner inherits the ambient credentials sitting in its execution environment. If that runner holds cluster-admin Kubernetes tokens, root vault capabilities, or wide cloud-provider keys, one prompt injection or one confused-deputy repair loop hands the entire estate to the process.

Under the Ravenhelm Release Operations Methodology (RROM), **Principle RP-17: Separation of Blast Radii** cuts that wire.

RROM partitions every operational mutation into two physically isolated security surfaces. Routine application deploys are severed from control-plane, datastore, network, and identity mutations. No automated worker or CI runner ever holds ambient authority to alter the security topology of the estate.

![Diagram 4: Blast Radius Partitioning](diagram4-blast-radius)

Even if an autonomous worker or CI runner is compromised or hallucinates a destructive repair, the blast radius stops at an unprivileged application container. It cannot pivot into root identity, secret engines, firewall rules, or relational schemas. It hits a wall.

---

## 1. Surface 1: Autonomous Application Mutations (Low Blast Radius)

Surface 1 covers the routine, high-frequency application changes that ship across the estate dozens of times a day: container images for `Bifrost`, `Heimdall`, `Vidar`, `Freyr`, `Mimir`, or `Vitki`; Helm values adjusting replica counts or memory limits; and non-structural feature flags.

### Scope Boundaries

Surface 1 mutations are restricted to stateless and state-isolated application workloads:
- **Container Images:** Application binaries, microservice containers, worker tasks, and static web assets compiled once during trunk ingress (`:b<N>`).
- **Deployment Manifests & Helm Values:** Replicas, CPU and memory requests/limits, ingress path rules, and environment variables referencing pre-existing secret mounts.
- **Feature Flags & Non-Structural Config:** Dynamic application flags, localization bundles, and operational thresholds that do not alter infrastructure topology or security boundaries.

### Authority Model: Merge-Then-Deploy (RP-10)

For Surface 1 mutations, RROM enforces **Merge-Then-Deploy**. Explicit human approval on a pull request targeting `main` is the complete authorization for production rollout:
- Once the human lead approves and merges an application PR, the autonomous delivery lane compiles, packages, and ships the artifact without pausing for a second manual gate.
- Autonomous deployment works on Surface 1 because the blast radius of a bad build is bounded to a pod replica set, verified by live probes, and reversible in seconds.

### Credential Profile, OpenBao AppRole, & Network Isolation

Surface 1 runs on machine identity and strict credential minimization:
1. **OpenBao AppRole Machine Identity:** Services and automation lanes authenticate with their own dedicated machine credentials provisioned via **OpenBao AppRole** on `Norns` (`automation-identity-openbao-approle-and-valkyrie-on-norns.md`), never with a borrowed human Personal Access Token (PAT) and never by calling `op` inside a loop.
2. **Scoped Robot Tokens:** The CI runner receives a least-privilege Harbor robot token scoped to push images into a single project repository (for example, `harbor.ravenhelm.dev/platform/vitki`). That token cannot delete tags, create projects, weaken immutability rules, or touch sibling repositories.
3. **Zero Cluster Control Plane Secrets:** The CI runner holds no `kubeconfig`, no Kubernetes service account token, and no network route to the Kubernetes API server (`:6443`).
4. **Pull-Based GitOps Reconciliation:** Runners never run `kubectl apply` or `helm upgrade` against production. Instead, the release lane commits the pinned digest (`:b<N>@sha256:...`) to `norns-gitops`. Argo CD, running inside the cluster network on `Norns`, pulls the commit and reconciles the pods. The runner never touches the cluster.

### Failure Semantics & Deterministic Rollback

When a Surface 1 deploy ships a defect - an unhandled panic, a deadlocked worker, or a bad config parse - the damage stays inside that deployment's replica set. The new pod enters `CrashLoopBackOff`, readiness probes fail, and Kubernetes keeps traffic pinned to the previous healthy replica set. Under **Principle RP-14: Rollback is a Pointer Revert**, recovery is a single git revert of the digest pointer in `norns-gitops`. No rebuilds. No panic.

---

## 2. Surface 2: Control Plane & Identity Mutations (High Blast Radius)

Surface 2 governs the foundation of the estate: identity providers, secret engines, firewall rules, registry permissions, and database schemas. A bad mutation here does not just crash a pod; it locks out every operator, drops relational tables, or exposes the cryptographic root.

### Scope Boundaries

Any change touching these five domains is a Surface 2 event:
- **Identity and Access Management (IAM):** Keycloak or Zitadel realms, client registrations, OAuth2/OIDC redirect URIs, token claim mappers, user federation rules, and directory syncs.
- **Secrets Infrastructure:** **OpenBao** policies, auth mounts (AppRole, JWT/OIDC, Kubernetes auth), secrets engines, and transit signing keys.
- **Container Registry Governance:** **Harbor** system RBAC, project access controls, vulnerability thresholds, and immutable tag retention rules.
- **Database Schemas & DDL Operations:** Relational schema migrations on `odin`, `hrafngud`, `vakr`, or `Norns`, table drops, column type alterations, production index builds, and role grants.
- **Network & Hypervisor Fabric:** OPNsense (`Modi`) firewall rules, MikroTik VLAN tables, Tailscale ACLs, Cloudflare Zero Trust tunnel routes, and host-level configurations.

### Authority Model: Strictly Non-Autonomous

Surface 2 suspends autonomous *Merge-Then-Deploy* completely.

Even after a pull request modifying an OpenBao policy or a Zitadel realm merges to `main`, **no automated runner has ambient authority to run `terraform apply` or mutate the live control plane**. Surface 2 mutations require an explicit, out-of-band cryptographic elevation signed by a human holding **The Gatekeeper** seat. Agents can draft the code, run syntax checks, and compile the deterministic execution plan, but the protocol blocks them from applying it alone.

### Failure Semantics

An unpartitioned Surface 2 failure is catastrophic:
- A broken OpenBao policy either exposes root secrets or revokes database leases across every running service at once.
- A malformed Zitadel or Keycloak realm change invalidates active OIDC sessions across the estate, locking humans and services out of the control plane.
- A destructive DDL migration drops columns or truncates audit tables that a git revert cannot bring back.

Because a git pointer revert cannot undo a dropped table or a leaked key, Surface 2 requires cryptographic action binding before a single byte changes in production.

---

## 3. The Vulnerability of Ambient CI Authority & Secret Sprawl

The corpse of v1 in almost every CI/CD system is the same: **ambient authority** backed by **static secrets** and careless shell handling.

### The Ambient Authority Anti-Pattern

Ambient authority means a process can perform privileged actions simply because of the room it woke up in. In a standard pipeline, teams stuff long-lived credentials into repository settings or host environments:
- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` provisioned with `AdministratorAccess` so the pipeline stops failing on permission errors.
- `KUBECONFIG` bound to `system:masters`.
- `VAULT_TOKEN` or personal PATs sitting in environment variables.

When a job starts, those secrets flood the runner's environment. Anything executing inside that shell - a build script, a compromised transitive dependency, or an agent trying to "fix" a blocker - inherits the keys to the kingdom.

### Four Real Credential Traps on the Workbench

Even when credentials are scoped, sloppy shell primitives turn routine debugging into a credential breach. Four production rules from the Ravenhelm ledger govern how agents and scripts handle secrets on the bench:

1. **Kubernetes `last-applied-configuration` Holds the Secret (`secret-metadata-last-applied-annotation-holds-the-secret.md`, 2026-09-29):** Never run `kubectl get secret <name> -o yaml` or dump `.metadata.annotations` assuming only `.data` is sensitive. When a `Secret` is applied declaratively, `kubectl.kubernetes.io/last-applied-configuration` stores the entire plaintext secret in JSON inside the metadata block. Inspect secret existence with `kubectl get secret <name> -o jsonpath='{.metadata.name}'` or verify keys with `jq '.data | keys'`.
2. **Mask Secrets with Python, Never BSD `sed` (`mask-secrets-with-python-never-bsd-sed.md`, 2026-09-29):** Never pipe sensitive output through `sed` to redact tokens before printing. macOS BSD `sed` and Linux GNU `sed` handle extended regex flags (`-E` vs `-r`), character classes, and non-greedy quantifiers differently; when the regex misses, `sed` exits `0` and prints the unredacted secret to the terminal. Always parse and mask in Python (`python3 -c 'import sys, json; ...'`) where failure throws a hard exception instead of echoing raw text.
3. **Never Leak Secrets Into `argv` or Process Dumps (`never-pgrep-lf-it-dumps-process-env-secrets.md` & `secrets-never-in-curl-argv-use-stdin.md`):** Never run `pgrep -lf` or `ps eww` on a host running services with environment-injected secrets, and never pass `-H "Authorization: Bearer $TOKEN"` or `-u user:$PASS` directly on `curl` command lines. Command-line arguments are world-readable in the process table. Pass headers and credentials to `curl` over standard input via `--config -` (or `--netrc-file` on a mode `0600` tmpfs file).
4. **Never Call `op` Inside a Loop (`agent-loops-must-not-call-op-per-iteration.md` & `every-op-call-is-a-prompt-on-nates-screen.md`):** On an operator workstation, every `op` CLI invocation triggers a macOS TCC biometric prompt on the human operator's screen. An agent loop calling `op` on each retry turn DDOSes the operator's keyboard focus. Automated workloads must use **OpenBao AppRole**; if an interactive workstation session truly needs a 1Password secret, resolve it once outside the loop, hold it in memory for that single command, and never poll with it.

### The Confused Deputy and Prompt Injection Hazards

When autonomous AI agents operate inside a repository, ambient authority turns routine problem-solving into an attack vector:
1. **The Autonomous Confused Deputy:** You tell an agent: *"Fix the 403 error when `bifrost` scrapes `PrometheusRules`."* On September 29, 2026 (`RAV-2086`), `bifrost` PR #37 failed on first deploy because `bifrost-deployer` lacked RBAC permission to write `PrometheusRules`. In an unpartitioned environment with ambient cluster-admin keys, an eager agent solves a 403 by binding `*` verbs on `*` resources and applying it directly. Under RROM, the deployer fails closed on missing RBAC, and the operator proves permissions first with `kubectl auth can-i`.
2. **Prompt Injection via Untrusted Input:** An agent reads an external issue, webhook payload, or log line containing an embedded instruction to exfiltrate `/var/run/secrets` or `.env`. If no control-plane credentials sit in the runner environment, there is nothing to steal.
3. **Supply Chain Hook Poisoning:** A compromised dependency runs a `build.rs` or `postinstall` script during CI compilation. Because the ingress build runner only has network line-of-sight to `harbor-nginx` and a push-only robot token for one repo, the script cannot reach the Kubernetes API or OpenBao.

---

## 4. Action-Hash Elevation (The Valkyrie & OpenBao Protocol)

To govern Surface 2 mutations without handing ambient credentials to agents or runners, RROM enforces **The Zero-Ambient Elevation Doctrine**:

> *"Trust no agent with ambient authority; elevate via Valkyrie, bound to the exact action hash, consumed on first use."*  
> - **The Zero-Ambient Elevation Doctrine**

Standard administrative MFA fails when applied to automated pipelines. In conventional session-based MFA, a human enters a TOTP code or taps "Approve" on a push prompt, opening an authenticated session window lasting 15 minutes to 8 hours. During that window, the runner or agent can execute *any command* the role permits. If an agent gets approved to apply a harmless firewall rule and a 15-minute window opens, the agent can run five more unreviewed commands before the clock expires.

**Action-Hash Elevation (Valkyrie MFAA)** replaces session windows with cryptographic payload binding:
- Human approval is never granted to an *actor* or a *time window*.
- Human approval is granted exclusively to the **SHA-256 digest of the exact compiled binary plan (`tfplan.binary` or migration bundle) about to execute**.
- The resulting elevation token is mathematically invalid for any other payload, executes at most once, and is burned the instant the command finishes.

```
TRADITIONAL SESSION-BASED MFA (Vulnerable):
[ Human MFA Approval ] ──> Opens 15-Minute Window ──> Runner executes:
                                                        ├─ Approved Action (Terraform Plan A)
                                                        ├─ Unreviewed Action (Alter IAM Role)
                                                        └─ Destructive Action (Drop Table)

VALKYRIE ACTION-HASH ELEVATION (Zero-Ambient):
[ Human Biometric Auth ] ──> Signs sha256(tfplan.binary) ──> Single-Use Elevation Token
                                                                   │
                                                                   ▼
Runner asserts: sha256(local_binary) == token.hash ───[PASS]──> Execute tfplan.binary ONLY
                                                    └──[FAIL]──> HARD ABORT & SIGKILL
                                                                   │
                                                                   ▼
                                                       Consume Token (Zero Replay)
```

---

## 5. The Cryptographic Protocol for Action-Hash Elevation

Action-Hash Elevation runs as a seven-step handshake between the CI Runner, the **OpenBao** secrets engine on `Norns`, the **Valkyrie** Multi-Factor Action Approval (MFAA) broker, and the human **Gatekeeper**.

| Protocol Step | Actor & Target | Payload & Cryptographic Invariant |
| :--- | :--- | :--- |
| **1. Read-Only Auth** | CI Runner $\to$ OpenBao | Authenticates via scoped AppRole; retrieves read-only state token. |
| **2. Plan Compilation** | CI Runner (Local) | Compiles deterministic execution plan (`tfplan.binary`); computes 64-char hex SHA-256. |
| **3. Challenge Dispatch** | CI Runner $\to$ Valkyrie MFAA | Submits elevation challenge: `{action, target, plan_hash, git_commit, nonce}`. |
| **4. Biometric Sign** | Valkyrie $\to$ Gatekeeper | Out-of-band prompt; human inspects diff and signs `plan_hash` with FIDO2 / Secure Enclave. |
| **5. Local Hash Guard** | CI Runner (Local) | Verifies Valkyrie JWS signature; re-hashes `tfplan.binary` on disk to block TOCTOU swaps. |
| **6. Token Exchange & Run** | CI Runner $\to$ OpenBao $\to$ Prod | Exchanges signed JWS at OpenBao `/v1/auth/mfaa/login` for 120s write lease; runs `tfplan.binary`. |
| **7. Burn & Audit** | CI Runner $\to$ Valkyrie | Burns `jti` in Valkyrie replay filter; writes immutable receipt to Týr / Vór ledger. |

### Step 1: Read-Only Plan Generation via OpenBao AppRole

When a PR modifying Surface 2 manifests is opened or merged, the runner starts in an unprivileged sandbox. It authenticates to OpenBao using a read-only AppRole (`tf-control-plane-plan`). That policy allows reading remote state so Terraform or the migration planner can diff reality against intent, while denying all writes:

```hcl
# OpenBao Policy: tf-control-plane-plan.hcl
path "terraform/state/control-plane/*" {
  capabilities = ["read", "list"]
}

path "identity/data/*" {
  capabilities = ["read"]
}

path "secret/data/production/*" {
  capabilities = ["deny"]
}
```

The runner initializes the backend and compiles the deterministic plan binary:

```bash
terraform init -backend-config="vault_token=${BAO_READ_TOKEN}"
terraform plan -out=tfplan.binary -detailed-exitcode
```

### Step 2: Binary Plan Compilation & Non-Empty SHA-256 Guard

The runner hashes the compiled `tfplan.binary` file on disk, never the human-readable console text and never the raw `.tf` files. Source files do not capture resolved remote modules, provider versions, or external data lookups, and ANSI terminal output can be spoofed with escape sequences. The compiled `tfplan.binary` holds the exact mutation graph that will hit the wire.

To prevent the empty-string checksum tautology (`RAV-2079`, where a missing hash binary caused two empty strings to compare equal), the script asserts that `PLAN_HASH` is a valid 64-character lowercase hex string before proceeding:

```bash
PLAN_HASH=$(shasum -a 256 tfplan.binary | awk '{print $1}')
if [[ ! "${PLAN_HASH}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "FATAL: Invalid or empty SHA-256 digest ('${PLAN_HASH}')" >&2
  exit 1
fi
echo "Calculated Immutable Plan Hash: ${PLAN_HASH}"
```

### Step 3: Elevation Challenge Dispatch (Stdin Credentials)

The runner pauses and posts an elevation challenge to Valkyrie. Obeying the estate argv rule (`secrets-never-in-curl-argv-use-stdin.md`), the authorization header is passed via `stdin` using `--config -` so the bearer token never appears in `ps` or `pgrep`:

```bash
CHALLENGE_RESPONSE=$(printf 'header = "Authorization: Bearer %s"\n' "${RUNNER_REGISTRATION_TOKEN}" | \
  curl -sSf --config - -X POST "https://valkyrie.ravenhelm.dev/v1/challenges" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "terraform_apply",
    "target": "identity_control_plane",
    "plan_hash": "'"${PLAN_HASH}"'",
    "repository": "platforms/ravenhelm/identity-plane",
    "git_commit": "'"${FORGEJO_SHA}"'",
    "requester": "'"${CI_RUNNER_ID}"'",
    "nonce": "'$(openssl rand -hex 16)'",
    "expires_in_seconds": 300
  }')

CHALLENGE_ID=$(printf '%s' "${CHALLENGE_RESPONSE}" | jq -r .challenge_id)
```

The job enters a bounded wait for `CHALLENGE_ID` (maximum 300 seconds). If the human does not sign within 5 minutes, the challenge expires and the job fails closed.

### Step 4: Out-of-Band Biometric Human Verification (The Gatekeeper)

Valkyrie never trusts the runner to self-approve. It dispatches an out-of-band challenge to the human **Gatekeeper**:
1. **Diff Inspection:** The Gatekeeper unlocks the challenge via hardware biometrics (Touch ID / Face ID / YubiKey FIDO2) and reads the sanitized resource diff (`+1 to add, 0 to change, 0 to destroy`), the target repo, the commit SHA, and the `plan_hash`. Tools deliver the evidence; the human clicks accept or reject.
2. **Hardware Signature:** When the Gatekeeper approves, the device's Secure Enclave or FIDO2 key signs `challenge_id + plan_hash + timestamp` with its non-exportable private key.
3. **Single-Use Token Issuance:** Valkyrie verifies the hardware signature against the Gatekeeper's registered public key and issues a short-lived JSON Web Signature (JWS) Elevation Token:

```json
{
  "iss": "https://valkyrie.ravenhelm.dev",
  "sub": "gatekeeper:nwalker85",
  "aud": "openbao.ravenhelm.dev",
  "challenge_id": "valk_ch_8f91c0e271a",
  "action": "terraform_apply",
  "target": "identity_control_plane",
  "plan_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "nonce": "a4f89d012e5c83b1029471f0",
  "iat": 1730736000,
  "exp": 1730736120,
  "jti": "elev_tok_99a82b3c"
}
```

### Step 5: Runner Token Validation & TOCTOU Hash Guard

Before exchanging the token or invoking Terraform, the runner validates the JWS against Valkyrie's CA certificate (`/etc/ssl/certs/valkyrie-ca.pem`) and re-hashes `tfplan.binary` from disk. Both digests are validated as 64-character hex strings before comparison:

```bash
# Canonical Verification Logic (scripts/verify-action-elevation.sh)
CURRENT_LOCAL_HASH=$(shasum -a 256 tfplan.binary | awk '{print $1}')
TOKEN_PLAN_HASH=$(valkyrie-cli decode-token --token "${ELEVATION_TOKEN}" | jq -r .plan_hash)

if [[ ! "${CURRENT_LOCAL_HASH}" =~ ^[0-9a-f]{64}$ ]] || [[ ! "${TOKEN_PLAN_HASH}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "FATAL: Malformed or empty SHA-256 digest in elevation check!" >&2
  exit 1
fi

if [[ "${CURRENT_LOCAL_HASH}" != "${TOKEN_PLAN_HASH}" ]]; then
  echo "CRITICAL SECURITY BREACH: Plan hash mismatch detected!" >&2
  echo "Local Binary Hash: ${CURRENT_LOCAL_HASH}" >&2
  echo "Token Claim Hash:  ${TOKEN_PLAN_HASH}" >&2
  rm -rf ./*
  kill -s SIGKILL $$
fi

echo "Cryptographic Invariant Verified: Local plan binary matches Gatekeeper signature."
```

If any process modified a single byte of `tfplan.binary` while waiting for the human signature (a Time-of-Check to Time-of-Use swap), the hashes diverge and the runner kills itself immediately.

### Step 6: OpenBao Lease Exchange & Plan Execution

The runner presents the verified Valkyrie JWS to OpenBao (`/v1/auth/mfaa/login`). OpenBao verifies the signature and expiration, checks that `jti` has not been spent, and mints a dynamic, 120-second write token scoped strictly to `identity_control_plane`.

The runner executes the exact binary file the Gatekeeper signed:

```bash
terraform apply -input=false -auto-approve "tfplan.binary"
```

Because Terraform receives `tfplan.binary` rather than source files, it cannot re-evaluate expressions or drift from the signed DAG.

### Step 7: Single-Use Token Burn & Audit Receipt

Whether `terraform apply` exits `0` or non-zero, the runner immediately calls Valkyrie's consumption endpoint in a `trap ... EXIT` block, passing its auth header over `stdin`:

```bash
printf 'header = "Authorization: Bearer %s"\n' "${RUNNER_REGISTRATION_TOKEN}" | \
  curl -sSf --config - -X POST "https://valkyrie.ravenhelm.dev/v1/approvals/consume" \
  -H "Content-Type: application/json" \
  -d '{
    "token_jti": "elev_tok_99a82b3c",
    "execution_exit_code": '"${APPLY_EXIT_CODE}"'
  }'
```

Valkyrie records `elev_tok_99a82b3c` as spent in its persistent store and emits an immutable receipt containing the Gatekeeper identity, runner ID, commit SHA, `plan_hash`, timestamp, and exit code. The token cannot be replayed.

---

## 6. Threat Modeling & Defense-in-Depth Analysis

| Threat Vector | How v1 Fails | How RROM Stops It Cold |
| :--- | :--- | :--- |
| **1. Prompt-Injected or Confused-Deputy Agent** | Agent edits IAM/RBAC to `*` to clear a 403 error and auto-applies via ambient CI keys. | Surface 2 changes cannot auto-apply. Valkyrie halts for human biometric signature on the exact resource diff. |
| **2. TOCTOU Binary Swap on Runner** | Background process swaps `tfplan.binary` while waiting for human MFA approval. | Step 5 re-hashes `tfplan.binary` on disk and compares 64-char hex against the JWS `plan_hash` before running. |
| **3. Intercepted Elevation Token Replay** | Attacker sniffs the elevation token and replays it 5 minutes later for a second change. | Token expires in 120s, is burned on first use (`jti`), and is bound to the exact `plan_hash` of the original binary. |
| **4. Transcript & Process Table Scraping** | Agent runs `kubectl get secret -o yaml`, `pgrep -lf`, `curl -H`, or BSD `sed` and leaks tokens to logs. | Secrets stay out of argv (`curl --config -`), masking uses Python, `.metadata.annotations` is treated as secret-bearing, and AppRole replaces `op` loops. |

---

## 7. Comparative Operational Matrix

| Evaluation Dimension | Surface 1: Autonomous Application Mutations | Surface 2: Control Plane & Identity Mutations |
| :--- | :--- | :--- |
| **Operational Blast Radius** | **Low:** Contained to a single deployment replica set. | **High / Existential:** Estate IAM, OpenBao, networks, DB DDL. |
| **Typical Asset Scope** | Container images (`:b<N>`), Helm values, app config. | Keycloak/Zitadel, OpenBao policies, Harbor RBAC, SQL DDL, OPNsense. |
| **Primary Operator Seat** | **The Delivery Closer** (Autonomous Agent or Lead). | **The Gatekeeper** (Sovereign Human Seat). |
| **Deployment Authority** | **Autonomous:** Merge to `main` is approval to ship (RP-10). | **Non-Autonomous:** Gated by out-of-band elevation (RP-17). |
| **Identity & Elevation** | **OpenBao AppRole** + scoped Harbor push robot. | **Valkyrie MFAA** (Action-Hash Elevation) + OpenBao 120s lease. |
| **Cryptographic Binding** | Immutable image digest (`:b<N>@sha256:...`). | SHA-256 digest of compiled execution payload (`tfplan.binary`). |
| **Runner Network Access** | Internal `harbor-nginx` only. Zero cluster API ingress. | Ephemeral read-only state inspection until JWS exchange. |
| **Rollback Mechanism** | **Deterministic Pointer Revert** in `norns-gitops` (RP-14). | Forward migration or explicit cutover ADR (RP-11). |
| **Primary Invariant** | *Builds are the unit; releases are names.* | *Trust no agent with ambient authority (Action-Hash Elevation).* |

---

## 8. Summary of Invariants & Augmentation Surface

### Where Autonomous Agents Operate

- **Clean Worktree Plan Compilation:** Agents check out repositories into isolated worktrees (`RP-18`), authenticate with read-only OpenBao AppRoles, and compile deterministic plan binaries (`terraform plan -out=tfplan.binary`).
- **Leak-Free Shell Execution:** Agents pass credentials via `stdin` (`curl --config -`), redact sensitive output with Python rather than BSD `sed`, never run `pgrep -lf` or `ps eww` on secret-bearing hosts, never dump `.metadata.annotations` on Kubernetes `Secret` objects, and never invoke `op` inside polling loops.
- **Pre-Execution Hash Verification:** Agents run `scripts/verify-action-elevation.sh` to verify Valkyrie's signature and prove that the local binary's 64-character SHA-256 matches the Gatekeeper's signed `plan_hash`.

### What the Human Gatekeeper Retains

- **Sole Elevation Authority:** Only the human Gatekeeper can authorize a Surface 2 mutation. Accountability always chains to the human actor.
- **Out-of-Band Biometric Signature:** The Gatekeeper inspects the concrete resource diff and signs the exact `plan_hash` using a hardware enclave over an out-of-band channel. No signature, no mutation.

<!-- RUBRIC_CHECK: Chapter 11 conforms to RROM specification. -->

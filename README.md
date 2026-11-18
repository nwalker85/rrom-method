# Ravenhelm Release Operations Methodology (RROM)

> **Book III of the Ravenhelm Operations Methodology** (*The Sovereign Engineering Trilogy: RLOM · RDOM · RROM*) - A tiered, sovereign operating methodology for software release, artifact custody, and multi-surface deployment; installable in days, scalable across platforms, and grounded in eighteen numbered principles.

Authored by **[Nathan Walker](https://nwalker.cc)** · Published by **[Ravenhelm LLC](https://ravenhelm.co)**  
Current Release: **v1.0.0** · [PDF (Dark Edition)](RROM-v1.0.0-dark.pdf) · [PDF (Print Edition)](RROM-v1.0.0.pdf) · [Changelog](CHANGELOG.md) · [Start Reading ->](docs/chapters/01-what-this-is.md)

---

## What Problem This Solves

On 2026-09-16 and 2026-09-17, an estate-wide audit exposed a pattern of systems that measured presence, printed green, and failed in silence: `.forgejo/workflows/deploy.yml` never fired on 1 of 24 pushes to `main`; `failedJobsHistoryLimit: 0` deleted crashed backup pods before anyone could read why they died; `freyr-api` tracked a mutable `:latest` tag that auto-rolled production without a digest pin; and 287,838 of 287,879 Alertmanager webhooks failed across four weeks behind a stale single-file Docker bind mount.

You pushed a git tag this morning. A CI runner triggered, checked out the tagged commit, re-compiled the source code, built a container image, and pushed it to production. What ran in production was **not** what you tested in staging. It was built thirty minutes later, resolved different transient dependencies, pulled different base container layers, and carried an unrecorded digest. Meanwhile:

- Your local CLI developer tools fell out of lockstep with the backend cluster API because no synchronized dual-surface release rail existed (or `doom update` shimmed `~/.local/bin/doom` ahead of Homebrew at `PATH` index 5 vs 9 while `--version` lied).
- A routine deploy silently swapped the datastore or message transport because the team confused an **architectural cutover** with a **code deployment** (`ADR-011`).
- An ambient CI secret pushed code directly to `main` or leaked a robot token into `kubectl.kubernetes.io/last-applied-configuration`, bypassing peer review and least-privilege custody.
- When an incident hit, "rollback" meant frantically compiling an older commit rather than repointing an immutable pointer to a known-good build digest in seconds.

The **Ravenhelm Release Operations Methodology (RROM)** is the third *dōmbōc* ("what is laid down; the judgment") of the **Ravenhelm Operations Methodology**, closing the loop from **RLOM** (Intent) and **RDOM** (Execution) to verified production custody:

```text
                  THE RAVENHELM OPERATIONS METHODOLOGY
             (The Sovereign Engineering Trilogy: RLOM · RDOM · RROM)

   ┌────────────────────────────────────────────────────────────────────────┐
   │ Book I: RLOM - Ravenhelm Linear Operating Method (The Work Graph)      │
   │    Governs: The Work Graph, Demand Intake, Validation Gates, Reporting │
   │    Axiom: "Merged != Built != Running; evidence beats assertion."      │
   │    Status: v1.0.3 · 29 Principles (P-1..P-29)                          │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       │
                                       ▼ (Issues dispatched to engineering)
   ┌────────────────────────────────────────────────────────────────────────┐
   │ Book II: RDOM - Ravenhelm Development Operations Methodology           │
   │    Governs: Topological Waves, Concurrency, Agent Slices, TDD, EAT     │
   │    Axiom: "Wave N+1 never opens on a promise; only on verified green." │
   │    Status: v1.0.0 · 24 Principles (DP-1..DP-24)                        │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       │
                                       ▼ (Merged code ready for compilation)
   ┌────────────────────────────────────────────────────────────────────────┐
   │ Book III: RROM - Ravenhelm Release Operations Methodology              │
   │    Governs: Build Once, Artifact Custody, Multi-Surface Rails, GitOps  │
   │    Axiom: "Builds are the unit; releases are names." (ADR-0007)        │
   │    Foundation: Harbor OCI Digests, Three Physical Rails, Valkyrie MFAA │
   │    Status: v1.0.0 · 18 Principles (RP-1..RP-18)                        │
   └────────────────────────────────────────────────────────────────────────┘
```

---

## The Core Axiom

> ### **Builds are the unit; releases are names.**
>
> *A build is an immutable artifact produced once on merge to `main`. A release is an authorized name assigned to an existing build. A deployment is the declarative reconciliation of a target environment to that named artifact.*
>
> **Releases never rebuild code.**

```
[ Merge to main ] ──> [ CI: Build Once ] ──> [ Immutable Registry: :b<N> @ sha256:... ]
                                                              │
                                      ┌───────────────────────┴───────────────────────┐
                                      ▼                                               ▼
                         [ Rail A: Server GitOps ]                       [ Rail B: Workstation Tap ]
                         Argo CD pulls pinned digest                     Dynamic formula inreplace
```

---

## The 18 Numbered Principles

RROM is governed by eighteen inviolable principles across four categories:

| ID | Principle | Core Rule |
|---|---|---|
| **RP-1** | **Build Once on Ingress** | Compilation occurs once on merge to `main`, producing an immutable artifact identified by `:b<N>` and a cryptographic digest. |
| **RP-2** | **Releases Never Rebuild** | The release lifecycle assigns a SemVer tag to an existing build. It never invokes a compiler, bundler, or docker build. |
| **RP-3** | **Promotion by Reference** | Promoting across environments is strictly an act of updating declarative pointer manifests to an immutable digest. |
| **RP-4** | **Tags for Humans, Digests for Runtime** | Runtime manifests pin `repository:tag@sha256:<digest>`. The tag is for human UX; the digest is kernel truth. |
| **RP-5** | **Parity Precedes Promotion** | A release candidate must prove zero source code drift against the parent build commit (`check-release-source-parity.sh`). |
| **RP-6** | **Multi-Surface Lockstep** | Repositories serving multiple surfaces (Server + CLI) must execute all applicable rails within the same release cycle. |
| **RP-7** | **Sandboxed Inreplace** | Workstation package formulae (e.g. Homebrew) dynamically inreplace version strings in a sandbox to preserve zero-drift git history. |
| **RP-8** | **Sovereign Binary Distribution** | Desktop applications distribute via signed binary archives with Minisign Ed25519 signatures and machine-readable `latest.json` manifests. |
| **RP-9** | **Declarative Convergence Authority** | Servers do not accept push deployments. An automated orchestrator (Argo CD / Launchd) is the sole applying authority. |
| **RP-10** | **Merge-Then-Deploy** | Approval to merge an approved release PR is approval to ship. Once merged, the release pipeline executes to live verification. |
| **RP-11** | **Cutovers Require ADRs** | A deploy reconciles code. A **cutover** changes the serving architecture. Cutovers require an ADR, migration plan, and elevated approval. |
| **RP-12** | **Zero Ambient CI Authority** | CI runners do not hold cluster-admin tokens. Operations use least-privilege AppRoles and Action-Hash Elevation (Valkyrie MFAA). |
| **RP-13** | **Shell Success Is Not Proof** | A pipeline exiting `0` is unverified. Deployment is proven only when the running system satisfies live network health probes and caller parity. |
| **RP-14** | **Fail-Closed Rollback** | Rollback is instantaneous pointer repointing to the preceding immutable build digest in gitops. |
| **RP-15** | **Strict SemVer Contract** | Breaking an existing API schema, authz tuple, or sentence address requires a MAJOR version bump. |
| **RP-16** | **Immutable Audit Ledgers** | Every promotion is recorded in a tamper-evident audit ledger binding git commit, build ID, digest, and signer identity. |
| **RP-17** | **Separation of Blast Radii** | Application deploys are autonomous; identity-plane mutations (Keycloak/OpenBao) require Action-Hash Elevation (Valkyrie MFAA). |
| **RP-18** | **Clean Worktree Custody** | Release operations execute from dedicated, disposable git worktrees with strict history custody. Never rely on git stash. |

---

## The Three Release Rails

RROM provides concrete, production-tested delivery rails across three computing surfaces:

1. **Rail A: Server & Kubernetes Cluster GitOps (Reference: Vitki)**  
   *Packaging:* Harbor OCI container image + Helm chart  
   *Authority:* Argo CD pull reconciliation (`norns-gitops`)  
   *Mechanism:* Moving `:uat` tag for staging, pinned `@sha256:` digest for production.

2. **Rail B: Developer Workstation CLI/TUI (Reference: Ullr / Yager)**  
   *Packaging:* Private Homebrew Tap (`nate/tools`)  
   *Authority:* Homebrew package manager (`brew upgrade`)  
   *Mechanism:* Sandboxed formula `inreplace` of version manifests during compilation, preserving source git parity.

3. **Rail C: Client Desktop Application OTA (Reference: Idunn)**  
   *Packaging:* Compressed application bundles (`.app.tar.gz`)  
   *Authority:* In-app background update engine  
   *Mechanism:* Minisign Ed25519 signature verification against Forgejo/GitHub releases and `latest.json` update manifests.

---

## Start Reading

The publication is structured into **14 chapters plus two technical appendices** (`55,205` words, 291 pages in publication digest trim):

| # | Chapter | Key Focus | Words |
|---|---|---|---|
| 01 | [What This Is and Who It's For](docs/chapters/01-what-this-is.md) | The gap between presence and absence, silent pipeline lies, and the multi-surface contract | 3,203 |
| 02 | [The Core Axiom](docs/chapters/02-the-core-axiom.md) | Builds are the unit; releases are names (ADR-0007 and the Vitki reference) | 3,006 |
| 03 | [The Numbered Principles](docs/chapters/03-numbered-principles.md) | Canonical principles (`RP-1`..`RP-18`) with bench physics, v1 corpses, and mechanical gates | 5,539 |
| 04 | [The Operator Roles](docs/chapters/04-the-operator-roles.md) | Human accountability (`dr-8`), service credentials (`frs #88`), Author, Custodian, Closer, Gatekeeper | 3,565 |
| 05 | [The Artifact Surface](docs/chapters/05-the-artifact-surface.md) | Monotonic `:b<N>` digests, the Harbor HTTP 200 token trap, and Registry v2 retagging | 3,316 |
| 06 | [The Three Physical Rails](docs/chapters/06-the-three-physical-rails.md) | Rail A (Norns K3s GitOps), Rail B (Homebrew Tap), Rail C (Idunn Minisign OTA), and the `openrsync` trap | 3,815 |
| 07 | [Workflow Canon & Validation Gate](docs/chapters/07-workflow-canon-and-validation-gate.md) | The Ten Ghosts (`0` callers), the DIS 1.8 fiction release, source parity, and changelog-to-tree verification | 3,509 |
| 08 | [The Tiered Adoption Ladder](docs/chapters/08-tiered-adoption-ladder.md) | Tier 1 (Solo Workstation) to Tier 4 (Sovereign Cluster with Action-Hash Elevation / Valkyrie MFAA) | 4,784 |
| 09 | [Cutovers vs. Deployments](docs/chapters/09-cutovers-vs-deployments.md) | Codifying ADR-011: the Bifrost cutover incident, SQL migration tracking, and RBAC dry-runs | 3,733 |
| 10 | [Hotfixes, Emergencies & Rollback](docs/chapters/10-hotfixes-emergencies-and-rollback.md) | Stale inode bind mounts (287,838 dead webhooks), Flannel subnet drops, and 60-second digest rollback | 2,779 |
| 11 | [Security Blast Radius & Elevation](docs/chapters/11-security-blast-radius-and-elevation.md) | App deploys vs. identity-plane mutations with Action-Hash Elevation (Valkyrie MFAA & OpenBao) | 4,005 |
| 12 | [Code Host & Registry Integration](docs/chapters/12-code-host-and-registry-integration.md) | Two `runs-on: docker` pools, reading missing CI logs from `dbfs`, and `build.yml` / `release.yml` | 3,187 |
| 13 | [Auditing, Provenance & Compliance](docs/chapters/13-auditing-provenance-and-compliance.md) | Killing the three backup lies, empty-string checksum traps, SLSA-3 provenance, and cluster audits | 2,639 |
| 14 | [The Release Maturity Assessment](docs/chapters/14-the-assessment.md) | Auditing presence vs. absence across the 100-point rubric and commercial advisory engagements | 3,050 |
| App. A | [Formula Inreplace Playbook](docs/chapters/appendix-a-formula-inreplace-playbook.md) | Sandboxed inreplace patterns for Rust (`Ullr`/`Yager`), Go, Node.js, and Python tool distribution | 1,796 |
| App. B | [The Vitki Reference Specification](docs/chapters/appendix-b-vitki-reference-specification.md) | Complete ADR-0007 production blueprint: Helm templates, helper scripts, CI workflows, and GitOps manifests | 3,279 |

---

## Publications & Artifacts

The manuscript is typeset using **Typst** in two publication-grade editions conforming to Ravenhelm's high-contrast brand standards (Source Serif 4 + IBM Plex Mono):

- **[Download PDF (Dark Edition)](RROM-v1.0.0-dark.pdf)** - Obsidian background (`#0B0C0E`), Bone ink (`#EDE8DC`), Garnet accents (`#A3222F`), vector diagrams.
- **[Download PDF (Print Edition)](RROM-v1.0.0.pdf)** - Bone paper (`#EDE8DC`), Obsidian ink (`#0B0C0E`), designed for formal print and digest reading.

To recompile the publication PDFs locally:

```bash
python3 scripts/build-pdf.py
```

---

## License & Commercial Inquiries

RROM is published under the **RROM Community License 1.0**. It is free for internal evaluation and adoption within your team or organization. Commercial training, third-party certification, and client advisory rights are reserved by **Ravenhelm LLC**.

For enterprise advisory, release pipeline audits, or multi-surface architecture engagements, contact:

**Nathan Walker** · **Ravenhelm LLC**  
Email: [nate@ravenhelm.co](mailto:nate@ravenhelm.co) · Web: [https://ravenhelm.co](https://ravenhelm.co)

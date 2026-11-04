# Chapter 14: The Release Maturity Assessment

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Assessing Your Release Debt

Before an organization can adopt RROM, it must honestly diagnose its current operational maturity. Most engineering teams believe they have "modern CI/CD" because they use GitHub Actions or GitLab pipelines. In reality, they suffer from deep release debt.

Use this 10-point assessment rubric to grade your organization's release posture.

---

## The 10-Point RROM Diagnostic Rubric

| # | Diagnostic Question | Points (0 - 2) |
|---|---|---|
| 1 | **Build Once:** Does your release pipeline promote existing, pre-tested image digests, or does it trigger a compiler/rebuild at tag time? *(2 = Promotes existing; 0 = Rebuilds at tag)* | ___ / 2 |
| 2 | **Digest Pinning:** Do your Kubernetes manifests or Compose files pin full `@sha256:` digests, or do they reference mutable tags? *(2 = Mandatory digests; 0 = Mutable tags)* | ___ / 2 |
| 3 | **Staging Parity:** Is the artifact running in staging byte-identical to the artifact promoted to production? *(2 = Byte-identical; 0 = Recompiled separately)* | ___ / 2 |
| 4 | **Workstation Lockstep:** Are developer CLIs and admin TUIs released in lockstep with backend APIs using sandboxed formula versioning? *(2 = Synchronized lockstep; 0 = Uncoordinated)* | ___ / 2 |
| 5 | **Declarative Authority:** Is an automated orchestrator (Argo CD) the sole applying authority, with zero laptop deploy access? *(2 = Strict GitOps; 0 = Manual laptop applies)* | ___ / 2 |
| 6 | **Zero Ambient Secrets:** Are CI runners restricted from holding permanent root or cluster-admin credentials? *(2 = Scoped AppRoles; 0 = Long-lived root secrets)* | ___ / 2 |
| 7 | **Cutover Governance:** Does your team enforce ADR-011 (formal ADRs and migration runbooks for architectural swaps)? *(2 = Strict cutover gates; 0 = Informal swaps)* | ___ / 2 |
| 8 | **Source Parity Gate:** Do automated scripts reject release PRs that contain unauthorized application source code modifications? *(2 = Automated parity checks; 0 = Unchecked PRs)* | ___ / 2 |
| 9 | **Instant Rollback:** Can your team rollback a failed production release in under 60 seconds without compiling or pushing code? *(2 = Pointer repoint < 60s; 0 = Recompiling rollback)* | ___ / 2 |
| 10 | **Audit Ledger:** Can you prove the exact git commit, build ID, and signer identity of the container currently running on port 443? *(2 = Cryptographic link; 0 = Guesswork)* | ___ / 2 |

---

## Scoring & Maturity Interpretation

- **0 – 8 Points (Fragile Delivery):** Your team is at extreme risk of production deployment outages, dependency drift, and supply chain tampering. Adopting **Tier 1 (Artifact Discipline)** and eliminating tag-time rebuilds should be an immediate priority.
- **10 – 14 Points (Emerging Discipline):** You have basic container discipline, but suffer from surface drift between backend APIs and developer CLIs, or allow ambient secrets in CI pipelines. Adopt **Tier 2 and Tier 3 (Multi-Rail GitOps)**.
- **16 – 20 Points (Sovereign Operations):** Your organization operates at the highest echelon of release engineering. Your releases are immutable, verified, multi-surface, and auditable.

---

## Commercial Implementation & Advisory

Installing RROM within an existing enterprise requires careful navigation of legacy pipelines, developer habits, and compliance boundaries.

**Ravenhelm LLC** provides specialized executive advisory, pipeline refactoring, and multi-surface release architecture services:
- **3-Day Release Pipeline Assessment:** Comprehensive audit of your repository workflows, registry topology, and cluster security boundaries.
- **RROM Implementation Engagements:** Turnkey installation of the Build-Once rail, Argo CD GitOps integration, and private Homebrew formula automation.
- **Valkyrie Sovereign Elevation Architecture:** Designing zero-trust action-hash elevation systems for high-consequence infrastructure.

For engagement inquiries, contact:

**Nathan Walker**  
Founder & Principal, Ravenhelm LLC  
Email: [nate@ravenhelm.co](mailto:nate@ravenhelm.co)  
Web: [https://ravenhelm.co](https://ravenhelm.co)

<!-- RUBRIC_CHECK: Chapter 14 conforms to RROM specification. -->

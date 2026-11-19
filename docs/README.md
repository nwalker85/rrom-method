# Documentation

The full **Ravenhelm Release Operations Methodology (RROM)** - **Book III of the Ravenhelm Operations Methodology** (*The Sovereign Engineering Trilogy: RLOM · RDOM · RROM*) - lives here.

## Layout

```text
docs/
├── chapters/         # 14 chapters + 2 technical appendices
└── _shared/          # Authoring spec - load-bearing for any editorial work
    └── CONTEXT.md    # Voice, style mechanics, rubric, chapter ordering
```

## Chapter Index

Read in order on first pass. Cross-references between chapters use the canonical ordering below.

1. [What This Is and Who It's For](chapters/01-what-this-is.md)
2. [The Core Axiom: Builds Are the Unit; Releases Are Names](chapters/02-the-core-axiom.md)
3. [The Numbered Principles](chapters/03-numbered-principles.md)
4. [The Operator Roles](chapters/04-the-operator-roles.md)
5. [The Artifact Surface](chapters/05-the-artifact-surface.md)
6. [The Three Physical Rails](chapters/06-the-three-physical-rails.md)
7. [Workflow Canon & Validation Gate: The Release State Machine](chapters/07-workflow-canon-and-validation-gate.md)
8. [The Tiered Adoption Ladder](chapters/08-tiered-adoption-ladder.md)
9. [Cutovers vs. Deployments](chapters/09-cutovers-vs-deployments.md)
10. [Hotfixes, Emergencies & Rollback](chapters/10-hotfixes-emergencies-and-rollback.md)
11. [Security Blast Radius & Elevation](chapters/11-security-blast-radius-and-elevation.md)
12. [Code Host & Registry Integration](chapters/12-code-host-and-registry-integration.md)
13. [Auditing, Provenance & Compliance: Cryptographic Custody and Provenance](chapters/13-auditing-provenance-and-compliance.md)
14. [The Release Maturity Assessment: Assessing Your Release Debt](chapters/14-the-assessment.md)

**Appendix A.** [Formula Inreplace Playbook](chapters/appendix-a-formula-inreplace-playbook.md) - sandboxed formula inreplace patterns for Rust, Go, Node.js, and Python workstation tool distribution.

**Appendix B.** [The Vitki Reference Specification](chapters/appendix-b-vitki-reference-specification.md) - complete end-to-end production reference specification of ADR-0007 across Helm charts, Registry v2 helpers, CI workflows, and `norns-gitops`.

## Reading Paths

- **Release Operator & Delivery Closer:** 01 -> 02 -> 04 -> 06 -> 07 -> 10.
- **Artifact Custodian:** 02 -> 05 -> 06 -> 12 -> 13 -> Appendix A.
- **Platform & Infrastructure Engineer:** 05 -> 06 -> 09 -> 11 -> 12 -> Appendix B.
- **Security & Compliance Auditor:** 04 -> 07 -> 11 -> 13 -> 14.

## Authoring Spec

[`_shared/CONTEXT.md`](_shared/CONTEXT.md) is the load-bearing spec for editorial work: voice rules, terminology boundaries, license header, and the rubric every chapter must pass. Read it before opening any chapter PR.

# Authoring Context & Style Guide - RROM

This specification defines the voice, conventions, and quality criteria for all chapters of the **Ravenhelm Release Operations Methodology (RROM)**, **Book III of the Ravenhelm Operations Methodology** (*The Sovereign Engineering Trilogy: RLOM · RDOM · RROM*).

---

## 1. Voice, Posture, and Mechanics

Every chapter follows the unified Ravenhelm style register (`STYLE-GUIDE.md`):

- **Zero prose em-dashes.** Replace every prose em-dash with `;` (when joining two weighted clauses) or ` - ` (spaced hyphen for parentheticals/asides).
- **Start at the crime scene on the bench, never in the lecture hall.** Kill throat-clearing openers (*"In modern software engineering..."*, *"For decades, organizations have..."*). Open with the broken artifact on the workbench, the exact date, the exact metric, the command that lied, or the production scar.
- **Show the corpse of v1 ("the wrong one we built first").** Never present a principle as if it fell from the sky whole. Show the naive v1 built first, the failure mode that killed it under load, and the physical constraint that forced the real design.
- **High-low collision (cathedral math + shop-floor nouns).** Collide exact technical primitives (`@sha256:`, `concurrencyPolicy: Forbid`, `Docker-Content-Digest`, `inreplace`, `Minisign Ed25519`) with blunt physical nouns (`corpse`, `hinge`, `wreckage`, `receipt`, `anvil`, `blindfold`).
- **Bench imperatives over brochure descriptions.** Write second-person shop-floor recipes and direct cause-and-effect, never third-person brochure prose.
- **Rhythm: long-build verse -> short-knife breakdown.** Accumulate evidence in multi-clause paragraphs, then land the verdict in a knife sentence of 5 words or fewer inside the paragraph.
- **Repetition must carry a receipt.** Never repeat a phrase for rhetorical rhythm alone; the second occurrence must escalate the paperwork.
- **Exact numbers always.** Cite exact ledger figures (`287,838 of 287,879 webhooks`, `1 of 24 pushes to main`, `47 minutes`, `73 passing tests and zero callers`), never vague approximations.
- **Terminology boundaries.** Personal codex / myth terms never leak into ops docs. Use **Action-Hash Elevation (Valkyrie MFAA)** and **The Zero-Ambient Elevation Doctrine** for cryptographic hardware-key elevation on control-plane and identity-plane mutations. Real running estate systems (`Bifrost`, `Heimdall`, `Vitki`, `Ullr`/`Yager`, `Idunn`, `Doom`/`Doomcourt`, `EAT`, `Snotra`, `Harbor`, `OpenBao`, `Valkyrie`, `Norns`) are valid architectural receipts when introduced with their functional role.

---

## 2. Structure of Each Chapter

Each chapter markdown file in `docs/chapters/` follows this structure:

1. **License Header Block**:

   ```markdown
   <!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->
   ```

2. **Opening Crime Scene**: The concrete release, deployment, or custody failure mode on the bench that occurs when this discipline is missing, including the corpse of v1.
3. **The Mechanical & Cryptographic Foundation**: Formal mechanics, state invariants, and architectural diagrams.
4. **Operational Mechanics & Step-by-Step Protocols**: Concrete implementation recipes, shell guards, Helm/GitOps manifests, Registry v2 API transactions, and tabular rules.
5. **Concrete Anti-Patterns & Defect Escapes**: How release pipelines and agent fleets fail in practice.
6. **Augmentation Surface Callout & `<!-- RUBRIC_CHECK -->` Block**: Validating chapter completeness, word count, and principle citations (`RP-1`..`RP-18`).

---

## 3. Canonical 16-Unit Ordering (14 Chapters + 2 Appendices)

1. **Chapter 01**: What This Is and Who It's For (`01-what-this-is.md`)
2. **Chapter 02**: The Core Axiom: Builds Are the Unit; Releases Are Names (`02-the-core-axiom.md`)
3. **Chapter 03**: The Numbered Principles (`03-numbered-principles.md`)
4. **Chapter 04**: The Operator Roles (`04-the-operator-roles.md`)
5. **Chapter 05**: The Artifact Surface (`05-the-artifact-surface.md`)
6. **Chapter 06**: The Three Physical Rails (`06-the-three-physical-rails.md`)
7. **Chapter 07**: Workflow Canon & Validation Gate: The Release State Machine (`07-workflow-canon-and-validation-gate.md`)
8. **Chapter 08**: The Tiered Adoption Ladder (`08-tiered-adoption-ladder.md`)
9. **Chapter 09**: Cutovers vs. Deployments (`09-cutovers-vs-deployments.md`)
10. **Chapter 10**: Hotfixes, Emergencies & Rollback (`10-hotfixes-emergencies-and-rollback.md`)
11. **Chapter 11**: Security Blast Radius & Elevation (`11-security-blast-radius-and-elevation.md`)
12. **Chapter 12**: Code Host & Registry Integration (`12-code-host-and-registry-integration.md`)
13. **Chapter 13**: Auditing, Provenance & Compliance: Cryptographic Custody and Provenance (`13-auditing-provenance-and-compliance.md`)
14. **Chapter 14**: The Release Maturity Assessment: Assessing Your Release Debt (`14-the-assessment.md`)
15. **Appendix A**: Formula Inreplace Playbook (`appendix-a-formula-inreplace-playbook.md`)
16. **Appendix B**: The Vitki Reference Specification (`appendix-b-vitki-reference-specification.md`)

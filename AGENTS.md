# Agent Guide - rrom-method

This file is authoritative for the `rrom-method` repository, **Book III of the Ravenhelm Operations Methodology** (*The Sovereign Engineering Trilogy: RLOM · RDOM · RROM*). Update it when repository authority, CI, release surfaces, or doctrine boundaries change.

## Source of Truth

- Canonical repository: `https://github.com/nwalker85/rrom-method` (public publication candidate).
- Human documentation: `README.md`, `docs/README.md`, `docs/_shared/CONTEXT.md`, and `docs/chapters/`.
- Project work: GitHub Issues, Pull Requests, and Discussions.
- Author: Nathan Walker (`https://nwalker.cc`) / Ravenhelm LLC (`https://ravenhelm.co`).

## Repository Posture

- Always work from a dedicated git worktree when editing this repo. Checkouts obey the Checkout Custody Standard.
- Never push directly to `main`. Every change lands via a Pull Request.
- Merging a PR requires Nate's explicit approval for that specific PR.
- Conventional Commits (`feat(chapter)`, `fix(chapter)`, `feat(doctrine)`, `chore(repo)`, `docs(meta)`).
- CI runs automated markdownlint and chapter rubric/license header checks on every pull request and push to `main`.

## Authority and Editorial Doctrine

- The manuscript is authoritative. Substantive prose is authored material by Nathan Walker.
- Every chapter obeys the voice and mechanical rules in `STYLE-GUIDE.md` and `docs/_shared/CONTEXT.md`: zero prose em-dashes (use `;` or ` - `), crime-scene openers on the workbench, showing the corpse of v1, high-low collision (cathedral math + shop-floor nouns), bench imperatives, and exact numbers from the ledger.
- Agents may fix objective publication defects (broken links, malformed markdown, anchor mismatches, inconsistent paths, deterministic metadata errors).
- Agents may NOT silently rewrite paragraphs, change arguments, alter doctrine/principles, invent evidence, or change chapter structure without explicit instruction.
- Any change to the 18 numbered principles (`RP-1`..`RP-18`) requires an Architecture Decision Record (ADR) in `docs/architecture/decisions/`.
- Every chapter conforms to the authoring specification in `docs/_shared/CONTEXT.md` and ends with a `RUBRIC_CHECK` comment block.

## Terminology and Data Boundaries

- No secrets, API keys, credentials, or private keys.
- No private customer names or confidential employer data.
- **Zero Myth / Codex vocabulary leakage:** Personal codex terms never appear in operations methodology text.
- **Action-Hash Elevation (Valkyrie MFAA):** Control-plane and identity-plane mutations are governed by **Action-Hash Elevation (Valkyrie MFAA)** and **The Zero-Ambient Elevation Doctrine** (`VALKYRIE ELEVATION GATE`).
- Real running Ravenhelm estate systems (`Bifrost`, `Heimdall`, `Vitki`, `Ullr`/`Yager`, `Idunn`, `Doom`/`Doomcourt`, `EAT`, `Snotra`, `Harbor`, `OpenBao`, `Valkyrie`, `Norns`) are valid architectural receipts when grounded with their functional role and concrete failure/verification history.

## Validation & Build

```bash
# Compile single-file Markdown edition
./scripts/compile.sh > build/rrom.md

# Build publication PDFs (Dark mode and Print mode) via Typst
python3 scripts/build-pdf.py
```

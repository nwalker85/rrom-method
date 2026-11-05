#!/usr/bin/env python3
"""Typeset Ravenhelm Release Operations Methodology (RROM) as a publication-grade PDF using Typst.

Compiles two editions:
  dark   — bone on obsidian (screen edition, matching 'Memory, Walking — v3 (dark).pdf' and RLOM Dark)
  print  — obsidian on bone paper (the print / digest edition)

Faces: Source Serif 4 (proposition/body), IBM Plex Mono (evidence/folios/code/colophon).
Trim: 5.5 x 8.5 in (digest chapbook / executive monograph).
"""
import os
import re
import sys
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(ROOT, "docs", "chapters")
DIAGRAMS_DIR = os.path.join(ROOT, "diagrams")
ASSETS_DIR = os.path.join(ROOT, "assets")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
OUTDIR = ROOT

BYLINE = "Nathan Walker"
IMPRINT = "Ravenhelm Publishing Series LLC"
COPYRIGHT = "© 2026 Ravenhelm LLC. All rights reserved."

CHAPTER_FILES = [
    ("01-what-this-is.md", "01", "What This Is and Who It's For", None),
    ("02-the-core-axiom.md", "02", "The Core Axiom: Builds Are the Unit; Releases Are Names", "diagram1-core-axiom"),
    ("03-numbered-principles.md", "03", "The Numbered Principles", None),
    ("04-the-operator-roles.md", "04", "The Operator Roles", None),
    ("05-the-artifact-surface.md", "05", "The Artifact Surface: Immutability and Registry Topology", None),
    ("06-the-three-physical-rails.md", "06", "The Three Physical Rails: GitOps, Tap, and OTA", "diagram2-three-rails"),
    ("07-workflow-canon-and-validation-gate.md", "07", "Workflow Canon and the Source Parity Rule", "diagram3-parity-triangle"),
    ("08-tiered-adoption-ladder.md", "08", "The Tiered Adoption Ladder", None),
    ("09-cutovers-vs-deployments.md", "09", "Cutovers vs. Deployments: The Architectural Shift Doctrine", None),
    ("10-hotfixes-emergencies-and-rollback.md", "10", "Hotfixes, Emergencies, and the Rollback Illusion", None),
    ("11-security-blast-radius-and-elevation.md", "11", "Security, Blast Radius, and Elevation Gates", "diagram4-blast-radius"),
    ("12-code-host-and-registry-integration.md", "12", "Code Host and Registry Integration", None),
    ("13-auditing-provenance-and-compliance.md", "13", "Auditing, Provenance, and Continuous Verification", None),
    ("14-the-assessment.md", "14", "The Release Operations Assessment", None),
    ("appendix-a-formula-inreplace-playbook.md", "A", "Formula Inreplace Playbook (Rail B)", None),
    ("appendix-b-vitki-reference-specification.md", "B", "Vitki Controller Reference Specification", None),
]

def markdown_to_typst_via_pandoc(md_path, edition):
    """Converts a Markdown file to Typst syntax via pandoc with post-processing."""
    raw_md = open(md_path, "r", encoding="utf-8").read()
    
    # Strip HTML license comments and rubric checks
    cleaned_md = re.sub(r"<!--.*?-->", "", raw_md, flags=re.S)
    
    # Strip the H1/H2 top-level chapter heading since Typst renders custom chapter opener
    cleaned_md = re.sub(r"^#\s+(Chapter\s+\d+|Appendix\s+[A-Z]).*?\n", "", cleaned_md, count=1, flags=re.M)
    cleaned_md = re.sub(r"^##\s+(Chapter\s+\d+|Appendix\s+[A-Z]).*?\n", "", cleaned_md, count=1, flags=re.M)

    res = subprocess.run(
        ["pandoc", "-f", "markdown", "-t", "typst"],
        input=cleaned_md,
        text=True,
        capture_output=True,
        check=True
    )
    typst_out = res.stdout

    # Inline diagrams in typst: replace pandoc #figure with clean center image
    def replace_figure(match):
        diag_name = match.group(1)
        diag_path = f"diagrams/{diag_name}-{edition}.svg"
        return f"\n#v(0.6em)\n#align(center)[#image(\"{diag_path}\", width: 95%)]\n#v(0.6em)\n"

    typst_out = re.sub(
        r'#figure\(\s*image\("(?:diagrams/)?(diagram\d+-[a-z-]+).*?\n\)\n?',
        replace_figure,
        typst_out,
        flags=re.S
    )

    return typst_out

def build_typst_document(edition):
    """Assembles the complete Typst source code for the requested edition."""
    if edition == "print":
        ink = "#0B0C0E"
        paper = "#EDE8DC"
        ash = "#6F6A62"
        garnet = "#A3222F"
        gold = "#96752C"
        card_bg = "#E2DDD1"
        card_border = "#B0A898"
        raven_logo = "assets/ravenhelm-raven-black-eye.svg"
    else: # dark
        ink = "#EDE8DC"
        paper = "#0B0C0E"
        ash = "#8E939B"
        garnet = "#A3222F"
        gold = "#C4A45A"
        card_bg = "#14171C"
        card_border = "#2B303A"
        raven_logo = "assets/ravenhelm-raven-bone-eye.svg"

    preamble = f'''
#let ink = rgb("{ink}")
#let paper = rgb("{paper}")
#let ash = rgb("{ash}")
#let garnet = rgb("{garnet}")
#let gold = rgb("{gold}")
#let card_bg = rgb("{card_bg}")
#let card_border = rgb("{card_border}")

#set page(
  width: 5.5in,
  height: 8.5in,
  margin: (top: 0.85in, bottom: 0.85in, inside: 0.85in, outside: 0.75in),
  fill: paper
)

#set text(
  font: "Source Serif 4",
  size: 9.6pt,
  fill: ink,
  lang: "en",
  hyphenate: true
)

#set par(
  justify: true,
  leading: 0.68em,
  first-line-indent: 1.1em,
  spacing: 0.72em
)

// Suppress heading hyphenation
#show heading: set text(hyphenate: false)

// Headings styling
#show heading.where(level: 1): it => block(
  spacing: 0.4em,
  text(font: "Source Serif 4", size: 19pt, weight: 600, fill: ink)[#it.body]
)

#show heading.where(level: 2): it => block(
  spacing: 1.1em,
  text(font: "Source Serif 4", size: 13pt, weight: 600, fill: garnet)[#it.body]
)

#show heading.where(level: 3): it => block(
  spacing: 0.9em,
  text(font: "Source Serif 4", size: 10.5pt, weight: 600, fill: ink)[#it.body]
)

#show heading.where(level: 4): it => block(
  spacing: 0.7em,
  text(font: "IBM Plex Mono", size: 8.5pt, weight: 600, fill: ash, tracking: 0.08em)[#it.body]
)

// Code styling: inline raw code (fixed padding to avoid spaces before punctuation)
#show raw.where(block: false): it => box(
  fill: card_bg,
  inset: (x: 2.5pt, y: 0pt),
  outset: (y: 2.5pt),
  radius: 2pt
)[#text(font: "IBM Plex Mono", size: 8.2pt, it)]

// Code styling: block code
#show raw.where(block: true): it => block(
  width: 100%,
  fill: card_bg,
  stroke: 0.5pt + card_border,
  inset: 7pt,
  radius: 3pt,
  spacing: 0.9em,
  text(font: "IBM Plex Mono", size: 7.4pt, fill: ink, it)
)

// Quote / Callout styling
#show quote: it => block(
  width: 100%,
  fill: card_bg,
  stroke: (left: 2.5pt + garnet, rest: 0.5pt + card_border),
  inset: (x: 9pt, y: 7pt),
  radius: (right: 3pt),
  spacing: 0.9em,
  text(style: "italic", size: 8.8pt, it.body)
)

// Table styling
#show table: set text(font: "IBM Plex Mono", size: 7.6pt)
#show table.cell.where(y: 0): set text(weight: "bold", fill: ink)

// ==========================================
// 1. FRONT COVER
// ==========================================
#page(margin: 0in, numbering: none, header: none, footer: none)[
  #place(top + left, rect(width: 100%, height: 100%, fill: paper))
  #place(center + horizon, dy: -1.3in)[
    #image("{raven_logo}", width: 3.5in)
  ]
  #place(center + horizon, dy: 1.4in)[
    #set align(center)
    #text(font: "Source Serif 4", size: 24pt, weight: 600, fill: ink)[Ravenhelm Release Operations]
    #v(0.08in)
    #text(font: "Source Serif 4", size: 18pt, weight: 400, fill: garnet)[Methodology]
    #v(0.2in)
    #text(font: "IBM Plex Mono", size: 8.2pt, fill: ash, tracking: 0.16em)[A TIERED METHODOLOGY FOR ARTIFACT CUSTODY & MULTI-SURFACE DEPLOYMENT]
    #v(0.55in)
    #text(font: "Source Serif 4", size: 11pt, weight: 600, fill: ink)[{BYLINE}]
    #v(0.05in)
    #text(font: "IBM Plex Mono", size: 7.5pt, fill: ash, tracking: 0.12em)[RAVENHELM LLC · 2026]
  ]
]

// ==========================================
// 2. VERSO / COPYRIGHT & IMPRINT
// ==========================================
#page(numbering: none, header: none, footer: none)[
  #v(1fr)
  #set text(font: "IBM Plex Mono", size: 7pt, fill: ash, tracking: 0.04em, hyphenate: false)
  #set par(justify: false, first-line-indent: 0em, leading: 0.9em)
  *Ravenhelm Release Operations Methodology (RROM)* \\
  Version 1.0.0 (2026-11-04) \\
  Authored by {BYLINE}. \\
  {COPYRIGHT} \\
  Published by {IMPRINT}. \\
  \\
  Distributed under the *RROM Community License 1.0*. \\
  Free to read, implement, and distribute verbatim internally within any organization. \\
  Commercial training, certification, and derivative consulting products reserved by Ravenhelm LLC. \\
  \\
  Inquiries: nate\\@ravenhelm.co · ravenhelm.co \\
  Source repository: github.com/nwalker85/rrom-method \\
  \\
  Set in Source Serif 4 and IBM Plex Mono. \\
  Typeset using Typst on macOS. \\
  #v(0.4in)
]

// ==========================================
// 3. HALF TITLE & EPIGRAPH
// ==========================================
#page(numbering: none, header: none, footer: none)[
  #v(2.3in)
  #align(center)[
    #text(font: "Source Serif 4", size: 14pt, weight: 600)[Ravenhelm Release Operations Methodology]
    #v(0.25in)
    #text(font: "Source Serif 4", size: 10.5pt, style: "italic", fill: ash)[
      "Builds are the unit; releases are names.\\
       Releases never rebuild code."
    ]
    #v(0.12in)
    #text(font: "IBM Plex Mono", size: 7.5pt, fill: garnet, tracking: 0.14em)[— THE CORE AXIOM (ADR 0007)]
  ]
]

// ==========================================
// 4. TABLE OF CONTENTS
// ==========================================
#page(numbering: none, header: none, footer: none)[
  #v(0.4in)
  #align(center)[
    #text(font: "Source Serif 4", size: 18pt, weight: 600)[Contents]
  ]
  #v(0.25in)
  #outline(title: none, depth: 1, indent: auto)
]

// ==========================================
// 5. HOW TO READ IT
// ==========================================
#page(numbering: none, header: none, footer: none)[
  #v(0.3in)
  #align(left)[
    #text(font: "IBM Plex Mono", size: 8.5pt, weight: 600, fill: garnet, tracking: 0.16em)[GUIDE]
    #v(0.08in)
    #heading(level: 1, numbering: none, outlined: true)[How to Read It]
    #v(0.05in)
    #line(length: 100%, stroke: 0.5pt + ash)
  ]
  #v(0.15in)
  
  #text(font: "IBM Plex Mono", size: 7.8pt, weight: 600, fill: garnet, tracking: 0.12em)[IN ORDER] \\
  #set text(size: 8.8pt)
  The chapters build sequentially from foundational axioms to concrete physical rails, verification gates, operational protocols, security boundaries, and assessment scorecards. Chapter 3 (*The Numbered Principles*) establishes the 18 numbered rules cited throughout every subsequent chapter as `RP-01` through `RP-18`.
  
  #v(0.12in)
  #text(font: "IBM Plex Mono", size: 7.8pt, weight: 600, fill: garnet, tracking: 0.12em)[BY ROLE — THE INSTALL PATH] \\
  #set text(size: 8.8pt)
  *Release Operator:* Chapters 01, 02, 04, 06, 07, 10 (Day-to-day release execution, promotion, and forward hotfixes). \\
  *Artifact Custodian:* Chapters 02, 05, 06, 12, 13, Appendix A (OCI digest immutability, Harbor management, formula sandbox). \\
  *Platform Engineer:* Chapters 05, 06, 09, 11, 12, Appendix B (GitOps reconciliation, cutovers, automated controller architecture). \\
  *Security & Compliance Auditor:* Chapters 04, 07, 11, 13, 14 (SLSA-3 provenance, Ehwaz elevation, non-repudiation).
  
  #v(0.12in)
  #text(font: "IBM Plex Mono", size: 7.8pt, weight: 600, fill: garnet, tracking: 0.12em)[BY NEED — CRISIS & ARCHITECTURE] \\
  #set text(size: 8.8pt)
  *Recovering from release drift or triage failure:* Read Chapters 01, 02, 06, 10. \\
  *Architecting cutovers vs. deployments:* Read Chapters 06, 09, Appendix A. \\
  *Integrating autonomous AI agents safely:* Read Chapters 04, 07, 11.
  
  #v(0.12in)
  #text(font: "IBM Plex Mono", size: 7.8pt, weight: 600, fill: garnet, tracking: 0.12em)[NAVIGATING THIS BOOK] \\
  #set text(size: 8.8pt)
  The bookmark outline carries every chapter and major section. Chapter openers feature metadata badges citing applicable physical rails and principles. Code symbols, manifests, and CLI recipes follow strict POSIX standards.
]

// ==========================================
// 6. THE PRINCIPLES AT A GLANCE
// ==========================================
#page(numbering: none, header: none, footer: none)[
  #v(0.3in)
  #align(left)[
    #text(font: "IBM Plex Mono", size: 8.5pt, weight: 600, fill: garnet, tracking: 0.16em)[CANON]
    #v(0.08in)
    #heading(level: 1, numbering: none, outlined: true)[The Principles at a Glance]
    #v(0.05in)
    #line(length: 100%, stroke: 0.5pt + ash)
  ]
  #v(0.12in)
  #set text(font: "IBM Plex Mono", size: 7.2pt, fill: ash)
  #set par(justify: false, first-line-indent: 0em, leading: 0.8em)
  
  #text(weight: "bold", fill: garnet)[GROUP A — ARTIFACT CUSTODY & THE CORE AXIOM] \\
  #text(fill: ink)[RP-01] Builds are the immutable unit; releases are authorized names \\
  #text(fill: ink)[RP-02] Source commits do not execute; binaries and digests execute \\
  #text(fill: ink)[RP-03] Single-build rule: compile on merge, promote across environments \\
  #text(fill: ink)[RP-04] Cryptographic pinning over mutable pointers (:latest is banned) \\
  \\
  #text(weight: "bold", fill: garnet)[GROUP B — THE THREE PHYSICAL RAILS] \\
  #text(fill: ink)[RP-05] Rail A (K3s GitOps): reconcile immutable Harbor OCI via Argo CD \\
  #text(fill: ink)[RP-06] Rail B (Workstation Tap): sandboxed inreplace versioning \\
  #text(fill: ink)[RP-07] Rail C (Desktop OTA): Ed25519-signed release archives \\
  #text(fill: ink)[RP-08] Dual-surface lock: synchronized deployment across rails \\
  \\
  #text(weight: "bold", fill: garnet)[GROUP C — DEPLOYMENT AUTHORITY & ELEVATION] \\
  #text(fill: ink)[RP-09] Autonomous continuous deployment to staging on merge \\
  #text(fill: ink)[RP-10] Explicit operator authorization gate for production \\
  #text(fill: ink)[RP-11] Cutovers are architectural shifts requiring ADRs and decommission \\
  #text(fill: ink)[RP-12] Identity, data, and transport mutations require elevation \\
  \\
  #text(weight: "bold", fill: garnet)[GROUP D — VERIFICATION & RELEASE PARITY] \\
  #text(fill: ink)[RP-13] The Source Parity Rule: release PRs modify only release metadata \\
  #text(fill: ink)[RP-14] Independent runtime verification before declaring release complete \\
  #text(fill: ink)[RP-15] The Rollback Illusion: rollback means repointing to proven digests \\
  \\
  #text(weight: "bold", fill: garnet)[GROUP E — OBSERVABILITY, AUDITING & GOVERNANCE] \\
  #text(fill: ink)[RP-16] Content-addressable provenance and SLSA attestation \\
  #text(fill: ink)[RP-17] Ephemeral secrets and vault isolation \\
  #text(fill: ink)[RP-18] Semantic Versioning governs human and machine contracts
]

// ==========================================
// 7. RUNNING HEADERS & BODY PAGES
// ==========================================
#set page(
  numbering: "1",
  number-align: center,
  footer: context [
    #set text(font: "IBM Plex Mono", size: 7.5pt, fill: ash, tracking: 0.08em)
    #align(center)[#counter(page).display("1")]
  ],
  header: context [
    #set text(font: "IBM Plex Mono", size: 7pt, fill: ash, tracking: 0.14em)
    #let page_num = counter(page).get().first()
    #let is_chapter_opener = query(heading.where(level: 1)).any(h => h.location().page() == page_num)
    #if not is_chapter_opener [
      #if calc.odd(page_num) [
        #align(right)[RAVENHELM RELEASE OPERATIONS METHODOLOGY]
      ] else [
        #align(left)[{BYLINE} · RROM METHOD]
      ]
    ]
  ]
)

'''

    body_chapters = []
    for file_name, num, title, diagram_base in CHAPTER_FILES:
        chapter_path = os.path.join(DOCS_DIR, file_name)
        if not os.path.exists(chapter_path):
            continue
        typst_content = markdown_to_typst_via_pandoc(chapter_path, edition)

        is_appendix = num in ("A", "B")
        label_prefix = "APPENDIX" if is_appendix else "CHAPTER"

        # Determine rail / principles badge for chapter opener
        badge_text = f"PRINCIPLES CITED: RP-1 · RP-2 · RP-3"
        if num == "01":
            badge_text = "SCOPE: METHODOLOGY FRONT DOOR · APPLIES TO ALL RAILS"
        elif num == "02":
            badge_text = "FOUNDATION: ADR 0007 · RP-1 · RP-2 · RP-3 · RP-4"
        elif num == "03":
            badge_text = "CANON: 18 NUMBERED PRINCIPLES · RP-1 THROUGH RP-18"
        elif num == "04":
            badge_text = "ROLES: OPERATOR · CUSTODIAN · AUDITOR · SYNTHETIC AGENT"
        elif num == "05":
            badge_text = "REGISTRY TOPOLOGY: HARBOR OCI · CONTENT DIGESTS · IMMUTABILITY"
        elif num == "06":
            badge_text = "PHYSICAL RAILS: RAIL A (K3S GITOPS) · RAIL B (TAP) · RAIL C (OTA)"
        elif num == "07":
            badge_text = "WORKFLOW CANON: THE VALIDATION GATE · SOURCE PARITY RULE"
        elif num == "08":
            badge_text = "MATURITY: TIERS 0 THROUGH 4 ADOPTION LADDER"
        elif num == "09":
            badge_text = "ARCHITECTURAL DISCIPLINE: CUTOVERS VS. DEPLOYMENTS · ADR-011"
        elif num == "10":
            badge_text = "INCIDENT DISCIPLINE: FORWARD FIXES · ROLLBACK MECHANICS"
        elif num == "11":
            badge_text = "SECURITY: VAULT ISOLATION · EHWAZ ELEVATION GATE"
        elif num == "12":
            badge_text = "INTEGRATION: FORGEJO ACTIONS · HARBOR WEBHOOKS · ARGO CD"
        elif num == "13":
            badge_text = "AUDITING: SLSA-3 PROVENANCE · IN-TOTO ATTESTATIONS"
        elif num == "14":
            badge_text = "EVALUATION: 20-POINT MATURITY RUBRIC & SCORECARD"
        elif num == "A":
            badge_text = "REFERENCE: RAIL B SANDBOXED FORMULA INREPLACE PLAYBOOK"
        elif num == "B":
            badge_text = "SPECIFICATION: VITKI AUTOMATED RECONCILER CRD & CONTROLLER"

        chapter_header = f"""
#pagebreak()
#v(0.8in)
#align(left)[
  #text(font: "IBM Plex Mono", size: 8.5pt, weight: 600, fill: garnet, tracking: 0.16em)[{label_prefix} · {num}]
  #v(0.08in)
  #heading(level: 1, numbering: (..n) => "{num}", outlined: true)[{title}]
  #v(0.12in)
  #text(font: "IBM Plex Mono", size: 7pt, fill: ash, tracking: 0.08em)[{badge_text}]
  #v(0.05in)
  #line(length: 100%, stroke: 0.5pt + ash)
]
#v(0.3in)
"""
        chapter_block = chapter_header + typst_content
        
        # If diagram was not inlined in text, embed it here
        if diagram_base and f"diagrams/{diagram_base}" not in typst_content:
            diag_file = f"diagrams/{diagram_base}-{edition}.svg"
            if os.path.exists(os.path.join(ROOT, diag_file)):
                chapter_block += f"""
#v(0.8em)
#align(center)[
  #image("{diag_file}", width: 95%)
]
#v(0.8em)
"""
        body_chapters.append(chapter_block)

    colophon = f'''
// ==========================================
// 7. COLOPHON
// ==========================================
#pagebreak()
#set page(numbering: none, header: none, footer: none)
#v(1fr)
#align(center)[
  #image("{raven_logo}", width: 1.1in)
  #v(0.25in)
  #set text(font: "IBM Plex Mono", size: 7pt, fill: ash, tracking: 0.04em, hyphenate: false)
  #set par(justify: false, first-line-indent: 0em, leading: 0.95em)
  Ravenhelm Release Operations Methodology (RROM) \\
  Version 1.0.0 (2026-11-04) \\
  Authored by {BYLINE}. \\
  {COPYRIGHT} \\
  Published by {IMPRINT}. \\
  Distributed under the RROM Community License 1.0. \\
  Set in Source Serif 4 and IBM Plex Mono. \\
  Typeset using Typst 0.15.1 on macOS. \\
  ravenhelm.co · nwalker.cc
]
#v(0.6in)
'''

    return preamble + "\n".join(body_chapters) + colophon

def main():
    os.makedirs(OUTDIR, exist_ok=True)
    for edition in ("dark", "print"):
        typ_content = build_typst_document(edition)
        typ_path = os.path.join(OUTDIR, f"build-rrom-{edition}.typ")
        with open(typ_path, "w", encoding="utf-8") as f:
            f.write(typ_content)

        if edition == "dark":
            pdf_path = os.path.join(OUTDIR, "RROM-v1.0.0-dark.pdf")
        else:
            pdf_path = os.path.join(OUTDIR, "RROM-v1.0.0.pdf")

        cmd = [
            "typst", "compile",
            "--root", ROOT,
            "--font-path", FONTS_DIR,
            typ_path,
            pdf_path
        ]
        print(f"Compiling {edition} edition -> {pdf_path}...")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Error compiling {edition}:", res.stderr, file=sys.stderr)
            sys.exit(res.returncode)
        print(f"Successfully compiled {pdf_path}")

        # Clean up temporary .typ file
        if os.path.exists(typ_path):
            os.remove(typ_path)

if __name__ == "__main__":
    main()

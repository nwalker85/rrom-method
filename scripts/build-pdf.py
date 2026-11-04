#!/usr/bin/env python3
"""Typeset Ravenhelm Release Operations Methodology (RROM) as a publication-grade PDF using Typst.

Compiles two editions:
  dark   — bone on obsidian (screen edition, matching 'Memory, Walking — v3 (dark).pdf')
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
    ("01-what-this-is.md", "Chapter 1", None),
    ("02-the-core-axiom.md", "Chapter 2", "diagram1-core-axiom"),
    ("03-numbered-principles.md", "Chapter 3", None),
    ("04-the-operator-roles.md", "Chapter 4", None),
    ("05-the-artifact-surface.md", "Chapter 5", None),
    ("06-the-three-physical-rails.md", "Chapter 6", "diagram2-three-rails"),
    ("07-workflow-canon-and-validation-gate.md", "Chapter 7", "diagram3-parity-triangle"),
    ("08-tiered-adoption-ladder.md", "Chapter 8", None),
    ("09-cutovers-vs-deployments.md", "Chapter 9", None),
    ("10-hotfixes-emergencies-and-rollback.md", "Chapter 10", None),
    ("11-security-blast-radius-and-elevation.md", "Chapter 11", "diagram4-blast-radius"),
    ("12-code-host-and-registry-integration.md", "Chapter 12", None),
    ("13-auditing-provenance-and-compliance.md", "Chapter 13", None),
    ("14-the-assessment.md", "Chapter 14", None),
    ("appendix-a-formula-inreplace-playbook.md", "Appendix A", None),
    ("appendix-b-vitki-reference-specification.md", "Appendix B", None),
]

def markdown_to_typst_via_pandoc(md_path):
    """Converts a Markdown file to Typst syntax via pandoc."""
    raw_md = open(md_path, "r", encoding="utf-8").read()
    # Strip HTML license comments and rubric checks
    cleaned_md = re.sub(r"<!--.*?-->", "", raw_md, flags=re.S)
    
    res = subprocess.run(
        ["pandoc", "-f", "markdown", "-t", "typst"],
        input=cleaned_md,
        text=True,
        capture_output=True,
        check=True
    )
    return res.stdout

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

// Headings styling
#show heading.where(level: 1): it => block(
  spacing: 1.2em,
  align(center)[
    #text(font: "Source Serif 4", size: 18pt, weight: 600, fill: ink)[#it.body]
  ]
)

#show heading.where(level: 2): it => block(
  spacing: 1.1em,
  text(font: "Source Serif 4", size: 13.5pt, weight: 600, fill: garnet)[#it.body]
)

#show heading.where(level: 3): it => block(
  spacing: 0.9em,
  text(font: "Source Serif 4", size: 11pt, weight: 600, fill: ink)[#it.body]
)

#show heading.where(level: 4): it => block(
  spacing: 0.7em,
  text(font: "IBM Plex Mono", size: 9pt, weight: 600, fill: ash, tracking: 0.08em)[#it.body]
)

// Code styling
#show raw.where(block: false): it => text(
  font: "IBM Plex Mono",
  size: 8.5pt,
  fill: ink,
  box(fill: card_bg, inset: (x: 3pt, y: 1.5pt), radius: 2pt, it)
)

#show raw.where(block: true): it => block(
  width: 100%,
  fill: card_bg,
  stroke: 0.5pt + card_border,
  inset: 8pt,
  radius: 4pt,
  spacing: 1.0em,
  text(font: "IBM Plex Mono", size: 7.6pt, fill: ink, it)
)

// Quote / Callout styling
#show quote: it => block(
  width: 100%,
  fill: card_bg,
  stroke: (left: 2.5pt + garnet, rest: 0.5pt + card_border),
  inset: (x: 10pt, y: 8pt),
  radius: (right: 4pt),
  spacing: 1.0em,
  text(style: "italic", size: 9pt, it.body)
)

// Table styling
#show table: set text(font: "IBM Plex Mono", size: 8pt)
#show table.cell.where(y: 0): set text(weight: "bold", fill: ink)

// ==========================================
// 1. FRONT COVER
// ==========================================
#page(margin: 0in, numbering: none, header: none, footer: none)[
  #place(top + left, rect(width: 100%, height: 100%, fill: paper))
  #place(center + horizon, dy: -1.3in)[
    #image("{raven_logo}", width: 3.6in)
  ]
  #place(center + horizon, dy: 1.4in)[
    #set align(center)
    #text(font: "Source Serif 4", size: 24pt, weight: 600, fill: ink)[Ravenhelm Release Operations]
    #v(0.08in)
    #text(font: "Source Serif 4", size: 18pt, weight: 400, fill: garnet)[Methodology]
    #v(0.2in)
    #text(font: "IBM Plex Mono", size: 8.5pt, fill: ash, tracking: 0.16em)[A TIERED METHODOLOGY FOR ARTIFACT CUSTODY & MULTI-SURFACE DEPLOYMENT]
    #v(0.55in)
    #text(font: "Source Serif 4", size: 11pt, weight: 600, fill: ink)[{BYLINE}]
    #v(0.05in)
    #text(font: "IBM Plex Mono", size: 7.5pt, fill: ash, tracking: 0.12em)[RAVENHELM LLC · 2026]
  ]
]

// ==========================================
// 2. HALF TITLE & EPIGRAPH
// ==========================================
#page(numbering: none, header: none, footer: none)[
  #v(2.5in)
  #align(center)[
    #text(font: "Source Serif 4", size: 13pt, weight: 600)[Ravenhelm Release Operations Methodology]
    #v(0.2in)
    #text(font: "Source Serif 4", size: 10pt, style: "italic", fill: ash)[
      "Builds are the unit; releases are names.\\
       Releases never rebuild code."
    ]
    #v(0.1in)
    #text(font: "IBM Plex Mono", size: 7.5pt, fill: garnet, tracking: 0.14em)[— THE CORE AXIOM (ADR 0007)]
  ]
]

// ==========================================
// 3. RUNNING HEADERS & BODY PAGES
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
    #if calc.odd(counter(page).get().first()) [
      #align(right)[RAVENHELM RELEASE OPERATIONS METHODOLOGY]
    ] else [
      #align(left)[{BYLINE} · RROM METHOD]
    ]
  ]
)
#counter(page).update(1)

'''

    body_chapters = []
    for file_name, label, diagram_base in CHAPTER_FILES:
        chapter_path = os.path.join(DOCS_DIR, file_name)
        if not os.path.exists(chapter_path):
            continue
        typst_content = markdown_to_typst_via_pandoc(chapter_path)

        chapter_block = f"""
#pagebreak()
{typst_content}
"""
        # Embed vector diagram if specified
        if diagram_base:
            diag_file = f"diagrams/{diagram_base}-{edition}.svg"
            if os.path.exists(os.path.join(ROOT, diag_file)):
                chapter_block += f"""
#v(1.0em)
#align(center)[
  #image("{diag_file}", width: 95%)
]
#v(0.8em)
"""
        body_chapters.append(chapter_block)

    colophon = f'''
// ==========================================
// 4. COLOPHON
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
  Version 1.0.0 \\
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

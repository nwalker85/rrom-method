#!/usr/bin/env bash
#
# compile.sh — concatenate the 14 RROM chapters plus appendices into a single-file publication edition.
#
# Usage:
#   ./scripts/compile.sh > build/rrom.md
#

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHAPTERS_DIR="${ROOT}/docs/chapters"

CHAPTERS=(
    "01-what-this-is.md"
    "02-the-core-axiom.md"
    "03-numbered-principles.md"
    "04-the-operator-roles.md"
    "05-the-artifact-surface.md"
    "06-the-three-physical-rails.md"
    "07-workflow-canon-and-validation-gate.md"
    "08-tiered-adoption-ladder.md"
    "09-cutovers-vs-deployments.md"
    "10-hotfixes-emergencies-and-rollback.md"
    "11-security-blast-radius-and-elevation.md"
    "12-code-host-and-registry-integration.md"
    "13-auditing-provenance-and-compliance.md"
    "14-the-assessment.md"
    "appendix-a-formula-inreplace-playbook.md"
    "appendix-b-vitki-reference-specification.md"
)

for ch in "${CHAPTERS[@]}"; do
    if [ ! -f "${CHAPTERS_DIR}/${ch}" ]; then
        echo "ERROR: missing chapter file: ${CHAPTERS_DIR}/${ch}" >&2
        exit 1
    fi
done

printf '# Ravenhelm Release Operations Methodology (RROM)\n\n'
printf '*A tiered, sovereign operating methodology for software release, artifact custody, and multi-surface deployment.*\n\n'
printf '© 2026 Ravenhelm LLC. Licensed material under RROM Community License 1.0.\n\n'
printf -- '---\n\n'

printf '## Table of Contents\n\n'
i=1
for ch in "${CHAPTERS[@]}"; do
    title=$(grep -m1 -E '^# (Chapter|Appendix)' "${CHAPTERS_DIR}/${ch}" | sed 's/^# //')
    if [ -z "${title}" ]; then
        title="Chapter ${i}"
    fi
    anchor=$(printf '%s' "${title}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | tr -s '-')
    printf -- '- [%s](#%s)\n' "${title}" "${anchor}"
    i=$((i + 1))
done
printf '\n---\n\n'

first=1
for ch in "${CHAPTERS[@]}"; do
    if [ "${first}" -eq 1 ]; then
        cat "${CHAPTERS_DIR}/${ch}"
        first=0
    else
        sed -e '/^<!-- LICENSE:/d' -e '/^<!-- RUBRIC_CHECK/d' "${CHAPTERS_DIR}/${ch}"
    fi
    printf '\n---\n\n'
done

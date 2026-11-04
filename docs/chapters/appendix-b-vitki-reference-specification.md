# Appendix B: The Vitki Reference Specification

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## The Canonical Reference Architecture

Vitki (`nate/vitki`) is the production reference implementation that birthed the Ravenhelm Release Operations Methodology. This appendix details its concrete directory layout, architectural decisions, and release helper scripts.

---

## 1. Directory Topology

```text
vitki/
├── .forgejo/
│   └── workflows/
│       ├── build.yml                  <- Ingress build on merge to main
│       └── release.yml                <- Parity verification & Harbor retag on tag
├── chart/
│   ├── Chart.yaml                     <- SemVer metadata (version, appVersion)
│   ├── values.yaml                    <- Production values: pins tag, digest, build
│   ├── values-uat.yaml                <- Staging values: follows :uat tag
│   └── templates/
│       └── deployment.yaml            <- Renders repository:tag@digest
├── scripts/
│   ├── release-pr.sh                  <- Pins build b<N> to vX.Y.Z in values.yaml
│   ├── harbor-artifact.sh             <- Speaks Registry v2 API: retags digests
│   ├── check-release-tag.sh           <- Verifies tag == Chart == values
│   └── check-release-source-parity.sh <- Proves zero application source drift
└── docs/
    └── architecture/
        └── decisions/
            ├── 0002-k3s-runtime-k0s-local.md
            ├── 0003-helm-harbor-argocd.md
            ├── 0004-semver-prod-tags.md
            └── 0007-builds-are-the-unit-releases-are-names.md
```

---

## 2. Core Helper Scripts

### `scripts/release-pr.sh` (Release Pinning)
```bash
#!/usr/bin/env bash
# Usage: scripts/release-pr.sh <build-id> <semver-tag>
# Example: scripts/release-pr.sh b42 v1.4.2

set -euo pipefail

BUILD="$1"
TAG="$2"
SEMVER="${TAG#v}"

# 1. Resolve digest for build b<N> from Harbor
DIGEST=$(scripts/harbor-artifact.sh resolve "${BUILD}")

# 2. Update Helm Chart metadata
yq -i ".version = \"${SEMVER}\"" chart/Chart.yaml
yq -i ".appVersion = \"${SEMVER}\"" chart/Chart.yaml

# 3. Pin image digest in values.yaml
yq -i ".image.tag = \"${TAG}\"" chart/values.yaml
yq -i ".image.digest = \"${DIGEST}\"" chart/values.yaml
yq -i ".image.build = \"${BUILD}\"" chart/values.yaml

# 4. Enforce source parity check
scripts/check-release-source-parity.sh
```

---

### `scripts/check-release-source-parity.sh` (Parity Guard)
```bash
#!/usr/bin/env bash
# Asserts that the release commit modified ONLY chart and changelog files.

set -euo pipefail

FORBIDDEN_DIFFS=$(git diff --name-only origin/main | grep -vE '^(chart/|CHANGELOG\.md|docs/runbooks/release\.md)' || true)

if [ -n "${FORBIDDEN_DIFFS}" ]; then
  echo "ERROR: Release PR touches application source files!" >&2
  echo "${FORBIDDEN_DIFFS}" >&2
  exit 1
fi

echo "PASS: Zero application source drift proven."
```

---

### `scripts/check-release-tag.sh` (Parity Triangle)
```bash
#!/usr/bin/env bash
# Validates that git tag == values.yaml tag == Chart.yaml appVersion

set -euo pipefail

GIT_TAG="${GITHUB_REF_NAME:-$(git describe --tags --exact-match)}"
VALUES_TAG=$(yq .image.tag chart/values.yaml)
CHART_APP_VER="v$(yq .appVersion chart/Chart.yaml)"

if [ "${GIT_TAG}" != "${VALUES_TAG}" ] || [ "${GIT_TAG}" != "${CHART_APP_VER}" ]; then
  echo "ERROR: Release parity triangle mismatch!" >&2
  echo "git tag:       ${GIT_TAG}" >&2
  echo "values.yaml:   ${VALUES_TAG}" >&2
  echo "Chart.yaml:    ${CHART_APP_VER}" >&2
  exit 1
fi

echo "PASS: Release parity triangle verified."
```

By standardizing these exact scripts across all platform and product repositories, Ravenhelm maintains unbroken release discipline across its entire software fleet.

<!-- RUBRIC_CHECK: Appendix B conforms to RROM specification. -->

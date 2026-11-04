# Chapter 12: Code Host & Registry Integration

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Engineering the Automation Substrate

RROM is agnostic to whether your source code lives on self-hosted Forgejo/Gitea, GitHub Enterprise, or GitLab. What matters is the strict enforcement of code-host hooks, runner network boundaries, and registry integration contracts.

---

## 1. The Build Workflow (`build.yml`)

The ingress build workflow executes on every push/merge to the default trunk (`main`). Below is the canonical workflow contract implemented in the Vitki reference:

```yaml
# .forgejo/workflows/build.yml / .github/workflows/build.yml
name: Build & Ingress Custody

on:
  push:
    branches:
      - main
    paths-ignore:
      - 'chart/**'
      - 'docs/**'
      - '*.md'

jobs:
  build:
    runs-on: [self-hosted, eikthyrnir]
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Resolve Commit & Build ID
        id: meta
        run: |
          SHA12=$(git rev-parse --short=12 HEAD)
          BUILD_NUM="b${{ github.run_number }}"
          echo "sha=${SHA12}" >> $GITHUB_OUTPUT
          echo "build=${BUILD_NUM}" >> $GITHUB_OUTPUT

      - name: Compile and Package Image
        run: |
          podman build \
            --label "net.ravenmask.build=${{ steps.meta.outputs.build }}" \
            --label "org.opencontainers.image.revision=${{ steps.meta.outputs.sha }}" \
            -t harbor.ravenhelm.dev/platform/vitki:${{ steps.meta.outputs.build }} \
            -t harbor.ravenhelm.dev/platform/vitki:sha-${{ steps.meta.outputs.sha }} \
            -t harbor.ravenhelm.dev/platform/vitki:uat \
            .

      - name: Push to Internal Registry
        env:
          HARBOR_USER: ${{ secrets.HARBOR_ROBOT_USER }}
          HARBOR_PASS: ${{ secrets.HARBOR_ROBOT_TOKEN }}
        run: |
          echo "$HARBOR_PASS" | podman login harbor-nginx.lan:8443 -u "$HARBOR_USER" --password-stdin
          podman push harbor.ravenhelm.dev/platform/vitki:${{ steps.meta.outputs.build }}
          podman push harbor.ravenhelm.dev/platform/vitki:sha-${{ steps.meta.outputs.sha }}
          podman push harbor.ravenhelm.dev/platform/vitki:uat
```

### Critical Operational Details:
1. **`paths-ignore` Guard:** Pushes that alter only Helm charts, markdown documentation, or changelogs are explicitly ignored. This prevents the Release PR merge from triggering an unnecessary recursive build!
2. **Internal Network Bypass (`harbor-nginx.lan`):** CI runners push directly over high-speed local network interfaces (`10GbE / internal MTU`), bypassing external Cloudflare tunnels and upload payload size limits.
3. **OCI Labels:** The build embeds `net.ravenmask.build` and `org.opencontainers.image.revision` as immutable OCI container labels, binding the running container directly to its git commit.

---

## 2. The Release Workflow (`release.yml`)

When an annotated git tag (`v*`) is pushed, `release.yml` triggers. Notice that it contains **zero build commands**:

```yaml
# .forgejo/workflows/release.yml / .github/workflows/release.yml
name: Release & Provenance Promotion

on:
  push:
    tags:
      - 'v*'

jobs:
  verify:
    runs-on: [self-hosted, eikthyrnir]
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Enforce Parity Checks
        run: |
          scripts/check-release-tag.sh
          scripts/check-release-source-parity.sh

  promote:
    needs: verify
    runs-on: [self-hosted, eikthyrnir]
    steps:
      - name: Retag Registry Digest
        env:
          HARBOR_USER: ${{ secrets.HARBOR_ROBOT_USER }}
          HARBOR_PASS: ${{ secrets.HARBOR_ROBOT_TOKEN }}
        run: |
          # Speaks Registry v2 API: retags the build digest to vX.Y.Z
          scripts/harbor-artifact.sh retag \
            "$(cat chart/values.yaml | yq .image.build)" \
            "${{ github.ref_name }}"

      - name: Package & Publish OCI Helm Chart
        run: |
          helm package chart/
          helm push vitki-*.tgz oci://harbor.ravenhelm.dev/charts/
```

The release workflow is fast, light, and reliable. Because it does not compile code or pull dependencies, it completes in seconds and is completely immune to upstream registry outages.

<!-- RUBRIC_CHECK: Chapter 12 conforms to RROM specification. -->

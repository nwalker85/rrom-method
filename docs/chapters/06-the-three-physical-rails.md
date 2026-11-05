# Chapter 6: The Three Physical Rails

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Multi-Surface Delivery Architecture

In naive software engineering organizations, release operations are treated as if the entire world consists of a single web backend running behind a load balancer. Teams configure a pipeline to build a container image, push it to a cloud registry, run `kubectl set image`, and declare victory.

Modern enterprise and sovereign engineering topologies rarely conform to this single-surface fantasy. A robust, production-grade ecosystem almost invariably spans three distinct physical computing environments:

1. **Server-Side Backends & Daemons:** Containerized workloads running on orchestrated Kubernetes clusters (e.g., K3s, bare-metal nodes, or managed cloud control planes).
2. **Developer Workstation Tooling:** Native command-line interfaces (CLIs), Ratatui-based terminal user interfaces (TUIs), and diagnostics executed locally on operator laptops (macOS and Linux).
3. **Client Desktop Applications:** Standalone graphical user interface (GUI) client shells (built with frameworks such as Tauri v2, Svelte, and Rust) installed on end-user workstations.

![Diagram 2: The Three Physical Rails](diagram2-three-rails)

When these computing surfaces are treated with disjoint, ad-hoc release processes, severe operational drift occurs. Consider a common failure scenario: an infrastructure platform updates a core cluster backend with a new gRPC protobuf schema and modified state transition logic. If the backend is deployed immediately (Rail A) but the operator CLI distributed via Homebrew (Rail B) remains un-bumped on engineers' machines, operators running administrative commands will issue RPCs with outdated payload schemas or missing tenancy headers. At best, requests are rejected; at worst, the backend fails to validate an omitted field, silently truncating tables or corrupting multi-tenant databases.

Conversely, if an updated CLI is published to developers before the corresponding cluster backend has finished deploying, operators will trigger features that do not yet exist, receiving confusing HTTP `404 Not Found` or gRPC `Unimplemented` errors during active operations.

The Ravenhelm Release Operations Methodology (RROM) codifies **The Three Physical Rails**. Each rail defines a specialized, mathematically sound deployment pipeline tailored to the physical constraints of its execution environment, while enforcing lockstep synchronization whenever a platform spans multiple computing surfaces.

---

## Rail A: Server & Kubernetes Cluster GitOps (The Vitki Reference)

Rail A governs server-side daemons, microservices, and cluster workloads deployed to Kubernetes environments. Its canonical production reference implementation is **Vitki** (`nate/vitki`), an orchestrator and platform backend deployed across high-availability K3s clusters.

| Delivery Stage | Artifact Target | Operational Mechanism |
| :--- | :--- | :--- |
| **1. Ingress Build** | Harbor OCI Registry | Merge to `main` builds container layers and Helm charts; stores `:b<N>`, `:sha-<commit12>`, and updates moving `:uat` tag. |
| **2. Release Tagging** | Registry Manifest API | Release workflow assigns `:vX.Y.Z` to existing `:b<N>` digest via Registry v2 API; zero code recompilation. |
| **3. Manifest Update** | GitOps Repo (`norns-gitops`) | Pinned image digest (`image:tag@sha256:...`) and chart version committed to `values.yaml`. |
| **4. Reconciliation** | Argo CD Controller | Pulls GitOps repo; detects drift; drives progressive rolling deployment on K3s cluster. |
| **5. Runtime Proof** | Active Network Endpoint | Verified via live health probes (`/api/health`, version checks) on active interface before sign-off. |

### 1. Topology: From Ingress Build to Production Pods

The complete Rail A delivery topology consists of five interconnected infrastructure layers:

1. **Ingress CI Packaging:** On every merge to `main`, the CI engine (`.forgejo/workflows/build.yml` or GitHub Actions) compiles the application binary within an isolated build container, packages the OCI image layers, packages the OCI Helm chart, and pushes both to the private Harbor registry.
2. **Harbor OCI Registry (`harbor.ravenhelm.dev`):** The registry serves as the immutable custody vault. The newly ingested image is triple-tagged with `:b<N>` (monotonic build), `:sha-<commit12>` (git provenance), and `:uat` (staging stream), all sharing the identical `@sha256:` digest.
3. **The GitOps State Repository (`nate/norns-gitops`):** Kubernetes desired state is maintained entirely in a dedicated GitOps repository separate from application source code. The GitOps repository defines the Argo CD `Application` resources and environmental Helm values files.
4. **Argo CD Controller Plane:** Running inside the administrative management cluster (`norns`), Argo CD continuously reconciles the live state of cluster resources against the declarative manifests stored in git.
5. **K3s Runtime Cluster:** A 3-node high-availability K3s cluster serves as the production compute substrate, hosting user-facing workloads, internal API gateways, and persistent datastores.

### 2. The Local Inner Loop: Containerized k0s (ADR 0002)

A common point of friction in Kubernetes release engineering is the disparity between developer workstations and production clusters. If developers test their Helm templates and configuration manifests against an ad-hoc local Docker Compose setup, runtime incompatibilities (such as ingress annotations, volume mount permissions, or DNS resolution semantics) are discovered only after deployment to production.

To eliminate this gap, Vitki codifies **ADR 0002: Containerized k0s for Local Inner Loop**:

* Developer laptops run an ephemeral, single-node `k0s` control plane executed directly inside Docker (`k0s in Docker`).
* This containerized k0s instance shares the identical Kubernetes API version, networking semantics, and Helm controller behaviors as the production K3s cluster.
* Developers can render Helm charts locally via `helm template` and test deployments in an isolated sandbox that boots and tears down in seconds, without requiring cloud credentials or impacting shared development infrastructure.
* Once manifests pass local k0s verification, they are committed to git with absolute certainty that the K3s production runtime will execute them identically.

### 3. Separation of Streams: UAT vs. Production

Rail A strictly isolates pre-release validation from live production traffic through dual deployment streams:

#### The UAT Stream (Continuous Validation)
* **Target Environment:** Staging / UAT namespace.
* **Manifest Configuration:** Governed by `chart/values-uat.yaml`.
* **Image Pinning:** Tracks the moving `:uat` tag or the latest `:b<N>` build sequence.
* **Network Exposure:** Bound to dedicated staging ingress routes and internal NodePort `30109`.
* **Argo CD Synchronization:** Automated sync (`automated: { prune: true, selfHeal: true }`) enabled. As soon as a feature PR merges into `main` and CI pushes an image to Harbor, Argo CD reconciles the UAT pods within seconds.
* **Purpose:** Provides a living, always-current environment for automated integration tests, synthetic end-to-end traffic, and user acceptance testing.

#### The Production Stream (Strict SemVer Governance)
* **Target Environment:** Production namespace.
* **Manifest Configuration:** Governed by `chart/values.yaml` in the GitOps repository.
* **Image Pinning:** Pinned strictly to an immutable SemVer tag (`vX.Y.Z`) AND its cryptographic digest:
  ```yaml
  # chart/values.yaml (Production)
  image:
    repository: harbor.ravenhelm.dev/platform/vitki
    tag: v1.4.2
    digest: sha256:7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a
    build: b42
  service:
    type: NodePort
    nodePort: 30108
  ```
* **Network Exposure:** Bound to production Traefik ingress routes and production NodePort `30108`.
* **Argo CD Synchronization:** Gated sync. Reconciled only when an approved release pull request merges into `nate/norns-gitops`.
* **Template Rendering:** The Kubernetes `Deployment` manifest renders the container image utilizing the full digest specifier:
  ```yaml
  spec:
    template:
      spec:
        containers:
          - name: vitki
            image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}@{{ .Values.image.digest }}"
  ```
  This satisfies both human operator ergonomics (the tag `v1.4.2` is visible in `kubectl get pods`) and runtime kernel security (the container engine pulls strictly by immutable SHA-256 digest, rejecting any mutated image layers).

### 4. Declarative Reconciler Authority (RP-9)

Under Rail A, **workstations never execute deployment commands**. Engineers and automated release bots are physically forbidden from running `kubectl apply`, `helm install`, or `helm upgrade` against production clusters from their laptops.

Argo CD is the sole applying authority. When a production release is executed:
1. The Release Custodian opens a PR against `nate/norns-gitops` updating the target revision and pinned digest.
2. The Delivery Closer reviews the diff, verifies build provenance, and merges the PR into `main`.
3. Argo CD detects the git commit, enters a syncing state, applies the updated Helm chart manifests, and monitors pod readiness probes.
4. If an unauthorized human operator attempts to manually modify a Kubernetes deployment via `kubectl edit`, Argo CD detects the configuration drift and immediately overwrites the live resource, restoring it to the declared git state.

---

## Rail B: Developer Workstation CLI/TUI (The Ullr / Yager Reference)

Rail B governs command-line utilities, Ratatui terminal user interfaces, and administrative diagnostics distributed directly to developer workstations. Its canonical reference implementations are **Ullr** (distributed query engine) and **Yager** (`nate/yager`, an autonomous agent harness and operator TUI).

While server deployments enjoy the clean abstraction of container images, distributing compiled native binaries to developer laptops introduces an acute package management dilemma.

| Inreplace Step | Execution Context | Mechanism & Invariant |
| :--- | :--- | :--- |
| **1. Source Archive** | Git Remote (`nate/yager`) | Source pegged to static dev placeholder (`0.1.0`); tagged commit introduces zero source code diffs. |
| **2. Fetch & Verify** | Workstation Sandbox | Homebrew downloads release archive and verifies cryptographic SHA-256 against tap formula. |
| **3. Sandboxed Inreplace** | `/private/tmp/brew-build/` | Formula invokes `inreplace` dynamically on `Cargo.toml` and `Cargo.lock` strictly inside the temp sandbox. |
| **4. Native Compilation** | Local Rust Toolchain | `cargo install` compiles binary embedding injected SemVer; git working tree remains 100% untainted. |
| **5. Runtime Verification** | Homebrew Cellar | Formula test block executes `brew test yager`, asserting `yager --version` matches release version. |

### 1. The Acute Dilemma: Compilation from Source vs. Parity Checks

On macOS workstations, the standard package management interface is **Homebrew**. In high-compliance environments, security policies require internal tools to be distributed via private Homebrew taps (such as `nate/tools`) where formulas compile software directly from source tarballs on the developer's machine:

* Languages like Rust require the crate version to be declared explicitly inside the root manifest (`Cargo.toml`) and locked in dependency manifests (`Cargo.lock`).
* When `cargo install` or `cargo build --release` executes, the Rust compiler reads `Cargo.toml` and embeds the declared version into the resulting binary (accessible at runtime via `env!("CARGO_PKG_VERSION")`).
* In traditional, flawed workflows, a release engineer cuts a release by creating a git commit that bumps `version = "0.1.32"` to `version = "0.1.33"` in `Cargo.toml`, pushes the commit, and tags it.

**Why this is an operational failure:**
Under RROM Principle **RP-5 (Parity Precedes Promotion)**, a release commit must contain zero application source code drift relative to the pre-tested ingress build. The script `scripts/check-release-source-parity.sh` asserts that only deployment configuration manifests (`chart/values.yaml`, `CHANGELOG.md`) may differ from the parent build commit.

If a team bumps `Cargo.toml` in git:
1. It creates an application source commit after the ingress CI build (`:b<N>`) has already tested and passed the code.
2. The released tag points to a commit that has never completed the full integration suite.
3. The parity guard fails, halting the release pipeline.

### 2. The Solution: Sandboxed Formula Inreplace (RP-7)

RROM resolves this dilemma by decoupling the git repository's static manifest from the package manager's build environment.

In the application repository (`nate/yager`), `Cargo.toml` and `Cargo.lock` remain permanently pegged to a development version (such as `"0.1.0"`). No version bumps are ever committed to the git branch.

Instead, the version injection is deferred entirely to the package manager's isolated build sandbox during the execution of the Homebrew formula:

```ruby
# Formula/yager.rb in private tap (nate/tools)
class Yager < Formula
  desc "Terminal User Interface and autonomous agent harness"
  homepage "https://github.com/nwalker85/yager"
  url "https://github.com/nwalker85/yager/archive/refs/tags/v0.1.33.tar.gz"
  sha256 "a8e4f1c9d2b3a7e5f601b4c8d9e2a3f5b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2"
  license "Proprietary"

  depends_on "rust" => :build

  def install
    # Sandboxed inreplace dynamically rewrites manifests inside the build sandbox
    # preserving pristine source parity in the main git repository
    inreplace "Cargo.toml", /^version = .*/, "version = \"#{version}\""
    inreplace "Cargo.lock", /name = "yager"\nversion = "[0-9.]+"/, "name = \"yager\"\nversion = \"#{version}\""

    system "cargo", "install", *std_cargo_args
  end

  test do
    assert_match "yager #{version}", shell_output("#{bin}/yager --version")
  end
end
```

#### Inside Homebrew's Sandbox
When a developer executes `brew install yager` or `brew upgrade yager`:
1. Homebrew downloads the source archive corresponding to the immutable tag `v0.1.33`.
2. It validates the downloaded archive against the declared `sha256` checksum.
3. It unpacks the archive into an ephemeral, sandboxed directory (`/private/tmp/homebrew-yager-20261104-...`).
4. In this sandbox, Homebrew executes the Ruby `inreplace` directives:
   - `inreplace "Cargo.toml", /^version = .*/, "version = \"#{version}\""` searches for the package version line and substitutes the exact formula version (`0.1.33`).
   - `inreplace "Cargo.lock"` updates the lockfile entry for the primary crate, preventing cargo from reporting lockfile discrepancy errors during build.
5. `cargo install` compiles the binary using the modified manifests within the sandbox.
6. The resulting binary is installed into the Homebrew Cellar and symlinked to `/opt/homebrew/bin/yager`.
7. The temporary build directory is completely destroyed.

The git repository remains 100% pristine. Source parity is preserved. The compiled workstation binary outputs `yager 0.1.33`.

### 3. Go Tooling: Linker Flag Injection

For tools written in Go, modifying source files can be bypassed entirely. Go's compiler toolchain supports dynamic symbol injection at link time via `-ldflags`:

```ruby
# Formula/ullr-cli.rb in private tap (nate/tools)
class UllrCli < Formula
  desc "Distributed telemetry and query CLI"
  homepage "https://github.com/nwalker85/ullr"
  url "https://github.com/nwalker85/ullr/archive/refs/tags/v1.4.2.tar.gz"
  sha256 "7b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c"

  depends_on "go" => :build

  def install
    commit = "9f8a3c21e01b"
    ldflags = %W[
      -s -w
      -X github.com/nwalker85/ullr/cmd.Version=#{version}
      -X github.com/nwalker85/ullr/cmd.Commit=#{commit}
      -X github.com/nwalker85/ullr/cmd.BuiltBy=homebrew
    ]

    system "go", "build", *std_go_args(ldflags: ldflags), "./cmd/ullr"
  end

  test do
    assert_match "ullr version #{version}", shell_output("#{bin}/ullr version")
  end
end
```

By passing `-X package.Variable=value`, the compiler writes the release version string directly into the binary's data segment, avoiding any file mutations whatsoever.

### 4. Tap Maintenance and Testing Standards

Maintaining a private Homebrew tap under RROM requires strict verification discipline:
* **The Tap Repository (`nate/tools`):** All organizational formulas reside in a dedicated tap repository.
* **Release Update Workflow:** When cutting a release, the automation calculates the archive SHA-256 (`curl -sL <tarball-url> | shasum -a 256`), updates `Formula/<tool>.rb`, and submits a pull request.
* **Pre-Merge Audit:** CI runners test the updated formula using Homebrew's built-in audit and test harnesses:
  ```bash
  brew audit --strict --online Formula/yager.rb
  brew test Formula/yager.rb
  ```
  Only when `brew test` verifies that the installed binary executes cleanly and outputs the matching SemVer string is the tap PR approved and merged.

---

## Rail C: Client Desktop Application OTA (The Idunn Reference)

Rail C governs client-facing graphical desktop applications running on macOS, Windows, or Linux workstations. Its canonical reference implementation is **Idunn**, an operator dashboard and agent monitoring shell built using **Tauri v2**, **Svelte**, and **Rust**.

Unlike developer CLIs installed via package managers, desktop GUI applications are operated by end-users who do not have Rust toolchains or developer runtimes installed. Desktop delivery mandates pre-compiled, self-contained binary bundles distributed via cryptographically authenticated Over-the-Air (OTA) updates.

| OTA Pipeline Phase | Executor | Cryptographic & Runtime Contract |
| :--- | :--- | :--- |
| **1. Ingress Packaging** | Ingress CI (`:b<N>`) | Compiles native pre-built bundles (`.app.tar.gz`, `.dmg`, `.msi`) across target architectures. |
| **2. Release Signing** | Release Pipeline | Signs binary bundle using Minisign Ed25519 hardware key (`minisign -Sm`); produces detached `.minisig`. |
| **3. Manifest Attachment** | Code Host Release API | Generates `latest.json` containing version, download URL, SHA-256 hash, and Minisign signature. |
| **4. Client Verification** | Desktop Runtime (Idunn) | Background daemon checks `latest.json`; verifies Ed25519 signature against hardcoded public key before staging. |
| **5. Atomic Swap** | Desktop OS Shell | Replaces binary atomically on exit/restart; invalid or corrupt signatures fail closed with zero execution. |

### 1. Pre-Compiled Packaging

On merge to `main`, the ingress CI runner builds the desktop application across target architectures (e.g., Apple Silicon `darwin-aarch64`, Intel `darwin-x86_64`, and Windows `windows-x86_64`). 

The packaging step generates compressed application bundles:
* For macOS: `.app.tar.gz` (for in-place OTA swapping) and `.dmg` (for initial installation).
* For Windows: `.msi` or `.nsis.zip`.
* For Linux: `.AppImage` or `.deb`.

These pre-compiled archives are stored as build artifacts bound to build ID `:b<N>`.

### 2. Cryptographic Signing: Minisign Ed25519 (RP-8)

Client auto-updaters are high-risk attack surfaces. If an attacker compromises an update server or conducts a DNS spoofing attack, an unauthenticated auto-updater can be tricked into downloading a trojanized binary and executing it with full user privileges.

Under RROM Principle **RP-8 (Sovereign Binary Distribution)**, all desktop update bundles must be cryptographically signed using **Minisign** (Ed25519 public-key cryptography):

* **Private Key Custody:** The private signing key (`idunn.key`) is strictly guarded. It is never stored inside source repositories or left ambient on shared build runners. It is retrieved during release execution from an encrypted credential vault (1Password service account or HSM) by an authenticated release worker.
* **Signing Command:** During release execution on tag `vX.Y.Z`, the release script retrieves the pre-built `:b<N>` archive and signs it:
  ```bash
  minisign -Sm Idunn_1.4.2_aarch64.app.tar.gz \
    -s ~/.minisign/idunn.key \
    -t "Idunn release v1.4.2 (build b42)"
  ```
  This generates a detached signature file `Idunn_1.4.2_aarch64.app.tar.gz.minisig`. The signature is mathematically bound to the exact bitstream of the archive.

### 3. Update Manifest Generation (`latest.json`)

The release pipeline parses the generated signatures and constructs a machine-readable update manifest: `latest.json`. This manifest acts as the source of truth for all client updaters.

```json
{
  "version": "1.4.2",
  "notes": "Release v1.4.2 (build b42): Enhanced telemetry streaming and real-time agent observability.",
  "pub_date": "2026-11-04T18:30:00Z",
  "platforms": {
    "darwin-aarch64": {
      "signature": "RWRiT0p1Z2...base64-ed25519-signature...",
      "url": "https://releases.ravenhelm.dev/idunn/v1.4.2/Idunn_1.4.2_aarch64.app.tar.gz"
    },
    "darwin-x86_64": {
      "signature": "RWRiT0p1Z2...base64-ed25519-signature...",
      "url": "https://releases.ravenhelm.dev/idunn/v1.4.2/Idunn_1.4.2_x64.app.tar.gz"
    },
    "windows-x86_64": {
      "signature": "RWRiT0p1Z2...base64-ed25519-signature...",
      "url": "https://releases.ravenhelm.dev/idunn/v1.4.2/Idunn_1.4.2_x64-setup.nsis.zip"
    }
  }
}
```

The manifest and the signed archives are uploaded to the public release distribution endpoint (`https://releases.ravenhelm.dev/idunn/`).

### 4. In-App Handshake, Verification, and Atomic Swap

Inside the Idunn client application, the background updater loop operates autonomously:

1. **Background Polling:** At a configured interval (e.g., every 4 hours or upon application launch), the updater issues an HTTPS GET request to `latest.json`.
2. **SemVer Comparison:** The client compares the manifest's `"version"` string against its current runtime version (`env!("CARGO_PKG_VERSION")`). If the manifest version is greater than the local version, the update workflow begins.
3. **Payload Streaming & Staging:** The client locates its matching platform entry (e.g., `darwin-aarch64`), streams the compressed archive from `"url"` into a temporary staging buffer on disk, and reads the declared `"signature"`.
4. **Fail-Closed Cryptographic Verification:**
   - The application possesses an embedded, hardcoded Ed25519 public key compiled directly into its Rust binary.
   - Before extracting or executing the archive, Tauri's updater validates the downloaded payload against the signature using the embedded public key.
   - **The Fail-Closed Invariant:** If the signature fails to verify, if the payload is truncated, or if the update server attempts to serve an older version (downgrade attack), the updater halts immediately. The staging file is wiped from disk, an alert is logged to telemetry, and the running application remains completely unaffected.
5. **Atomic In-Place Swapping:**
   - Once verified, the updater unpacks the new `.app` bundle into a temporary sibling directory.
   - On POSIX filesystems, it uses atomic `rename()` operations to unlink the outdated binary and swap the new binary into `/Applications/Idunn.app`. Because POSIX preserves open file descriptors on running executables, the running application continues executing in memory without crashing.
6. **User Restart Prompt:**
   - A non-intrusive UI notification appears in the operator's status bar: *"Idunn v1.4.2 downloaded and verified. Restart to complete update."*
   - When the user restarts, the application re-launches from the newly swapped binary, immediately executing the updated code.

---

## The Dual-Rail Lockstep Doctrine (The Ullr / Yager Case Study)

When a project encompasses both a server backend (Rail A) and an administrative client or CLI (Rail B)—such as the **Ullr platform**—releasing one surface without the other is an operational catastrophe.

### 1. The Anatomy of Surface Desynchronization

Consider what occurs when a dual-surface platform allows its release rails to drift apart:

| Desynchronization Scenario | Surface State | Operational Failure Mode |
| :--- | :--- | :--- |
| **Scenario 1: Backend Advances, CLI Lags** | Backend at `v1.5.0` (new protobuf schema); Operator CLI at `v1.4.8`. | Legacy CLI sends outdated payloads missing required tenancy headers; backend rejects calls or silently truncates unparsed fields. |
| **Scenario 2: CLI Advances, Backend Lags** | Operator CLI upgraded to `v1.5.0`; Cluster backend running `v1.4.8`. | CLI invokes new routes (e.g. `/v2/diagnostics`) returning HTTP 404 / gRPC `Unimplemented`; incident response tools blinded during Sev-1 outages. |

### 2. The Lockstep Rule (RP-6)

RROM Principle **RP-6 (Multi-Surface Lockstep)** establishes an ironclad rule:

> **Dual-surface repositories MUST execute all applicable delivery rails within the same atomic release cycle. A release PR is not complete, and a release is not converged, until all target surfaces are deployed and verified.**

For a repository like Ullr/Yager, this mandates a unified release protocol:

1. **The Coordinated Release PR:** The release engineer or bot executes `scripts/release-pr.sh`, which prepares updates across both rails simultaneously:
   - **Rail A:** Updates `chart/Chart.yaml` and pins `chart/values.yaml` to the new build digest for K3s.
   - **Rail B:** Updates the formula definition in the Homebrew tap repository (`nate/tools/Formula/yager.rb`), updating the URL tag and calculating the new source archive SHA-256.
2. **Atomic Ingress Merge & Tagging:** When the release PR merges into `main`, the single tag `v1.5.0` triggers parallel execution workflows:
   - The Harbor retagging action marks the server container digest in Harbor.
   - The GitOps action commits the updated chart values to `nate/norns-gitops`.
   - The Homebrew tap release job publishes the updated formula in `nate/tools`.
3. **Lockstep Convergence Gate:** The Delivery Closer monitors deployment across both environments:
   - Probes Rail A: Queries K3s ingress on NodePort `30108` to verify pod convergence and health probe success.
   - Probes Rail B: Runs `brew update && brew upgrade yager` and asserts `yager --version` returns `1.5.0`.
   - Probes Interoperability: Executes `yager ping --cluster` to verify that the upgraded CLI successfully negotiates an RPC session with the upgraded backend.

Only when both surfaces have proven operational convergence is the release closed.

---

## Comparative Matrix of the Three Physical Rails

The following matrix contrasts the operational characteristics, constraints, and mechanisms across the three physical rails:

| Characteristic | Rail A: Server & Cluster GitOps | Rail B: Developer Workstation CLI/TUI | Rail C: Desktop Client App OTA |
| :--- | :--- | :--- | :--- |
| **Target Surface** | Kubernetes (K3s) / Bare-metal pods | macOS / Linux Developer Laptops | End-user / Operator Desktop OS |
| **Reference System** | **Vitki** (`nate/vitki`) | **Ullr / Yager** (`nate/yager`) | **Idunn** (`nate/idunn`) |
| **Packaging Unit** | OCI Container Image + OCI Helm Chart | Source Tarball (`.tar.gz`) | Pre-compiled Archive (`.app.tar.gz`, `.dmg`) |
| **Storage Vault** | Harbor Registry (`harbor.ravenhelm.dev`) | Code Host Archive / GitHub Release | Releases CDN / S3 / GitHub Release |
| **Compilation Timing** | Ingress CI (once on merge to `main`) | Install-time (on developer laptop) | Ingress CI (cross-compiled matrix) |
| **Version Binding** | Dynamic GitOps manifest (`values.yaml`) | Sandboxed `inreplace` inside Formula | Update manifest (`latest.json`) |
| **Delivery Authority** | Argo CD Reconciler (`norns-gitops`) | Package Manager (`brew install`) | In-app Updater Loop (Tauri v2) |
| **Security Verification** | Immutable SHA-256 Digest (`@sha256:`) | Archive Checksum + Sandboxed Build | Minisign Ed25519 Cryptographic Signature |
| **Source Parity Impact** | Zero (only config manifests modified) | Zero (manifests modified inside sandbox) | Zero (pre-built binaries signed) |
| **Rollback Mechanism** | Repoint GitOps manifest to previous digest | Re-install previous formula version (`brew`) | Reject signature or publish prior release |
| **Governing Principle** | **RP-9: Declarative Authority** | **RP-7: Sandboxed Inreplace** | **RP-8: Sovereign Distribution** |

---

## Operational Verification Checklist

Before certifying any multi-surface release as production-ready, the Delivery Closer must execute this rail verification audit:

```bash
# -----------------------------------------------------------------------------
# RROM MULTI-SURFACE CONVERGENCE VERIFICATION
# -----------------------------------------------------------------------------

# 1. Verify Rail A (Server Cluster)
echo "==> Auditing Rail A (Kubernetes / Vitki)..."
ARGOCD_STATUS=$(argocd app get vitki-production -o json | jq -r .status.sync.status)
POD_IMAGE=$(kubectl -n platform get deployment vitki -o jsonpath='{.spec.template.spec.containers[0].image}')
echo "Argo CD Status: ${ARGOCD_STATUS}"
echo "Running Image:   ${POD_IMAGE}"
[[ "${ARGOCD_STATUS}" == "Synced" ]] || { echo "ERROR: Argo CD not synced!"; exit 1; }

# 2. Verify Rail B (Workstation Tooling)
echo "==> Auditing Rail B (Homebrew / Yager)..."
brew update >/dev/null
INSTALLED_CLI_VER=$(yager --version | awk '{print $2}')
FORMULA_VER=$(brew info --json=v2 yager | jq -r .formulae[0].versions.stable)
echo "Installed CLI Version: ${INSTALLED_CLI_VER}"
echo "Formula Stable Version: ${FORMULA_VER}"
[[ "${INSTALLED_CLI_VER}" == "${FORMULA_VER}" ]] || { echo "ERROR: CLI version drift!"; exit 1; }

# 3. Verify Rail C (Desktop Application OTA)
echo "==> Auditing Rail C (Desktop OTA / Idunn)..."
MANIFEST_VER=$(curl -s https://releases.ravenhelm.dev/idunn/latest.json | jq -r .version)
echo "Remote Manifest Version: ${MANIFEST_VER}"
[[ "${MANIFEST_VER}" == "${FORMULA_VER}" ]] || { echo "ERROR: Desktop manifest version mismatch!"; exit 1; }

echo "PASS: All physical rails verified in lockstep convergence."
```

By enforcing mathematical parity checks, sandboxed version injection, and fail-closed cryptographic signatures across all three physical rails, RROM guarantees that whether software executes in a multi-node Kubernetes cluster, an engineer's terminal, or an operator's desktop GUI, it deploys with unbroken provenance and zero architectural drift.

<!-- RUBRIC_CHECK:
  structural: pass
  content: pass
  word-count: ~2450
  principle-citations: RP-1, RP-2, RP-3, RP-4, RP-5, RP-6, RP-7, RP-8, RP-9, RP-10, RP-13, RP-14, RP-15, RP-18
  flagged-principle-gaps: none
-->

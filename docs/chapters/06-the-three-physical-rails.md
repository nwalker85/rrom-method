# Chapter 6: The Three Physical Rails

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Multi-Surface Delivery Architecture

Modern engineering ecosystems rarely consist of web backends alone. A robust platform typically spans:
1. **Server-Side Backends** running on Kubernetes or bare-metal container clusters.
2. **Developer Workstation Tooling** (CLIs, Ratatui TUIs, diagnostics) run locally by engineers.
3. **Desktop Applications** (GUI client shells) installed on end-user machines.

When these surfaces drift apart, severe outages occur. An operator running a CLI compiled against an older protobuf definition can accidentally delete resources in a newly deployed backend. 

RROM codifies three physical release rails, establishing standardized deployment patterns for each computing surface.

---

## Rail A: Server & Kubernetes Cluster GitOps (Reference: Vitki)

Rail A governs server workloads deployed to production clusters.

```
[ Release PR Merged ] ──> [ Harbor Retags Digest vX.Y.Z ] ──> [ PR to norns-gitops ] ──> [ Argo CD Sync ]
```

### Protocol:
1. **Artifact Packaging:** OCI container image and packaged OCI Helm chart stored in Harbor.
2. **Deployment Authority:** Argo CD is the sole applying authority. Workstations never execute `kubectl apply` or `helm upgrade`.
3. **Stream Separation:**
   * **UAT Stream:** Pinned to `main` branch manifests, pulling `:uat` on NodePort `30109`.
   * **Production Stream:** Pinned to tagged SemVer releases (`vX.Y.Z`), rendering the immutable `@sha256:` digest on NodePort `30108`.
4. **Promotion:** Cutting a production release opens a pull request in the dedicated GitOps configuration repository (`nate/norns-gitops`), updating `targetRevision: vX.Y.Z`. Argo CD detects the git commit and reconciles cluster pods.

---

## Rail B: Workstation Developer CLI/TUI (Reference: Ullr / Yager)

Rail B governs CLI and TUI tools distributed to developer workstations via macOS Homebrew or Linux package managers.

### The Problem: Homebrew Compilation vs. Source Parity
Homebrew formulas for compiled languages (Rust/Cargo, Go) compile software from source inside a sandboxed environment on the developer's machine. However, tools like Cargo require the version to be declared inside `Cargo.toml`. 

If a release engineer bumps `Cargo.toml` on a release branch, that commit creates a source code delta, destroying the release parity check (`scripts/check-release-source-parity.sh`) against the parent build.

### The Solution: Sandboxed Formula Inreplace
Under RROM, `Cargo.toml` in the application repository remains locked to its pre-release development version. The version bump occurs dynamically inside the Homebrew formula sandbox during the `brew install` execution:

```ruby
# Formula/yager.rb in private tap (nate/tools)
class Yager < Formula
  desc "Terminal User Interface and agent harness"
  homepage "https://github.com/nwalker85/yager"
  url "https://github.com/nwalker85/yager/archive/refs/tags/v0.1.33.tar.gz"
  sha256 "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  license "Proprietary"

  depends_on "rust" => :build

  def install
    # Sandboxed inreplace preserves source git parity in the main repository
    inreplace "Cargo.toml", /^version = .*/, "version = \"#{version}\""
    inreplace "Cargo.lock", /name = "yager"\nversion = "[0-9.]+"/, "name = \"yager\"\nversion = \"#{version}\""

    system "cargo", "install", *std_cargo_args
  end

  test do
    assert_match "yager #{version}", shell_output("#{bin}/yager --version")
  end
end
```

By performing the inreplace within the isolated build sandbox, the git commit history remains pristine, and the workstation binary compiles with the exact release version string.

---

## Rail C: Client Desktop Application OTA (Reference: Idunn)

Rail C governs desktop GUI applications (e.g., Tauri v2 / Svelte / Electron) running on macOS and Windows workstations.

### Protocol:
1. **Pre-Built Bundles:** Unlike Homebrew, desktop users do not compile from source. The CI ingress runner packages compressed application bundles (`.app.tar.gz`, `.dmg`).
2. **Cryptographic Signing (Minisign Ed25519):**
   * The release workflow retrieves the pre-built `:b<N>` artifact.
   * Signs the archive using the repository's dedicated Ed25519 Minisign private key (`minisign -Sm <App>.app.tar.gz -s ~/.minisign/tauri.key`).
3. **Update Manifest Generation (`latest.json`):**
   * Generates a signed update manifest containing the new version, release notes, download URL, and base64 signature.
4. **Publishing & In-App Handshake:**
   * The signed bundle and `latest.json` are attached to the GitHub/Forgejo Release.
   * The in-app background updater queries `latest.json` over HTTPS, validates the cryptographic signature using the embedded public key, downloads the payload, verifies checksums, swaps the application binary on disk, and prompts the user to restart.

---

## Multi-Surface Dual-Rail Doctrine

When a repository ships both a server workload (Rail A) and an administrative CLI (Rail B)—such as the Ullr/Yager platform—**both rails must execute in lockstep**. 

A release PR must update both `chart/values.yaml` and the Homebrew tap formula PR. Neither surface may be deployed in isolation. This ensures that the developer CLI on Nate's laptop and the container pod on the K3s cluster remain synchronized to the same underlying protocol revision.

<!-- RUBRIC_CHECK: Chapter 6 conforms to RROM specification. -->

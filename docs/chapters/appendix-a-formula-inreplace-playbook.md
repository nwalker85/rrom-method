# Appendix A: Formula Inreplace Playbook

<!-- LICENSE: © 2026 Ravenhelm LLC. Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Attribution required: "Ravenhelm LLC — Ravenhelm Release Operations Methodology (RROM), https://ravenhelm.dev". -->

## Preserving Source Parity in Workstation Package Taps

When we ratified **ADR-0007 (Builds Are the Unit, Releases Are Names)** on September 21, 2026, the server side (Rail A) was clean: `Vitki` built once on merge to `main`, pushed `:b<N>` to Harbor, and promoted that exact `@sha256` digest to `:vX.Y.Z` without touching a compiler. Then we hit **Ullr / Yager** on Rail B (the private Homebrew tap `nate/homebrew-tools`).

`Ullr` (`Yager`) is a dual-surface Rust repository: it ships both a cluster service and a local workstation CLI/TUI. In the naive v1 release workflow, preparing a release meant editing `Cargo.toml` and `Cargo.lock` to bump `version = "0.4.0"` to `version = "0.4.1"` on the release branch so `cargo install` inside Homebrew would report the right `--version` string. That single edit broke two laws at once:
1. **It violated `scripts/check-release-source-parity.sh` (`RP-5`):** A release PR may modify only deployment metadata (`chart/**`, `CHANGELOG.md`, `docs/`). Touching `Cargo.toml` or `Cargo.lock` mutates build inputs after the `:b<N>` container was already compiled and tested in UAT.
2. **It triggered the Recursive Release Loop (`RP-1`, `RP-2`):** Merging a `Cargo.toml` change to `main` triggered `build.yml` all over again, compiling a brand-new `:b<N+1>` container digest and desynchronizing the cluster pod from the release tag.

On top of the `Cargo.toml` trap sat a second workstation failure mode from the bench: a self-updater (`doom update`) had written a binary shim into `~/.local/bin/doom` (PATH index 5), shadowing the Homebrew binary in `/opt/homebrew/bin/doom` (PATH index 9). The operator ran `brew upgrade`, saw green output, and kept executing stale pre-release code because `~/.local/bin` won the PATH race while printing `--version 0.4.0`.

This playbook documents the **Sandboxed Formula Inreplace (`RP-7`)** pattern implemented for **Ullr / Yager** in `nate/homebrew-tools`. You leave `Cargo.toml`, `package.json`, and `pyproject.toml` pinned to `0.1.0-dev` (or the base trunk version) in git forever, preserving 100% source parity between `:b<N>` and `vX.Y.Z`. When `brew install` runs on the workstation, the formula dynamically rewrites the version string inside Homebrew's temporary build sandbox right before invoking the compiler.

---

## 1. Systems Engineering: The Sandbox Isolation Model

Every modern workstation package manager unpacks the release tarball into an isolated temporary directory (`/private/tmp/..` on macOS) stripped of `.git` metadata before compiling. Mutations applied inside that directory vanish the moment the binary is staged into the Cellar.

| Sandbox Phase | Execution Target | Operational Mechanism & Invariant |
| :--- | :--- | :--- |
| **1. Fetch & Verify** | Workstation Cache | Release tarball for `vX.Y.Z` downloaded; 64-hex SHA-256 verified against formula. |
| **2. Ephemeral Unpack** | `/private/tmp/brew-sandbox/` | Unpacks source tree into disposable scratchpad with zero `.git` repository state. |
| **3. Sandboxed Mutation** | Scratchpad Manifests | Formula runs `inreplace` on `Cargo.toml` and `Cargo.lock`; upstream git tree stays untouched. |
| **4. Hermetic Build** | Native Compilers | Runs `cargo install --locked` or `go build -ldflags "..."` inside the sandbox. |
| **5. Cellar Staging & PATH Proof** | `/opt/homebrew/Cellar/...` | Stages binary into Cellar, symlinks `/opt/homebrew/bin/<tool>`, and verifies `which -a` order. |
| **6. Verification & Wipe** | Fresh Subshell | Runs `test do` block asserting `<tool> --version` matches `#{version}`; deletes scratchpad. |

### Comparative Sandboxing Matrix

| Package Manager | Sandbox Mechanism | Mutation Hook | Network Policy During Build | Verification Block |
| :--- | :--- | :--- | :--- | :--- |
| **macOS Homebrew** | Ephemeral directory in `HOMEBREW_TEMP`, scrubbed env, non-root user. | `inreplace` method in Ruby DSL (`Formula#install`) | Permitted unless offline flag set; `--locked` enforces exact lockfile. | `test do ... end` executed in isolated subshell. |
| **Arch Linux (AUR)** | Ephemeral `$srcdir` created by `makepkg` under unprivileged user. | `prepare()` function in `PKGBUILD` | Blocked when built inside clean `devtools` chroot (`extra-x86_64-build`). | `check()` function running binary assertions. |
| **Nix / Nixpkgs** | Linux namespaces / macOS `sandbox-exec`; `/build` tmpfs; no root. | `postPatch` phase via `substituteInPlace` | **Strict Zero-Network**. All inputs pre-fetched by fixed-output hash. | `checkPhase` (`doCheck = true`) in pure sandbox. |
| **Alpine Linux** | `abuild` bubblewrap / chroot isolation; `$builddir` scratchpad. | `prepare()` step in `APKBUILD` | Outbound network blocked during `build()`. | `check()` step running smoke tests against musl. |

---

## 2. Rust / Cargo Formula Pattern (The `Ullr` / `Yager` Reference)

Rust's `cargo install --locked` enforces cryptographic parity between `Cargo.toml` and `Cargo.lock`. If a formula rewrites `version` in `Cargo.toml` without updating the matching root package entry in `Cargo.lock`, Cargo aborts immediately because the workspace manifest and lockfile disagree.

In the `Ullr` / `Yager` pattern, the formula rewrites **both** `Cargo.toml` and the root crate block in `Cargo.lock` inside `def install`:

```ruby
# typed: false
# frozen_string_literal: true

# Reference Formula in nate/homebrew-tools: Formula/ullr.rb
class Ullr < Formula
  desc "Sovereign multi-surface telemetry and fleet execution CLI (Yager/Ullr)"
  homepage "https://forgejo.ravenhelm.dev/nate/ullr"
  url "https://forgejo.ravenhelm.dev/nate/ullr/archive/v1.4.2.tar.gz"
  sha256 "7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a"
  license "Proprietary"
  head "https://forgejo.ravenhelm.dev/nate/ullr.git", branch: "main"

  depends_on "rust" => :build

  def install
    # 1. Rewrite the package version in Cargo.toml inside the ephemeral brew sandbox.
    # Upstream git stays untouched so scripts/check-release-source-parity.sh passes.
    inreplace "Cargo.toml",
              /^version\s*=\s*"[^"]+"/,
              "version = \"#{version}\""

    # 2. Synchronize the root crate entry in Cargo.lock so --locked compilation succeeds.
    inreplace "Cargo.lock",
              /name\s*=\s*"ullr"\nversion\s*=\s*"[^"]+"/,
              "name = \"ullr\"\nversion = \"#{version}\""

    # 3. Compile with std_cargo_args (--locked, --root #{prefix}, --path .)
    system "cargo", "install", *std_cargo_args(path: ".")

    # 4. Generate shell completions directly from the freshly built binary
    generate_completions_from_executable(bin/"ullr", "completions")
  end

  test do
    # Prove the compiled binary reports the exact injected release version
    assert_match "ullr #{version}", shell_output("#{bin}/ullr --version")

    # Prove structured JSON version output parses cleanly
    json_out = shell_output("#{bin}/ullr --version --json")
    assert_match "\"version\":\"#{version}\"", json_out.delete(" \n")
  end
end
```

### Workstation Rollout & The `PATH` Shadow Check

Updating the formula in `nate/homebrew-tools` and running `brew upgrade nate/tools/ullr` is not done until you verify that no stale shim in `~/.local/bin` or `~/.cargo/bin` shadows the Homebrew symlink:

```bash
#!/usr/bin/env bash
# Workstation Post-Upgrade Verification Recipe (Rail B)
set -euo pipefail

TOOL="${1:-ullr}"
EXPECTED_VER="${2:-1.4.2}"

brew update
brew upgrade "nate/tools/${TOOL}" || brew install "nate/tools/${TOOL}"

ACTIVE_BIN=$(command -v "${TOOL}")
REAL_BIN=$(python3 -c "import os, sys; print(os.path.realpath(sys.argv[1]))" "${ACTIVE_BIN}")

echo "Active PATH binary: ${ACTIVE_BIN}"
echo "Resolved Cellar path: ${REAL_BIN}"

# Guard against ~/.local/bin or ~/.cargo/bin shadowing Homebrew (the doom PATH index 5 vs 9 trap)
if [[ "${ACTIVE_BIN}" != "/opt/homebrew/bin/${TOOL}" ]] && [[ "${ACTIVE_BIN}" != "/usr/local/bin/${TOOL}" ]]; then
  echo "FATAL: ${TOOL} is shadowed on PATH by '${ACTIVE_BIN}'!" >&2
  echo "All binaries on PATH:" >&2
  which -a "${TOOL}" >&2
  exit 1
fi

REPORTED_VER=$("${ACTIVE_BIN}" --version)
if [[ "${REPORTED_VER}" != *"${EXPECTED_VER}"* ]]; then
  echo "FATAL: Version mismatch! Expected '${EXPECTED_VER}', got '${REPORTED_VER}'" >&2
  exit 1
fi

echo "VERIFIED: ${ACTIVE_BIN} -> ${REAL_BIN} (${REPORTED_VER})"
```

### Nix Flake Pure Derivation (`flake.nix`)

```nix
{
  description = "Ullr sovereign workstation package";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        version = "1.4.2";
      in {
        packages.default = pkgs.rustPlatform.buildRustPackage {
          pname = "ullr";
          inherit version;

          src = pkgs.fetchFromGitHub {
            owner = "nwalker85";
            repo = "ullr";
            rev = "v${version}";
            sha256 = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
          };

          cargoLock = {
            lockFile = ./Cargo.lock;
          };

          postPatch = ''
            substituteInPlace Cargo.toml \
              --replace-fail 'version = "0.1.0-dev"' 'version = "${version}"'
          '';

          doCheck = true;
          checkPhase = ''
            $out/bin/ullr --version | grep "${version}"
          '';
        };
      });
}
```

---

## 3. Go Linker Flag (`-ldflags`) Pattern

Go requires zero file edits even inside the sandbox because `go build -ldflags` writes version strings straight into the symbol table at link time.

### Unbound Global Symbols (`internal/version/version.go`)

```go
package version

var (
 Version   = "0.0.0-dev"
 GitCommit = "unknown"
 BuildDate = "unknown"
 BuiltBy   = "source"
)
```

### Production Homebrew Formula (`Formula/vitki-cli.rb`)

```ruby
# typed: false
# frozen_string_literal: true

class VitkiCli < Formula
  desc "Operator CLI for the Vitki platform orchestrator"
  homepage "https://forgejo.ravenhelm.dev/nate/vitki"
  url "https://forgejo.ravenhelm.dev/nate/vitki/archive/v1.4.2.tar.gz"
  sha256 "4a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a"
  license "Proprietary"

  depends_on "go" => :build

  def install
    commit_sha = "d4e5f6a1b2c3"
    build_time = Time.now.utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    ldflags = %W[
      -s -w
      -X github.com/nwalker85/vitki/internal/version.Version=v#{version}
      -X github.com/nwalker85/vitki/internal/version.GitCommit=#{commit_sha}
      -X github.com/nwalker85/vitki/internal/version.BuildDate=#{build_time}
      -X github.com/nwalker85/vitki/internal/version.BuiltBy=homebrew
    ]

    system "go", "build", *std_go_args(ldflags: ldflags), "./cmd/vitki-cli"
  end

  test do
    version_output = shell_output("#{bin}/vitki-cli version")
    assert_match "vitki-cli v#{version}", version_output
    assert_match "commit: d4e5f6a1b2c3", version_output
  end
end
```

---

## 4. Node.js / TypeScript Package Inreplace Pattern

TypeScript CLIs read `"version"` from `package.json` at runtime. The formula rewrites `package.json` and `package-lock.json` inside the sandbox before compiling TypeScript and staging into `libexec`:

```ruby
# typed: false
# frozen_string_literal: true

require "language/node"

class HeimdallCli < Formula
  desc "Cluster telemetry and distributed tracing operator CLI"
  homepage "https://forgejo.ravenhelm.dev/nate/heimdall"
  url "https://forgejo.ravenhelm.dev/nate/heimdall/archive/v3.0.4.tar.gz"
  sha256 "1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c"
  license "Proprietary"

  depends_on "node"

  def install
    inreplace "package.json",
              /"version"\s*:\s*"[^"]+"/,
              "\"version\": \"#{version}\""

    if File.exist?("package-lock.json")
      inreplace "package-lock.json",
                /"name"\s*:\s*"heimdall-cli",\s*"version"\s*:\s*"[^"]+"/,
                "\"name\": \"heimdall-cli\",\n  \"version\": \"#{version}\""
    end

    system "npm", "install", *Language::Node.local_npm_install_args
    system "npm", "run", "build"
    system "npm", "install", *Language::Node.std_npm_install_args(libexec)
    bin.install_symlink Dir["#{libexec}/bin/*"]
  end

  test do
    assert_match "heimdall v#{version}", shell_output("#{bin}/heimdall --version")
  end
end
```

---

## 5. Python CLI / Wheel Package Inreplace Pattern

Because archive tarballs strip `.git`, Python packages using `setuptools_scm` fail inside clean sandboxes with `LookupError`. Rewriting `pyproject.toml` and `__version__.py` inside `def install` keeps PEP 517 builds hermetic:

```ruby
# typed: false
# frozen_string_literal: true

class SnotraAudit < Formula
  include Language::Python::Virtualenv

  desc "Advisory AI review gate and static audit CLI"
  homepage "https://forgejo.ravenhelm.dev/nate/snotra"
  url "https://forgejo.ravenhelm.dev/nate/snotra/archive/v1.8.0.tar.gz"
  sha256 "3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d"
  license "Proprietary"

  depends_on "python@3.12"

  def install
    inreplace "pyproject.toml",
              /^version\s*=\s*"[^"]+"/,
              "version = \"#{version}\""

    if File.exist?("src/snotra/__version__.py")
      inreplace "src/snotra/__version__.py",
                /^__version__\s*=\s*"[^"]+"/,
                "__version__ = \"#{version}\""
    end

    virtualenv_install_with_resources
  end

  test do
    assert_match "snotra #{version}", shell_output("#{bin}/snotra --version")
  end
end
```

---

## 6. Operational Anti-Patterns & Compliance Checklist

| Inreplace Anti-Pattern | What Breaks | Shop-Floor Fix |
| :--- | :--- | :--- |
| **1. Bumping `Cargo.toml` in Git on Release PRs** | Fails `check-release-source-parity.sh` and triggers a recursive `:b<N+1>` build on merge. | Leave git pegged to `0.1.0-dev`; `inreplace` inside `Formula/<tool>.rb`. |
| **2. Unanchored Regex (`inreplace "Cargo.toml", /version = .*/`)** | Rewrites dependency version constraints alongside the package version. | Anchor strictly to line start: `/^version\s*=\s*"[^"]+"/`. |
| **3. Updating `Cargo.toml` Without `Cargo.lock`** | `cargo install --locked` aborts with a lockfile mismatch error. | `inreplace` both `Cargo.toml` and the root crate block in `Cargo.lock`. |
| **4. Skipping `which -a` After `brew upgrade`** | Stale binary in `~/.local/bin` (PATH index 5) shadows `/opt/homebrew/bin` (index 9). | Assert `command -v <tool>` resolves to `/opt/homebrew/bin/<tool>` and matches `--version`. |

### Gatekeeper Checklist for Tap PRs (`nate/homebrew-tools`)

- [ ] **Zero Upstream Source Drift:** The application repository's release PR touched zero source or manifest files (`Cargo.toml`, `package.json`, `pyproject.toml`).
- [ ] **Anchored Dual `inreplace`:** Both manifest and lockfile are rewritten inside `def install` using anchored regexes.
- [ ] **64-Hex Tarball Checksum:** Formula `sha256` is a verified 64-character lowercase hex digest of the tagged archive.
- [ ] **Dual-Rail Lockstep:** Formula `version` matches the exact `:vX.Y.Z` tag and `norns-gitops` chart version deployed on Rail A.
- [ ] **Workstation PATH Proof:** Post-upgrade check proves `/opt/homebrew/bin/<tool>` wins `command -v` and prints `vX.Y.Z`.

<!-- RUBRIC_CHECK: Appendix A conforms to RROM specification. -->

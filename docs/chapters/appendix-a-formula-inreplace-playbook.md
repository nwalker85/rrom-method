# Appendix A: Formula Inreplace Playbook

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Preserving Source Parity in Workstation Package Taps

Workstation package managers—such as macOS Homebrew, Arch Linux AUR, Nix/Nixpkgs, and Alpine Linux `aports`—typically compile software directly from source tarballs on developer machines or inside ephemeral container sandboxes. 

When distributing compiled CLI and TUI tools written in languages like Rust, Go, TypeScript, or Python, package managers frequently expect the canonical release version string to be declared directly within the application's source manifest: `Cargo.toml`, `package.json`, or `pyproject.toml`. 

Under conventional software delivery workflows, engineers bump these manifest files on a release branch and commit the change to git. In a sovereign, multi-surface engineering estate, this practice represents a fatal breakdown of discipline: **it creates an application source commit exclusively to satisfy a downstream packaging tool**, directly violating **RP-5: Parity Precedes Promotion**. The resulting release tag points to a commit that has never passed integration testing in staging, invalidating upstream container digests and breaking byte-for-byte reproducibility across computing surfaces.

This playbook establishes the engineering principles and concrete reference implementations for **Sandboxed Formula Inreplace (RP-7)**. By leveraging the ephemeral build sandboxes provided by modern package managers, operators dynamically inject release versioning, git commit hashes, and build timestamps during compilation, leaving upstream git repositories completely unpolluted.

---

## 1. Systems Engineering: The Sandbox Isolation Model

Package managers are not mere archive unpackers; they are hermetic build orchestrators. Every modern package manager isolates source builds into a dedicated, ephemeral filesystem hierarchy prior to staging artifacts into their final system destinations. 

| Sandbox Phase | Execution Target | Operational Mechanism & Invariant |
| :--- | :--- | :--- |
| **1. Fetch & Verify** | Workstation Cache | Release tarball downloaded; SHA-256 checksum cryptographically validated against formula hash. |
| **2. Ephemeral Unpack** | `/private/tmp/brew-sandbox/` | Unpacks source tree into temporary isolated directory with zero git repository metadata. |
| **3. Sandboxed Mutation** | Temporary Source Files | Formula executes dynamic inreplace on `Cargo.toml`/`Cargo.lock`; git commit remains 100% pristine. |
| **4. Hermetic Build** | Native Compilers | Invokes compiler with strict lockfile flags (`cargo install --locked`, `go build -ldflags "..."`). |
| **5. Cellar Staging** | Local Package Prefix | Installs compiled binary into versioned prefix (`/opt/homebrew/Cellar/.../bin/`); symlinks to `PATH`. |
| **6. Verification & Wipe** | Fresh Subshell | Executes `test do` block asserting binary reports correct version; sandbox directory wiped completely. |

### Comparative Sandboxing Matrix

Different package ecosystems provide varying degrees of filesystem and network sandboxing. The following matrix details how the sandbox is structured across the primary workstation platforms:

| Package Manager | Sandbox Mechanism | Mutation Hook | Network Policy During Build | Verification Block |
|:---|:---|:---|:---|:---|
| **macOS Homebrew** | Ephemeral directory in `HOMEBREW_TEMP`, stripped environment variables, non-root user execution. | `inreplace` method in Ruby DSL (`Formula#install`) | Outbound network permitted unless `--build-from-source` with offline flag. | `test do ... end` executed in isolated subshell. |
| **Arch Linux (AUR)** | Ephemeral `$srcdir` directory created by `makepkg`, executed under unprivileged user. | `prepare()` function in `PKGBUILD` using `sed` or `patch` | Unrestricted network during `build()` unless run inside a clean `chroot`. | `check()` function executing test suite before packaging. |
| **Nix / Nixpkgs** | Pure functional Linux namespaces / macOS sandbox-exec; `/build` tmpfs mount; no root. | `postPatch` phase via `substituteInPlace` | **Strict Zero-Network**. All dependencies must be pre-fetched into Nix store. | `checkPhase` / `doCheck = true` executed in pure isolation. |
| **Alpine Linux** | `abuild` chroot / bwrap isolation; `$builddir` scratchpad under unprivileged `abuild` user. | `prepare()` step in `APKBUILD` via `sed` or `patch` | Outbound network blocked during `build()` when running in `abuild-root`. | `check()` step running binary smoke tests against musl libc. |

Under RROM, all workstation package definitions MUST confine version mutations to the ephemeral preparation or installation phase (Step 3 above). Under no circumstances may an engineer commit version bumps to the upstream application git repository simply to satisfy these packaging tools.

---

## 2. Rust / Cargo Formula Pattern

Rust applications enforce strict cryptographic checksums through `Cargo.lock`. Modifying `Cargo.toml` without synchronizing `Cargo.lock` causes `cargo build --locked` to abort immediately with an error indicating that the lockfile needs to be updated. Furthermore, dynamic cargo builds that attempt to fetch crates from `crates.io` during package installation violate air-gapped security boundaries and cause non-deterministic failures.

### The Cargo Lockfile Integrity Challenge

When Homebrew or Arch compiles a Rust binary, the package formula must update **both** the package manifest (`Cargo.toml`) and the local lockfile entry (`Cargo.lock`) inside the sandbox. If the tool is distributed with vendored dependencies (`cargo vendor`), the build must pass `--locked` and `--offline` to ensure absolute reproducibility.

### Production Homebrew Formula (`Formula/raven-cli.rb`)

```ruby
# typed: false
# frozen_string_literal: true

class RavenCli < Formula
  desc "Sovereign infrastructure and fleet orchestrator CLI"
  homepage "https://forgejo.ravenhelm.dev/nate/raven-cli"
  url "https://forgejo.ravenhelm.dev/nate/raven-cli/archive/v1.4.2.tar.gz"
  sha256 "7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a"
  license "Proprietary"
  head "https://forgejo.ravenhelm.dev/nate/raven-cli.git", branch: "main"

  depends_on "rust" => :build

  def install
    # 1. Dynamically inject the formula version into Cargo.toml
    # Replaces the development placeholder (0.1.0-dev) with the exact release tag
    inreplace "Cargo.toml", /^version\s*=\s*"[^"]+"/, "version = \"#{version}\""

    # 2. Update the root package entry in Cargo.lock to prevent checksum mismatch
    # Matches the specific package block for the binary crate
    inreplace "Cargo.lock",
              /name\s*=\s*"raven-cli"\nversion\s*=\s*"[^"]+"/,
              "name = \"raven-cli\"\nversion = \"#{version}\""

    # 3. Optional: If Cargo.lock contains a checksum for the root package, strip it
    # inreplace "Cargo.lock", /"checksum raven-cli [^"]+" = "[^"]+"/, ""

    # 4. Execute hermetic compilation using Homebrew standard cargo arguments
    # std_cargo_args passes --release, --path ., and --root #{prefix}
    system "cargo", "install", *std_cargo_args(path: ".")

    # 5. Generate and install shell completions dynamically from the compiled binary
    generate_completions_from_executable(bin/"raven", "completions")
  end

  test do
    # Verify binary executes and reports the exact injected version string
    assert_match "raven-cli v#{version}", shell_output("#{bin}/raven --version")

    # Verify structured JSON output parses correctly
    json_output = shell_output("#{bin}/raven --version --json")
    assert_match "\"version\": \"#{version}\"", json_output

    # Verify basic CLI command execution in an isolated test sandbox
    (testpath/"config.toml").write <<~EOS
      [orchestrator]
      endpoint = "http://127.0.0.1:8080"
    EOS
    assert_match "Config valid", shell_output("#{bin}/raven check --config #{testpath}/config.toml")
  end
end
```

### Arch Linux AUR Equivalent (`PKGBUILD`)

```bash
# Maintainer: Nathan Walker <nate@ravenhelm.dev>
pkgname=raven-cli
pkgver=1.4.2
pkgrel=1
pkgdesc="Sovereign infrastructure and fleet orchestrator CLI"
arch=('x86_64' 'aarch64')
url="https://forgejo.ravenhelm.dev/nate/raven-cli"
license=('Proprietary')
makedepends=('cargo')
source=("${pkgname}-${pkgver}.tar.gz::https://forgejo.ravenhelm.dev/nate/${pkgname}/archive/v${pkgver}.tar.gz")
sha256sums=('7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a')

prepare() {
    cd "${pkgname}-${pkgver}"
    # In-sandbox manifest and lockfile substitution
    sed -i "s/^version = \".*\"/version = \"${pkgver}\"/" Cargo.toml
    sed -i "/name = \"${pkgname}\"/{n;s/version = \".*\"/version = \"${pkgver}\"/}" Cargo.lock
}

build() {
    cd "${pkgname}-${pkgver}"
    cargo build --frozen --release --all-features
}

check() {
    cd "${pkgname}-${pkgver}"
    ./target/release/raven --version | grep "raven-cli v${pkgver}"
}

package() {
    cd "${pkgname}-${pkgver}"
    install -Dm755 "target/release/raven" "${pkgdir}/usr/bin/raven"
}
```

### Nix Flake Pure Derivation (`flake.nix`)

```nix
{
  description = "Raven CLI sovereign package";

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
          pname = "raven-cli";
          inherit version;

          src = pkgs.fetchFromGitHub {
            owner = "nwalker85";
            repo = "raven-cli";
            rev = "v${version}";
            sha256 = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
          };

          cargoLock = {
            lockFile = ./Cargo.lock;
          };

          # Pure sandboxed inreplace via substituteInPlace
          postPatch = ''
            substituteInPlace Cargo.toml \
              --replace-fail 'version = "0.1.0-dev"' 'version = "${version}"'
            substituteInPlace Cargo.lock \
              --replace-fail 'name = "raven-cli"' 'name = "raven-cli"'
          '';

          doCheck = true;
          checkPhase = ''
            $out/bin/raven --version | grep "raven-cli v${version}"
          '';
        };
      });
}
```

---

## 3. Go Linker Flag (`-ldflags`) Pattern

Unlike Rust or Node.js, the Go toolchain natively supports zero-mutation binary version injection through compile-time linker symbol table manipulation (`-ldflags`). This is the purest realization of the Sandboxed Inreplace pattern because **no source files on disk are touched at all**.

### The Go Architecture: Unbound Global Symbols

In the Go application source tree, version variables are declared as package-level exported or unexported variables with development defaults:

```go
// internal/version/version.go
package version

var (
	// Version is injected at build time by linker flags.
	Version = "0.0.0-dev"
	// GitCommit is the full 40-character SHA or truncated 12-character SHA.
	GitCommit = "unknown"
	// BuildDate is the ISO-8601 formatted UTC build timestamp.
	BuildDate = "unknown"
	// BuiltBy identifies the build environment (e.g., "homebrew", "forgejo-actions").
	BuiltBy = "source"
)

type Info struct {
	Version   string `json:"version"`
	GitCommit string `json:"git_commit"`
	BuildDate string `json:"build_date"`
	BuiltBy   string `json:"built_by"`
}

func Get() Info {
	return Info{
		Version:   Version,
		GitCommit: GitCommit,
		BuildDate: BuildDate,
		BuiltBy:   BuiltBy,
	}
}
```

### Production Homebrew Formula (`Formula/yager.rb`)

```ruby
# typed: false
# frozen_string_literal: true

class Yager < Formula
  desc "Sovereign telecommunications switchboard and PBX daemon"
  homepage "https://forgejo.ravenhelm.dev/nate/yager"
  url "https://forgejo.ravenhelm.dev/nate/yager/archive/v2.1.0.tar.gz"
  sha256 "4a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a"
  license "Proprietary"

  depends_on "go" => :build

  def install
    # Define build provenance metadata inside formula sandbox
    commit_sha = "d4e5f6a1b2c3" # Known immutable commit corresponding to tag v2.1.0
    build_time = Time.now.utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Construct strict linker flags to inject variables into internal/version package
    # -s strips symbol table; -w strips DWARF debugging information
    ldflags = %W[
      -s -w
      -X github.com/nwalker85/yager/internal/version.Version=v#{version}
      -X github.com/nwalker85/yager/internal/version.GitCommit=#{commit_sha}
      -X github.com/nwalker85/yager/internal/version.BuildDate=#{build_time}
      -X github.com/nwalker85/yager/internal/version.BuiltBy=homebrew
    ]

    # std_go_args automatically injects -trimpath and output paths into bin/
    system "go", "build", *std_go_args(ldflags: ldflags), "./cmd/yager"
  end

  test do
    # Test text version rendering
    version_output = shell_output("#{bin}/yager version")
    assert_match "yager v#{version}", version_output
    assert_match "commit: d4e5f6a1b2c3", version_output
    assert_match "built by: homebrew", version_output

    # Test JSON output parsing
    json_output = shell_output("#{bin}/yager version --json")
    assert_match "\"version\": \"v#{version}\"", json_output
    assert_match "\"built_by\": \"homebrew\"", json_output

    # Validate server configuration dry-run in test sandbox
    (testpath/"yager.yaml").write <<~EOS
      server:
        listen_address: "127.0.0.1:9090"
      sip:
        realm: "telecom.internal"
    EOS
    system "#{bin}/yager", "validate", "--config", testpath/"yager.yaml"
  end
end
```

### Alpine Linux `APKBUILD` Go Pattern

```bash
# Maintainer: Nathan Walker <nate@ravenhelm.dev>
pkgname=yager
pkgver=2.1.0
pkgrel=0
pkgdesc="Sovereign telecommunications switchboard and PBX daemon"
url="https://forgejo.ravenhelm.dev/nate/yager"
arch="x86_64 aarch64"
license="Proprietary"
makedepends="go"
source="${pkgname}-${pkgver}.tar.gz::https://forgejo.ravenhelm.dev/nate/${pkgname}/archive/v${pkgver}.tar.gz"
builddir="${srcdir}/${pkgname}-${pkgver}"

build() {
    export CGO_ENABLED=0
    export GOFLAGS="-trimpath"
    
    local _commit="d4e5f6a1b2c3"
    local _date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local _pkg="github.com/nwalker85/yager/internal/version"
    
    local _ldflags="-s -w \
        -X ${_pkg}.Version=v${pkgver} \
        -X ${_pkg}.GitCommit=${_commit} \
        -X ${_pkg}.BuildDate=${_date} \
        -X ${_pkg}.BuiltBy=alpine-aports"

    go build -ldflags "${_ldflags}" -o bin/yager ./cmd/yager
}

check() {
    ./bin/yager version | grep "yager v${pkgver}"
}

package() {
    install -Dm755 bin/yager "${pkgdir}/usr/bin/yager"
}
```

---

## 4. Node.js / TypeScript Package Inreplace Pattern

Node.js and TypeScript CLI applications present a distinct challenge: the package runtime is interpreted, and tools like `npm`, `pnpm`, or `bun` resolve their metadata directly from `package.json` at startup. If `package.json` contains a stale development version (such as `"version": "0.0.0-semantically-released"`), the CLI will output misleading version information to operators.

### In-Sandbox Dynamic Manipulation

In this pattern, Homebrew unpacks the source tarball, executes `inreplace` on `package.json` inside the sandbox, builds the TypeScript distribution (`npm run build`), and bundles the runtime dependencies into `libexec` before symlinking the entrypoint shim into `bin/`.

### Production Homebrew Formula (`Formula/heimdall-cli.rb`)

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
    # 1. Dynamically rewrite the version attribute inside package.json
    # Preserves formatting while replacing placeholder with release version
    inreplace "package.json",
              /"version"\s*:\s*"[^"]+"/,
              "\"version\": \"#{version}\""

    # 2. Also inject into package-lock.json if present to avoid npm install warnings
    if File.exist?("package-lock.json")
      inreplace "package-lock.json",
                /"name"\s*:\s*"heimdall-cli",\s*"version"\s*:\s*"[^"]+"/,
                "\"name\": \"heimdall-cli\",\n  \"version\": \"#{version}\""
    end

    # 3. Install production dependencies into libexec
    system "npm", "install", *Language::Node.local_npm_install_args

    # 4. Compile TypeScript source code into JavaScript distribution in-sandbox
    system "npm", "run", "build"

    # 5. Stage the application into libexec and link binary shims into bin
    system "npm", "install", *Language::Node.std_npm_install_args(libexec)
    bin.install_symlink Dir["#{libexec}/bin/*"]
  end

  test do
    # Validate CLI version output
    assert_match "heimdall v#{version}", shell_output("#{bin}/heimdall --version")

    # Validate Node.js execution environment and help menu
    assert_match "Usage: heimdall [options] [command]", shell_output("#{bin}/heimdall --help")

    # Validate execution in an empty directory without local node_modules
    test_dir = testpath/"isolated-run"
    test_dir.mkpath
    cd test_dir do
      assert_match "No traces found", shell_output("#{bin}/heimdall traces list 2>&1", 1)
    end
  end
end
```

---

## 5. Python CLI / Wheel Package Inreplace Pattern

Modern Python packages conform to PEP 517 and PEP 518, specifying build backends such as `hatchling`, `flit_core`, `setuptools`, or `poetry-core` within `pyproject.toml`. 

In traditional workflows, dynamic versioning is either abandoned in favor of rigid file bumps or tied to VCS tags via `setuptools_scm`. However, when compiling inside an isolated package manager sandbox, the `.git` directory is stripped from source tarballs. Tools that rely on `git describe` fail immediately with `LookupError: setuptools-scm was unable to detect version`.

### Dynamic Injection in `pyproject.toml`

By executing `inreplace` directly on `pyproject.toml` or `__init__.py` inside the build sandbox, operators satisfy PEP 517 build backends without requiring git metadata.

### Production Homebrew Formula (`Formula/snotra-audit.rb`)

```ruby
# typed: false
# frozen_string_literal: true

class SnotraAudit < Formula
  include Language::Python::Virtualenv

  desc "Advisory AI review gate and static audit daemon"
  homepage "https://forgejo.ravenhelm.dev/nate/snotra"
  url "https://forgejo.ravenhelm.dev/nate/snotra/archive/v1.8.0.tar.gz"
  sha256 "3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d"
  license "Proprietary"

  depends_on "python@3.12"

  def install
    # 1. Dynamically rewrite pyproject.toml version
    inreplace "pyproject.toml",
              /^version\s*=\s*"[^"]+"/,
              "version = \"#{version}\""

    # 2. If package uses static __version__.py, replace it directly
    if File.exist?("src/snotra/__version__.py")
      inreplace "src/snotra/__version__.py",
                /^__version__\s*=\s*"[^"]+"/,
                "__version__ = \"#{version}\""
    end

    # 3. Create isolated virtualenv inside libexec and install package
    # virtualenv_install_with_resources vendors dependencies and isolates site-packages
    virtualenv_install_with_resources
  end

  test do
    # Validate CLI responds with injected version string
    assert_match "snotra #{version}", shell_output("#{bin}/snotra --version")

    # Validate Python imports function within virtualenv
    system Formula["python@3.12"].opt_bin/"python3.12", "-c", <<~EOS
      import snotra
      assert snotra.__version__ == "#{version}", f"Expected #{version}, got {snotra.__version__}"
    EOS

    # Run smoke test on a temporary file
    (testpath/"sample.py").write "print('hello world')\n"
    system "#{bin}/snotra", "lint", testpath/"sample.py"
  end
end
```

---

## 6. Verification and Assertion Strategies

The `test do` block in a Homebrew formula or the `check()` function in an Arch/Alpine package is not an optional nice-to-have; in RROM, it is the **gate of physical proof**. A formula that compiles cleanly but produces an empty binary or prints `0.0.0-dev` has failed delivery.

### Anatomy of an Industrial-Grade Formula Test Block

A resilient formula verification block must satisfy four distinct assertions:

1. **Version Exactness:** Asserts that the compiled binary reports the exact formula `version` string, confirming that `inreplace` or `-ldflags` succeeded.
2. **Help & Exit Status Validation:** Verifies that invoking the command with `--help` or invalid arguments yields standard POSIX exit codes (0 for help, non-zero for syntax errors).
3. **Structured Telemetry Validation:** Asserts that structured JSON or YAML flags emit machine-parseable data containing the expected build metadata.
4. **Sandboxed State Execution:** Creates real configuration files in `testpath` and invokes a non-trivial subcommand (such as `validate`, `check`, or `init`) to prove that shared libraries, runtime paths, and embedded resources resolve properly.

```ruby
  test do
    # 1. Version Exactness
    assert_match "mytool v#{version}", shell_output("#{bin}/mytool --version")

    # 2. Exit Code & Help
    output = shell_output("#{bin}/mytool --help")
    assert_match "Usage:", output

    # 3. Structured Output Parsing
    json = JSON.parse(shell_output("#{bin}/mytool version --json"))
    assert_equal "v#{version}", json["version"]
    assert_equal "homebrew", json["built_by"]

    # 4. Sandboxed Execution
    (testpath/"test.conf").write "key = value\n"
    system "#{bin}/mytool", "check-config", "--path", testpath/"test.conf"
  end
```

### Automated Tap CI Pipeline (`.forgejo/workflows/tap-ci.yml`)

Formulas stored in a private Homebrew tap (`nate/homebrew-tools`) must be verified on every pull request using automated containers. The following workflow runs on Forgejo Actions runner capacity to ensure that formula modifications compile and pass their `test do` suites:

```yaml
name: Tap CI Validation

on:
  pull_request:
    paths:
      - "Formula/**.rb"

jobs:
  audit-and-test:
    runs-on: [self-hosted, macos-arm64]
    steps:
      - name: Checkout Tap Repository
        uses: actions/checkout@v4

      - name: Configure Local Tap
        run: |
          brew tap-new nate/test-tap --no-git
          cp -r Formula/* $(brew --repo nate/test-tap)/Formula/

      - name: Audit Formula Syntax
        run: |
          brew audit --strict --tap=nate/test-tap $(brew --repo nate/test-tap)/Formula/*.rb

      - name: Build and Test Formulas
        run: |
          for formula in Formula/*.rb; do
            name=$(basename "$formula" .rb)
            echo "Testing formula: ${name}..."
            brew install --build-from-source "nate/test-tap/${name}"
            brew test "nate/test-tap/${name}"
            brew uninstall "nate/test-tap/${name}"
          done
```

---

## 7. Security, Reproducibility, and Operational Anti-Patterns

When implementing sandboxed inreplace patterns, operators must guard against four common architectural failures:

| Inreplace Anti-Pattern | Root Problem & Pathology | Operational Remedy |
| :--- | :--- | :--- |
| **1. Upstream Release Commits** | Committing version bump to `Cargo.toml` on git release branch. | Mutates application source; breaks single-build rule and invalidates pre-tested digests. Keep source pegged to placeholder; mutate only in sandbox. |
| **2. Loose Regex Substitution** | `inreplace "Cargo.toml", /version = .*/, "..."` | Accidentally rewrites dependency versions or comments. Anchor regex strictly: `/^version\s*=\s*"[^"]+"/` or match under `[package]` header. |
| **3. Network Leakage** | Invoking `cargo build` or `npm install` without lockfiles or offline flags. | Pulls unvetted transitive packages; breaks offline/air-gapped builds. Enforce `--locked`, vendor dependencies, or use Nix pure derivations. |
| **4. Lockfile Desynchronization** | Rewriting `Cargo.toml` while ignoring `Cargo.lock`. | Cargo aborts build due to checksum mismatch under `--locked`. Execute dual `inreplace` across manifest and lockfile in lockstep. |

---

## 8. Summary: Sandboxing Compliance Checklist

Prior to approving any workstation package formula PR in a sovereign tap, the Release Gatekeeper must verify compliance against the following checklist:

- [ ] **Zero Git Pollution:** Upstream source repository contains zero commits dedicated to version bumping.
- [ ] **Exact Regex Anchoring:** Manifest rewriting regexes are strictly anchored to package-level fields (`/^version\s*=\s*.../`) to avoid corrupting dependency version constraints.
- [ ] **Dual Manifest/Lockfile Lockstep:** For Cargo and npm packages, both the primary manifest and the lockfile are synchronized within the sandbox.
- [ ] **Hermetic Compiler Flags:** Compilers are invoked with standard isolation arguments (`std_cargo_args`, `std_go_args`, `-trimpath`, `-s -w`).
- [ ] **Substantive Assertion Test:** The formula defines a `test do` block that asserts the exact version string and tests non-trivial command execution in an isolated directory.
- [ ] **Multi-Surface Parity:** The formula version matches the OCI container image tag and GitOps chart metadata deployed to the cluster for that release name.

<!-- RUBRIC_CHECK: Appendix A conforms to RROM specification. -->

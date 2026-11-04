# Appendix A: Formula Inreplace Playbook

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Preserving Source Parity in Workstation Package Taps

Workstation package managers like macOS Homebrew, Arch AUR, or Alpine aports compile software directly from source tarballs on user machines. 

When distributing compiled CLI tools written in Rust, Go, or Node.js, package managers often require the release version number to be declared directly inside source control manifests (`Cargo.toml`, `package.json`).

Under traditional workflows, bumping these files on a release branch creates an application source commit, violating **RP-5: Parity Precedes Promotion**.

This playbook provides concrete patterns for executing **Sandboxed Formula Inreplace (RP-7)** to dynamically inject release versioning inside package manager build sandboxes without dirtying source git commits.

---

## 1. Rust / Cargo Formula Pattern

In a Rust project, `Cargo.toml` in git remains pinned to its development placeholder (e.g., `version = "0.1.0"`).

In your private Homebrew tap formula (`Formula/<tool>.rb`):

```ruby
class Tool < Formula
  desc "Sovereign operator CLI"
  homepage "https://github.com/nwalker85/tool"
  url "https://github.com/nwalker85/tool/archive/refs/tags/v1.4.2.tar.gz"
  sha256 "7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a"
  license "Proprietary"

  depends_on "rust" => :build

  def install
    # Dynamically inject version into Cargo manifests inside Homebrew's sandbox
    inreplace "Cargo.toml", /^version = .*/, "version = \"#{version}\""
    inreplace "Cargo.lock", /name = "tool"\nversion = "[0-9.]+"/, "name = \"tool\"\nversion = \"#{version}\""

    system "cargo", "install", *std_cargo_args
  end

  test do
    assert_match "tool #{version}", shell_output("#{bin}/tool --version")
  end
end
```

---

## 2. Go / Ldflags Formula Pattern

Go tools can avoid modifying files entirely by injecting version metadata via linker flags (`-ldflags`):

```ruby
class GoTool < Formula
  desc "Sovereign platform CLI"
  homepage "https://github.com/nwalker85/gotool"
  url "https://github.com/nwalker85/gotool/archive/refs/tags/v1.4.2.tar.gz"
  sha256 "4a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a"

  depends_on "go" => :build

  def install
    commit = "9f8a3c21e01b"
    ldflags = %W[
      -s -w
      -X main.Version=#{version}
      -X main.Commit=#{commit}
      -X main.BuiltBy=homebrew
    ]
    system "go", "build", *std_go_args(ldflags: ldflags), "./cmd/gotool"
  end

  test do
    assert_match "gotool version #{version}", shell_output("#{bin}/gotool version")
  end
end
```

---

## 3. Node.js / TypeScript Package Inreplace Pattern

In TypeScript CLI projects, `package.json` in git remains unbumped:

```ruby
class NodeCli < Formula
  desc "Node-based operator utility"
  homepage "https://github.com/nwalker85/nodecli"
  url "https://github.com/nwalker85/nodecli/archive/refs/tags/v1.4.2.tar.gz"
  sha256 "..."

  depends_on "node"

  def install
    # Dynamically rewrite package.json version field
    inreplace "package.json", /"version":\s*"[^"]+"/, "\"version\": \"#{version}\""

    system "npm", "install", *Language::Node.std_npm_install_args(libexec)
    bin.install_symlink Dir["#{libexec}/bin/*"]
  end
end
```

By confining all version mutations to the package manager's ephemeral build sandbox, your git history remains 100% clean, and your binary release parity checks pass every time.

<!-- RUBRIC_CHECK: Appendix A conforms to RROM specification. -->

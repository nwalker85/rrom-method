# Chapter 7: Workflow Canon & Validation Gate

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## The Release State Machine

The movement of software from code commit to production traffic is modeled as a 5-state finite state machine. Transitions between states are fail-closed: if any verification gate fails, the state machine halts immediately without promoting the release.

```
[ INGRESS ] ──(Build CI)──> [ CANDIDATE ] ──(Release PR)──> [ PINNED ] ──(Tag & Gate)──> [ PROMOTED ] ──(Sync)──> [ CONVERGED ]
```

---

## 1. INGRESS: The Feature Merge
- **Event:** A feature or bug-fix pull request is reviewed and merged into `main`.
- **Action:** The CI workflow (`.forgejo/workflows/build.yml` or `.github/workflows/build.yml`) compiles the code, executes test suites, packages the container/binary, and pushes it to Harbor.
- **State Output:** An immutable build artifact tagged `:b<N>`, `:sha-<commit12>`, and `:uat`, carrying an immutable SHA-256 digest.

---

## 2. CANDIDATE: The Staging Exercise
- **Event:** The artifact is deployed automatically to the UAT / staging environment.
- **Action:** Automated integration tests, end-to-end user flows, and canary observations execute against the candidate build.
- **State Output:** A candidate build proven stable under operational load, identified by its build ID (e.g., `b42`).

---

## 3. PINNED: The Release Pull Request
- **Event:** The Release Custodian initiates the release for build `b42` targeting SemVer `v1.4.2`:
  ```bash
  scripts/release-pr.sh b42 v1.4.2
  ```
- **Action:** The script connects to the registry, retrieves the digest for `b42`, and generates a dedicated release branch modifying **only** metadata files:
  * Updates `chart/Chart.yaml`: sets `version: 1.4.2` and `appVersion: 1.4.2`.
  * Updates `chart/values.yaml`: pins `image.tag: v1.4.2`, `image.digest: sha256:...`, and `image.build: b42`.
  * Prepends release notes to `CHANGELOG.md`.
- **The Parity Guard:** The script executes `scripts/check-release-source-parity.sh`. It computes a diff between the release branch and the candidate commit, asserting that zero application source code files have been modified. If any `.rs`, `.go`, `.ts`, or `.py` files differ, the script aborts with exit code 1.

---

## 4. PROMOTED: The Tag and Retag Gate
- **Event:** The Delivery Closer reviews and merges the release pull request into `main`, then tags the commit:
  ```bash
  git tag -a v1.4.2 <commit-sha> -m "Release v1.4.2 = build b42"
  git push origin v1.4.2
  ```
- **Action:** The release workflow (`release.yml`) triggers on the tag and executes the three-way parity check:
  ```bash
  scripts/check-release-tag.sh
  ```
  It validates that:
  ```text
  git tag (v1.4.2) == values.yaml image.tag (v1.4.2) == Chart.yaml appVersion (1.4.2)
  ```
- **Retagging:** The release runner invokes `scripts/harbor-artifact.sh retag b42 v1.4.2`. Harbor adds the tag `v1.4.2` to the exact digest that ran in staging.

---

## 5. CONVERGED: GitOps Reconciliation and Proof
- **Event:** The release pipeline opens a pull request in the central GitOps repository (`nate/norns-gitops`), bumping `targetRevision: v1.4.2`.
- **Action:** Argo CD detects the updated manifest, pulls the digest `@sha256:...`, and performs a rolling update of the cluster pods.
- **Proof of Life:** The Delivery Closer probes the live running system:
  ```bash
  kubectl exec -it <pod> -- node -e 'fetch("http://localhost:3000/api/health").then(r => r.json()).then(console.log)'
  ```
- **Completion:** The release state transitions to **CONVERGED**.

<!-- RUBRIC_CHECK: Chapter 7 conforms to RROM specification. -->

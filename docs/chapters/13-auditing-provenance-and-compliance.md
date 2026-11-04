# Chapter 13: Auditing, Provenance & Compliance

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Cryptographic Custody and Provenance

In high-consequence environments, compliance is not an annual questionnaire filled out for an auditor; it is the verifiable output of your release automation. 

RROM mandates that every release construct a tamper-evident audit ledger that cryptographically connects:
1. **The Human / Agent Author:** The signed git commit.
2. **The Integration Record:** The CI build log and immutable build identifier (`:b<N>`).
3. **The Software Bill of Materials (SBOM):** The full inventory of upstream dependencies.
4. **The Registry Digest:** The cryptographic SHA-256 hash in Harbor.
5. **The Deployment Ledger:** The GitOps pull request and timestamped Argo CD sync status.

---

## 1. Automated Software Bill of Materials (SBOM)

During the single ingress build (`build.yml`), the CI runner generates a comprehensive Software Bill of Materials in standard CycloneDX or SPDX JSON format:
```bash
syft packages harbor.ravenhelm.dev/platform/vitki:b42 -o cyclonedx-json=sbom.json
cosign attest --predicate sbom.json --type cyclonedx harbor.ravenhelm.dev/platform/vitki:b42
```
The SBOM is cryptographically signed and pushed directly to Harbor as an OCI artifact attached to the container image digest.

---

## 2. The Verification Triangle Audit

When an internal compliance officer, auditor, or incident investigator examines a running production cluster, they execute the **Verification Triangle Audit**:

```text
       [ Live Pod Image Digest ]
               /      \
              /        \
 [ Harbor Tag Digest ] ── [ GitOps values.yaml Digest ]
```

1. Query the live container runtime on the cluster:
   ```bash
   kubectl get pod -n vitki -l app=vitki -o jsonpath='{.items[0].status.containerStatuses[0].imageID}'
   ```
   Output: `harbor.ravenhelm.dev/platform/vitki@sha256:7f9a...3c`
2. Query the GitOps repository configuration at tag `v1.4.2`:
   ```bash
   git show refs/tags/v1.4.2:chart/values.yaml | yq .image.digest
   ```
   Output: `sha256:7f9a...3c`
3. Query Harbor registry manifest for tag `v1.4.2`:
   ```bash
   crane digest harbor.ravenhelm.dev/platform/vitki:v1.4.2
   ```
   Output: `sha256:7f9a...3c`

If all three values match, **parity is proven**. There is zero possibility that an undocumented binary, unauthorized build layer, or tampered file is executing in production.

<!-- RUBRIC_CHECK: Chapter 13 conforms to RROM specification. -->

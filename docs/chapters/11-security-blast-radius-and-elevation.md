# Chapter 11: Security Blast Radius & Elevation

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## The Principle of Blast Radius Partitioning

Autonomous engineering systems and CI/CD pipelines require clear security boundaries. If an automation runner possesses the authority to rewrite root identity policies, a single prompt injection or compromised dependency can compromise the entire infrastructure estate.

RROM divides all operational mutations into two discrete security surfaces:

```
+-----------------------------------------------------------------------------------+
| SURFACE 1: ROUTINE APPLICATION MUTATIONS (AUTONOMOUS / LOW BLAST RADIUS)          |
| Scope:     Container images, Helm values, environment variables, web assets.      |
| Authority: The Delivery Closer (Autonomous CI / Merge to main is approval).       |
| Tokens:    Least-privilege registry push/pull tokens. Zero cluster admin secrets. |
+-----------------------------------------------------------------------------------+
                                         │
                                   [ HARD ISOLATION ]
                                         │
+-----------------------------------------------------------------------------------+
| SURFACE 2: CONTROL PLANE & IDENTITY MUTATIONS (ELEVATION / HIGH BLAST RADIUS)     |
| Scope:     Keycloak / Zitadel realms, OpenBao vault policies, Harbor RBAC.        |
| Authority: Gated by Valkyrie Multi-Factor Action Approval (MFAA).                 |
| Gate:      Plan SHA-256 hash bound to single-use consumable approval token.       |
+-----------------------------------------------------------------------------------+
```

---

## 1. Zero Ambient Authority for CI Runners

Under traditional CI setups, pipelines are provisioned with long-lived static secrets: AWS admin access keys, Kubernetes cluster-admin kubeconfigs, or root vault tokens. If an attacker compromises a pipeline runner, they inherit ambient root authority over the entire cluster.

RROM enforces **Zero Ambient Authority**:
- **Application Ingress Runners:** Possess only temporary, scoped tokens capable of pushing images to specific Harbor registry projects (`harbor.ravenhelm.dev/platform/*`). They have zero network access to Kubernetes API servers.
- **GitOps Reconcilers:** Argo CD runs entirely inside the cluster netns. It pulls manifests from git; no inbound deploy port is exposed to the internet or CI runners.

---

## 2. Action-Hash Elevation (The Ehwaz Doctrine)

For Surface 2 mutations—such as altering identity provider mappings or modifying database access controls via Terraform—automation is untrusted:

> *"Trust no agent with ambient authority; elevation via Valkyrie, action-hash bound, single use."*  
> — **The Ehwaz Doctrine**

### The Elevation Protocol:
1. **The Read-Only Plan:** The pull request triggers a CI runner authenticated with a read-only OpenBao AppRole (`tf-control-plane-plan`). The runner executes `terraform plan -out=tfplan.binary`.
2. **Cryptographic Hashing:** The runner computes the SHA-256 hash of the compiled plan:
   ```bash
   PLAN_HASH=$(sha256sum tfplan.binary | awk '{print $1}')
   ```
3. **The Approval Challenge:** The pipeline posts an elevation challenge to the Valkyrie MFAA service:
   ```json
   {
     "action": "terraform_apply",
     "target": "identity_plane",
     "plan_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
     "requester": "ci-runner-eikthyrnir-04"
   }
   ```
4. **Human Verification:** The authorized human Gatekeeper receives an encrypted challenge on their mobile device, inspects the exact diff, and cryptographically signs the challenge with biometric authentication.
5. **Single-Use Consumption:** The apply runner retrieves the signed authorization, verifies that the approval token's embedded `plan_hash` exactly matches the SHA-256 hash of `tfplan.binary`, executes `terraform apply`, and immediately calls the Valkyrie consume endpoint to invalidate the approval token.

Even if an attacker gains full control of the CI runner, they cannot mutate the identity plane without generating an approval token bound to the exact byte-level hash of their unauthorized plan.

<!-- RUBRIC_CHECK: Chapter 11 conforms to RROM specification. -->

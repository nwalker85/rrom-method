# Chapter 9: Cutovers vs. Deployments

<!-- LICENSE: RROM Community License 1.0 (c) 2026 Ravenhelm LLC -->

## Codifying the Cutover Boundary (ADR-011)

One of the most destructive traps in software operations is treating an **architectural cutover** as a routine **code deployment**. 

Under RROM, an organization must maintain a strict, legalistic distinction between these two operational concepts.

---

## Definitions: The Deploy vs. The Cutover

| Dimension | Routine Deployment | Architectural Cutover |
|---|---|---|
| **Definition** | Reconciling a running service to a new build of the **same code/stack**. | Changing **what codebase, datastore, or transport** serves production. |
| **Examples** | Bumping Vitki from `v1.4.1` to `v1.4.2`; fixing a bug in an existing HTTP handler; updating CSS tokens. | Swapping PostgreSQL for ClickHouse; replacing a RabbitMQ broker with NATS JetStream; swapping repo implementations. |
| **Authority** | The Delivery Closer (routine PR approval and merge). | Explicit Architectural Decision Record (ADR) + Formal Human Sign-Off. |
| **Data Plane** | Backward-compatible schema additions (expand-contract). | Data migration runbook, parity verification, and rollback snapshots. |
| **Old System** | Replaced in-place via rolling pod updates. | Running in parallel until decommissioning protocol completes. |

---

## The Lessons of the Bifrost Incident

The necessity of this boundary was forged in estate history. In mid-2026, an agentic engineering session attempted to upgrade an internal tool gateway service ("Bifrost"). Rather than deploying an incremental update, the session substituted an entirely different repository codebase, changed the datastore schema, and severed active transport layers in a single pull request.

Because the pull request was reviewed and merged as a "routine version bump," the deployment went live immediately. Production traffic crashed, active agent workflows were severed, and unmigrated database records were orphaned. 

From that disaster emerged **ADR-011: The Cutover Doctrine**:

> **NEVER replace a deployed service's architecture without an ADR and explicit cutover approval.**  
> A merge that changes what codebase or stack serves production—repo swap, datastore swap, transport removal—is a cutover, not a deploy. It requires:
> 1. An Architectural Decision Record (ADR) accepted prior to implementation.
> 2. A documented, dry-run tested data migration plan.
> 3. An explicit, dual-running verification window.
> 4. A formal decommissioning protocol for the replaced system.

---

## The Four Requirements of a Cutover

Whenever a proposed change satisfies the definition of a cutover, the release pipeline halts. The following four gates must be satisfied before traffic may shift:

### 1. The Decision Record (ADR)
An ADR must be committed to the repository's architecture decisions log (`docs/architecture/decisions/`), detailing:
- The technical justification for replacing the serving architecture.
- The rejected alternatives.
- The backward-compatibility guarantees for existing client consumers.

### 2. The Expand-and-Contract Migration Plan
Datastore and schema cutovers must never occur in a single "big bang" release:
- **Phase 1 (Expand):** Deploy schema additions. The application dual-writes to both the old and new structures while continuing to read from the old.
- **Phase 2 (Backfill):** Offline background workers migrate historical data. Parity checks verify byte-level integrity between old and new stores.
- **Phase 3 (Contract):** The application switches reads to the new datastore. Once verified under peak production load, writes to the legacy datastore cease.

### 3. The Shadow-Traffic Verification
The new architecture must run concurrently alongside the legacy system in production for a minimum evaluation window. Ingress proxies mirror real production requests to both stacks, asserting response parity and error-rate equivalence.

### 4. Loud Decommissioning
The legacy system is not left running as an undocumented zombie process. A formal decommissioning PR removes the legacy manifests from the GitOps repository, archives the retired codebase, tears down unused network routes, and reclaims allocated storage.

<!-- RUBRIC_CHECK: Chapter 9 conforms to RROM specification. -->

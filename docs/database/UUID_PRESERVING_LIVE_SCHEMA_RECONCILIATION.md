# MediCycle — UUID-preserving schema alignment plan

**Baseline:** live TiDB schema snapshot captured 2026-11-27.  
**Design authority:** `MediCycle_Database_Design_39_Table_Specifications.md`.  
**Implementation:** existing SQLAlchemy models and deployed TiDB schema.

## Approved architecture decision

Preserve the deployed singular camelCase table names and UUID `CHAR(32)` primary/foreign keys. Do not rename tables, convert identifiers, or replace existing application fields solely to match the proposed BIGINT/plural-snake_case design.

## Verified live inventory

- 39 deployed tables
- 354 deployed columns
- 39 primary keys
- 76 foreign keys
- 17 unique constraints
- 89 indexes
- 126 `CHAR(32)` columns
- Snapshot: `2026-11-27T15:30:34.064022+00:00` UTC

The approved specification contains 39 entities and 376 attributes. The net column-count difference (22) is not the count of missing fields: implementation-only fields and semantically equivalent names must be reconciled individually.

## Field-level findings confirmed for Module 1

| Spec entity | Live table | Confirmed differences | Safe handling |
|---|---|---|---|
| `users` | `user` | Missing `account_type`; `email` and `phone` nullable live vs required in spec; live boolean `emailVerified`/`phoneVerified` differ from proposed timestamps; `lastLoginAt` is implementation-only. | Add a nullable role field first; do not force existing email/phone NOT NULL; retain legacy fields. Verification timestamp semantics need a decision. |
| `user_addresses` | `userAddress` | Missing `is_active` and `updated_at`; `landmark` is implementation-only; `addressLabel` already exists. | Preserve `landmark`; add fields only as nullable/defaulted after preview. |
| `user_documents` | `userDocument` | Missing storage metadata (`storage_key`, original filename, MIME type, size, deleted timestamp); existing `documentNumber`, `filePath`, `reviewedAt`. | Do not assume `filePath` is a secure object-storage key. Preserve legacy columns and add metadata separately. |
| `verifications` | `verification` | `verifiedBy` resembles reviewer ID but has no FK; `rejectionReason` is not necessarily equivalent to `remarks`; timestamp names differ. | Validate existing reviewer IDs before adding an FK. Keep reason and remarks distinct until semantics are confirmed. |

## Reconciliation classification

Every attribute must be compared across the three sources (approved specification, live TiDB, SQLAlchemy) and assigned exactly one status:

- **Exact:** same meaning and compatible type/constraint.
- **Equivalent candidate:** naming differs; semantic equivalence still needs validation.
- **Missing live column:** candidate for additive migration after defaults/backfill analysis.
- **Implementation-only:** existing field not in the 39-entity spec; preserve unless explicitly retired.
- **Needs decision:** meaning, lifecycle, ownership or cardinality differs.

## Relationship and constraint rules

- The captured TiDB foreign keys and unique constraints are the deployed baseline.
- A one-to-one relationship must be backed by a unique constraint on the child FK; ORM relationship declarations alone are insufficient.
- Polymorphic identifiers (for example generic party references, notification references and audit entity references) are not ordinary foreign keys.
- Add FKs only after orphan checks; add unique constraints only after duplicate checks; add CHECK constraints only after invalid-value counts are reviewed.
- Do not shorten VARCHAR columns or tighten nullability until existing data has been checked for compatibility.

## Migration safety contract

1. Preview mode is the default; apply mode must require an explicit flag.
2. Verify the expected database, table names and baseline columns before any DDL.
3. First migration adds only nullable columns or columns with deterministic safe server defaults.
4. Backfills are separate, idempotent steps with before/after counts and unresolved-row reports.
5. Foreign keys, unique constraints and CHECK constraints are separate guarded steps.
6. No automatic migration at application startup.
7. No table/column drops, table renames, UUID conversion, `drop_all()`, or seed execution.
8. Downgrade must not silently delete populated data.

## Decisions that cannot be automated safely

- Existing users' account-role assignment.
- Tightening nullable email/phone columns.
- Mapping legacy document paths to private object storage.
- Adding reviewer/actor FKs without orphan and actor-type validation.
- Prescription document ownership and one-to-one semantics.
- Typed custody-transfer actors and exactly-one-actor rules.
- Intake/inspection/return-item cardinality.
- Retiring any implementation-only fields or the medicine-tracking `ReturnBucketItem` extension.

## Phase status

**Completed:** UUID architecture decision recorded; live schema inventory counts verified; Module 1 semantic mismatches documented.

**Next:** produce the exhaustive 39-entity attribute crosswalk (spec ↔ live ↔ ORM), then implement guarded additive migrations and corresponding ORM changes in dependency-safe batches. ORM mappings must not be deployed before their matching columns exist, because SQLAlchemy will otherwise select columns that TiDB does not yet have.

**Production status:** no live DDL or data mutation has been performed.

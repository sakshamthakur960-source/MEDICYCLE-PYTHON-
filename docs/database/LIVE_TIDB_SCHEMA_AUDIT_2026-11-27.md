# MediCycle — Live TiDB Schema Audit

**Inspection:** GitHub Actions run [#46025492632](https://github.com/sakshamthakur960-source/MEDICYCLE-PYTHON-/actions/runs/46025492632) — successful  
**Database:** `medicycle`  
**Snapshot generated:** 2026-11-27 15:31 UTC  
**Method:** SQLAlchemy metadata inspection plus TiDB `information_schema.KEY_COLUMN_USAGE`; read-only. No application rows queried.

## Verified physical inventory

| Metric | Live value |
|---|---:|
| Tables | 39 |
| Columns | 354 |
| Primary keys | 39 |
| Foreign keys | 76 |
| Unique constraints | 17 |
| Indexes | 89 |

The 39 physical tables are:

`auditLog`, `binItem`, `collectionManifest`, `commissionPayout`, `custodyTransfer`, `disposalBatch`, `disposalCertificate`, `disposalRecord`, `driver`, `facility`, `facilityIntake`, `facilityStaff`, `inspectionRecord`, `medicine`, `medicineBatch`, `medicineRoutine`, `notification`, `pickupAssignment`, `pickupSlot`, `prescription`, `returnItem`, `returnRequest`, `returnStatusHistory`, `reward`, `rewardRedemption`, `route`, `routeStop`, `staffCommission`, `storageBin`, `tamperSeal`, `trackingLog`, `user`, `userAddress`, `userDocument`, `userMedicine`, `vehicle`, `verification`, `wallet`, `walletTransaction`.

## Confirmed compatibility findings

1. **Entity coverage:** the 39 live table names correspond to the 39 entities in the approved specification, using the existing singular camelCase naming convention rather than plural snake_case.
2. **Identifier strategy:** the live snapshot contains 126 `CHAR(32)` columns, consistent with the deployed UUID key strategy. The approved design proposes `BIGINT UNSIGNED AUTO_INCREMENT` primary keys and matching foreign keys. This is a high-risk key migration, not a cosmetic rename.
3. **Column count:** live schema has 354 columns; the approved design specifies 376 attributes. The net difference is 22, but this is **not** the exact count of missing fields because the implementation also has additional fields and differently named/equivalent fields.
4. **Relationships:** 76 live foreign keys were reflected. These must be compared by source column and target column, not inferred from table names.
5. **Return bucket:** the ORM branch contains a `ReturnBucketItem` model, but the live snapshot contains no `returnBucketItem` table. Resolve this against PR #8 before enabling its feature/migration.

## Safe remediation decision

- Do **not** rename live tables or convert UUID keys to BIGINT in place. Existing application code and stored relationships depend on UUIDs.
- Do **not** apply the canonical 39-table proposal as a blind migration. First build a per-attribute matrix classifying each field as exact, equivalent, missing, implementation-only, or requiring a business decision.
- Any additive changes must be backward-compatible and checked against existing values, defaults, nullability, indexes, foreign keys, and application usage. New required fields need a staged nullable → backfill → enforce migration.
- The UUID-to-BIGINT conversion, if ultimately approved, requires a separately staged dual-key/backfill/validation/cutover plan and rollback strategy.
- PR #8's medicine-tracking migration remains separate and must receive its own fresh preview and reconciliation before application.

## Scope and integrity

This audit reads database metadata only. It did not read or modify user records, execute DDL, apply migrations, or seed data. The exact machine-readable snapshot is retained as the GitHub Actions artifact named `medicycle-live-schema-snapshot` in run #46025492632.

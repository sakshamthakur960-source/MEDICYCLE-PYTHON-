# Option A — live schema reconciliation status

Date: 2026-11-27  
Base: main at `701ebdf3dbdeacdb46061b934fca08465ee202d3`

## Confirmed architecture

- Preserve all 39 deployed singular camelCase tables.
- Preserve UUID `CHAR(32)` primary and foreign keys.
- Do not rename physical tables or convert identifiers to BIGINT.
- Keep existing live-only columns until usage and data ownership are established.
- No production DDL or DML is included in this phase.

## Reconciliation baseline

| Item | Count |
|---|---:|
| Approved specification entities | 39 |
| Specification attributes | 376 |
| Live tables | 39 |
| Live columns | 354 |
| Live UUID CHAR(32) columns | 126 |
| Candidate same-convention field-name matches | 242 |
| Unmatched candidate names requiring semantic review | 134 |

The 242/134 split is a lexical candidate comparison using the documented snake_case-to-camelCase convention. It is **not** a semantic match/missing-field verdict. Each unmatched field must be checked against the ORM and API usage before a migration is proposed.

## Production data preflight

Read-only GitHub Actions run: [46028723309](https://github.com/sakshamthakur960-source/MEDICYCLE-PYTHON-/actions/runs/46028723309)

- 39 tables scanned; 56 rows total.
- 76 foreign-key orphan checks passed.
- 56 unique-index duplicate checks passed.
- Zero failed checks and zero review flags.
- Scanner used SELECT-only statements; no production data or schema changed.

## Migration gate

No Alembic revision is generated or applied until each difference has:
1. Current live definition and ORM mapping.
2. Target mapping that preserves UUID identity and existing table names.
3. Existing-row impact analysis (NULLs, lengths, precision/ranges, duplicate candidates).
4. TiDB-compatible DDL preview and lock/online behavior.
5. Isolated-schema upgrade, application CRUD, and rollback/forward-fix validation.

## Important limitation

The live schema snapshot and current ORM are the implementation baseline. The 39-table specification includes proposed attributes and proposed business rules; it is not evidence that every proposed attribute is already a finalized production requirement. The exhaustive field crosswalk is maintained as a separate generated review artifact and must not be treated as migration authorization.

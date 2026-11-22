# MediCycle implementation status

## Baseline retained
- 39 existing SQLAlchemy model classes retained.
- Existing MySQL schema and backup are not modified by this code generation pass.
- Existing model attribute names are not renamed in this pass.
- New HTTP API code is isolated under `api/`.

## Backend API pass 1
Implemented:
- Environment-backed MySQL configuration already present in `Database.py`.
- User registration and password login.
- Scrypt password hashing and JWT bearer authentication.
- User profile read/update and address create/list.
- Medicine catalogue search and user-medicine create/list.
- Pickup-slot listing.
- Return request creation with multiple return items and return list/detail.
- Wallet summary, rewards listing, transactions and certificate listing.
- Reward redemption with wallet debit in one database transaction.
- CORS configuration for local frontend development.

## Workflow invariants applied
- A return request can contain multiple return items.
- Doorstep pickup requires an address and available slot.
- Pharmacy drop-off is associated with an operational destination facility. The API does not put this drop-off into pharmacy storage bins.
- New return items receive zero credits and remain pending until physical receipt and verification.
- Reward debit and redemption creation are atomic.

## Remaining backend work
- Driver and staff identity/authorization policies.
- Pickup assignment, route, route-stop and driver tracking endpoints.
- Custody transfer and scan endpoints.
- Facility intake, inspection and request-level accept/reject decision.
- Credit allocation and wallet credit after accepted physical receipt.
- Storage-bin, bin-item, tamper-seal and manifest operations.
- Disposal batch/record/certificate lifecycle.
- Commission, payout, notification and audit-log workflows.
- File storage for prescriptions and user documents.
- OTP flow if retained as a working authentication method.
- Alembic migrations and integration tests against a local MySQL instance.

## Known schema issues carried forward
- `CustodyTransfer.fromPartyId` and `toPartyId` are polymorphic identifiers without conventional FKs.
- Several actor/reviewer UUID fields have no FK.
- `DisposalCertificate` references both a return and optionally a disposal record; ownership/cardinality needs final enforcement.
- `ReturnItem.inspectionStatus` and `creditsAwarded` are item-level while the confirmed acceptance decision is request-level. API must apply one decision to the whole request.
- `TrackingLog` coordinates use `Numeric(12,2)`, which is not sufficient precision for GPS. A migration is required before changing it.

## Validation
- All Python files pass `compileall` syntax compilation.
- Full API import/integration testing was not possible in this build environment because the MySQL DBAPI package `PyMySQL` is not installed here and network package installation is unavailable. Install `requirements.txt` in the project's Python 3.11 virtual environment before running the API.


## Python frontend conversion (2026-11-22)

- Replaced the active React/Vite UI with a Python Streamlit application in `streamlit_app/app.py`.
- The previous React source is retained in `docs/react-reference/` for reference only.
- Added a consolidated PowerShell launcher `start_medicycle.ps1` to start FastAPI and Streamlit.
- Added `README_PYTHON_APP.md` with Windows installation, configuration, launch and database safety instructions.
- Added Streamlit, requests and pandas to requirements.
- UI covers customer registration/login, dashboard, multi-item returns, profile/address, wallet/rewards, certificates/notifications, facility operations and driver workflows.
- Updated driver status action to use the backend's actual POST route.
- Preserved existing 39 SQLAlchemy entities and MySQL database target `medicycle`; no schema reset/migration/drop was performed.
- Validation: `compileall` passed; existing isolated SQLite workflow smoke test passed. Streamlit is not installed in the build environment, so runtime browser validation remains a local setup step. PyMySQL is also unavailable in the build environment, so no live MySQL connection was attempted.

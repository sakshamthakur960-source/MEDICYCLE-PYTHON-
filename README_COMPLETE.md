# MediCycle — full-stack application package

This package contains the existing SQLAlchemy/MySQL data model, a FastAPI backend, and a Python Streamlit frontend. It is a development-ready application foundation built around the 39 identified MediCycle entities and the existing 18 HTML prototype screens.

## Architecture

- **Database:** existing MySQL database `medicycle`; existing 39 SQLAlchemy entity models retained.
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.x, PyMySQL, Pydantic, JWT bearer authentication.
- **Frontend:** Streamlit + Python; communicates with FastAPI over authenticated HTTP.
- **Authentication:** email/phone + password, scrypt password hashes, signed JWT access tokens. The frontend keeps the token in `sessionStorage` (cleared when the browser session ends).

## Critical database safety

1. Keep your existing MySQL database and backup. The earlier audit found 39 model tables plus a separate legacy `users` table; the application does not delete that extra table.
2. Do not run `Base.metadata.drop_all()`.
3. Do not use a fresh database or reset command over your existing `medicycle` database.
4. `Base.metadata.create_all()` creates missing tables only; it does not alter existing columns or constraints. The optional demo seed script calls it for missing tables and inserts only reference/demo records where the relevant tables are empty. Review the script before running it.
5. Existing schema/model differences must be reconciled through reviewed, versioned migrations. No automatic migration is run by the application startup.

## Windows setup — backend

Open PowerShell in the backend folder (the folder containing `Database.py`):

```powershell
py -3.11 --version
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and use the credentials for your existing local MySQL `medicycle` database:

```dotenv
DB_USER=root
DB_PASSWORD=YOUR_MYSQL_PASSWORD
DB_HOST=localhost
DB_PORT=3306
DB_NAME=medicycle
JWT_SECRET=REPLACE_WITH_A_LONG_RANDOM_SECRET
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://sakshamthakur960-source.github.io
```

Generate a strong secret in PowerShell if needed:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Never commit `.env`. If MySQL is not running, start the MySQL service first. Before connecting, retain a fresh SQL backup. The existing backup command is:

```powershell
mysqldump -u root -p medicycle > medicycle_backup_before_app.sql
```

Start the API:

```powershell
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Open:
- Health check: http://127.0.0.1:8000/health
- API documentation: http://127.0.0.1:8000/docs

### Optional demo reference data

The database was previously observed to have empty tables. To make the catalogue, drop-off facility, pickup slots and rewards screens demonstrable, you may run:

```powershell
python seed_demo.py
```

This is optional. It inserts clearly labelled demo catalogue/facility/reward/slot records only when the corresponding tables are empty; it does not delete or update existing records. The demo facility is illustrative and must not be represented as a real authorized facility in production. Do not run this on a production/shared database.

## Windows setup — Python frontend

Follow `README_PYTHON_APP.md`. Run `start_medicycle.ps1` after installing the requirements and configuring `.env`. The Streamlit interface runs at http://127.0.0.1:8501 and FastAPI runs at http://127.0.0.1:8000. The former React prototype source is retained under `docs/react-reference/` only; it is not required to run MediCycle.

## Customer workflows implemented

- Register and log in; create a wallet on registration.
- View/update profile and manage addresses.
- Search medicine catalogue and add multiple medicines to one return request.
- Choose doorstep pickup with an available slot or direct facility drop-off.
- View return history and request statuses.
- View wallet balance and transactions.
- Redeem available rewards with atomic wallet debit.
- View disposal certificates that have already been issued.
- View notifications.

## Facility staff workflows implemented

- Facility membership is derived from active `FacilityStaff` rows; no new `User.role` column was invented.
- View facility dashboard, return queue, bins, driver/vehicle options, commissions, payouts, manifests and disposal records.
- Record physical facility receipt.
- Inspect every item and make one request-wide ACCEPTED or REJECTED decision. Mixed partial request decisions are rejected.
- Award explicit credits per item only after intake and verification. The application does not assume a credit formula.
- Store accepted items in a bin, respecting bin capacity; apply tamper seals.
- Assign verified drivers and available vehicles to doorstep pickup returns.
- Create disposal records against an authorized facility and optional intake.

## Driver workflows implemented

- Driver workspace is derived from a `Driver.userId` link.
- View own assignments, update en-route/arrived/picked-up states and submit GPS tracking updates.
- Return tracking access is restricted to the return owner, assigned driver or associated facility staff.

## Prototype screens reviewed as design references

The 18 original files `01-add-items-and-choose-route.html` through `18-good-morning-ramesh.html` were audited for screen labels, interactions, navigation and workflow concepts. This React application consolidates the customer-facing return, profile, wallet, reward and certificate workflows, and provides separate facility and driver workspaces. It does not claim to reproduce every decorative prototype screen pixel-for-pixel. Prototype-only simulated OTP, biometric login, live maps, camera barcode scanning and push notification behavior are not represented as real services.

## API route groups

- `/api/auth/*` — registration/login
- `/api/users/me*` — profile and addresses
- `/api/medicines/*`, `/api/user-medicines` — medicine catalogue and user medicine list
- `/api/returns*`, `/api/pickup-slots` — customer returns
- `/api/wallet*`, `/api/rewards`, `/api/reward-redemptions`, `/api/certificates` — wallet and rewards
- `/api/facilities`, `/api/notifications*`, `/api/tracking/returns/*` — shared user services
- `/api/staff/*` — staff operations, intake, inspections, storage, assignments, commissions, disposal
- `/api/driver/*` — driver assignments and tracking

## Current known limitations / decisions not silently assumed

- OTP/SMS/email delivery, KYC document upload/review, real barcode/camera scanning, maps/routing/ETA, push notifications and real certificate PDF generation require provider configuration and are not faked as operational services.
- Commission calculation/payout rules and reward partner fulfillment are not defined by the source specifications; existing commission and reward records can be viewed/redeemed, but no financial calculation or bank payout is fabricated.
- Certificate ownership and file-generation rules need a finalized decision. Existing issued certificates are listed; the API does not invent a certificate record or PDF.
- Custody transfer uses polymorphic party type/ID columns. This needs an explicit schema decision before enforcing all party references at database level.
- User verification actor IDs and some other operational actor IDs lack conventional foreign keys in the current model. No schema changes are made here.
- The source milestone PDF gives detailed attributes for only 17 entities and names for all 39. The remaining attributes are taken from the existing `models.py`, not falsely attributed to the PDF.
- The original `TrackingLog.latitude`/`longitude` precision in the existing model is `Numeric(12,2)`. GPS-grade precision should be changed only through an approved migration after schema review; this package does not silently alter it.
- Facility/driver/staff accounts must be provisioned in the existing `FacilityStaff` and `Driver` tables by an authorized administrator. There is no public self-service role escalation.

## Validation status

- Python Streamlit UI source compilation: passed. Streamlit runtime launch could not be performed in the build environment because Streamlit is not installed there; it is included in `requirements.txt` for local installation.

- Python source compilation: passed.
- Isolated SQLite API workflow smoke test: passed (registration, address, return, physical intake, request-wide inspection, explicit credit issuance and duplicate-award protection). This test uses an in-memory SQLite database and does not touch the MySQL database.
- React JSX/JavaScript syntax transpilation check: passed.
- Password hashing helpers: previously unit-checked in the initial API pass.
- Full FastAPI/MySQL integration: not run in this build environment because the local execution environment does not have the PyMySQL driver and cannot reach package indexes. Install `requirements.txt` in the Windows virtual environment and test against your backed-up local database.
- React production build: not run because npm dependency installation timed out in this environment. Run `npm install` and `npm run build` locally.
- No command in this build modified your Windows machine, GitHub repository, or live MySQL database.

## First run checklist

1. Back up `medicycle`.
2. Install Python dependencies in the `.venv`.
3. Fill in backend `.env` and start MySQL.
4. Start FastAPI and verify `/health` and `/docs`.
5. If using demo mode, review and run `python seed_demo.py`.
6. Install frontend packages and run Vite.
7. Register a customer account; test an address and return submission.
8. Provision a separate staff user with a matching active `FacilityStaff` row and facility; test intake and inspection.
9. Provision a driver user linked through `Driver.userId`; test assignments and tracking.
10. Only then configure external providers and deployment.

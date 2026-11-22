# MediCycle — Python full-stack setup

This is the consolidated Python-interface build. The user interface is **Streamlit (Python)**; the backend is **FastAPI (Python)**; the ORM is **SQLAlchemy**; the database remains your existing **MySQL `medicycle`** database. The old React folder is retained only as a reference and is not needed to run this Python UI.

## 1. Do not delete your database

Keep the current `medicycle` database and your SQL backup. The earlier inspection found 39 modeled entities plus a separate legacy `users` table. This application does not drop or reset either. Do not run `Base.metadata.drop_all()` and do not run `create_database.py` against the existing database. The application startup does not automatically migrate the schema.

Before setup, make a new backup in PowerShell:

```powershell
mysqldump -u root -p medicycle > medicycle_before_python_ui.sql
```

## 2. Install prerequisites

- Python 3.11
- MySQL Server running locally
- MySQL command-line tools (`mysqldump` is recommended for backups)

Open PowerShell in the folder containing `Database.py`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run this once in the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 3. Configure database and authentication

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```dotenv
DB_USER=root
DB_PASSWORD=YOUR_MYSQL_PASSWORD
DB_HOST=localhost
DB_PORT=3306
DB_NAME=medicycle
JWT_SECRET=REPLACE_WITH_A_LONG_RANDOM_SECRET
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:8501,http://127.0.0.1:8501
```

Generate a JWT secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not share or commit `.env`.

## 4. Start the complete application

Double-click `start_medicycle.ps1`, or run it from PowerShell:

```powershell
.\start_medicycle.ps1
```

It opens the FastAPI backend in a separate PowerShell window and runs the Python Streamlit interface in the current window.

Open:

- Python frontend: http://127.0.0.1:8501
- API health: http://127.0.0.1:8000/health
- API docs: http://127.0.0.1:8000/docs

To stop the app, close both PowerShell windows or press Ctrl+C in each.

## 5. First-use checklist

1. Register a customer account in the Streamlit app.
2. Add a delivery address under Profile & addresses.
3. Ensure medicine catalogue entries and pickup slots exist before creating a doorstep return.
4. A facility drop-off needs an operational, authorized facility.
5. Staff accounts must be linked to active `FacilityStaff` records. Driver accounts must be linked through `Driver.userId`. Customer registration cannot grant staff/driver privileges.
6. Staff must record physical intake before deciding the return. All items must receive the same request-wide decision. Accepted returns require explicit per-item credit values; no credit formula is invented.

The optional `seed_demo.py` script can insert illustrative demo reference data only when relevant tables are empty. Review it before running and never run demo seeding on a production database. Do not represent its demo facility as a real authorized facility.

## 6. Architecture

```text
Streamlit Python UI :8501
        |
        | HTTP + JWT
        v
FastAPI backend :8000
        |
        | SQLAlchemy / PyMySQL
        v
Existing MySQL database: medicycle
```

## 7. Known limitations

- OTP, SMS/email delivery, live maps/ETA, real camera barcode scanning and push notifications need external providers and are not simulated as live services.
- Certificate ownership/PDF generation, commission calculation/payout rules, reward partner fulfillment and polymorphic custody-party foreign keys still require finalized specifications.
- The 18 original HTML screens remain in `docs/frontend-prototypes/` as visual/workflow references. The Python UI provides consolidated customer, staff and driver workflows; it is not a pixel-perfect copy of every HTML prototype.
- Full local MySQL integration must be run on your computer after installing dependencies. This package does not include your database credentials or data.
## Frontend visual refresh
The Streamlit interface now uses a consistent MediCycle visual system (deep green/teal, soft mint surfaces, updated typography, refined controls and metric cards). The login screen has a split hero-and-authentication layout. This refresh changes presentation only; existing API routes, database models and return/credit business rules are unchanged.

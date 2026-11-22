# MediCycle API — first implementation pass

This API layer is added alongside the existing 39 SQLAlchemy models. It does not drop, rename, or recreate database tables.

## Stack
- FastAPI + Pydantic
- Existing SQLAlchemy 2.x models and MySQL/PyMySQL connection
- scrypt password hashing using Python standard library
- Signed bearer access tokens through PyJWT

## Setup (Windows PowerShell)

```powershell
cd C:\Users\saksh\OneDrive\Desktop\MediCycle_Backend_Ready
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`. Set the real MySQL password and replace `JWT_SECRET` with a long random secret. Never commit `.env`.

## Start the API

```powershell
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

- Health: `http://127.0.0.1:8000/health`
- Interactive API docs: `http://127.0.0.1:8000/docs`

## Implemented endpoints in this pass

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | API health |
| POST | `/api/auth/register` | Register account and create wallet |
| POST | `/api/auth/login` | Email/phone + password login |
| GET/PATCH | `/api/users/me` | Read/update current profile |
| GET/POST | `/api/users/me/addresses` | List/create addresses |
| GET | `/api/medicines/search` | Search medicine catalogue |
| GET/POST | `/api/user-medicines` | List/add user's medicine records |
| GET | `/api/pickup-slots` | List available pickup slots |
| POST | `/api/returns` | Create a return request with one or more items |
| GET | `/api/returns` | List current user's returns |
| GET | `/api/returns/{return_id}` | Return details and status history |
| GET | `/api/wallet` | Wallet balance/status |
| GET | `/api/rewards` | Available rewards |
| GET | `/api/wallet/transactions` | Recent wallet transactions |
| GET | `/api/certificates` | Current user's disposal certificates |
| POST | `/api/reward-redemptions` | Atomic reward redemption and wallet debit |

## Important workflow rules already enforced
- A return request contains one or more return items.
- A doorstep pickup requires an address and an available pickup slot.
- A pharmacy drop-off requires an operational destination facility; it does not create a pharmacy storage-bin record.
- New return items begin with `inspectionStatus=PENDING` and `creditsAwarded=0`.
- Reward redemption and wallet debit are committed in one database transaction.
- User records and wallet records are created together during registration.

## Not yet implemented
This is the first API pass, not a claim that the complete platform is finished. Remaining API work includes OTP verification, secure document upload, staff/driver/facility authorization, pickup assignment and route operations, custody transfer, intake inspection and all-or-nothing return decision/credit issuance, storage/seal workflows, disposal records/certificates, commissions, notifications, audit logging, and full integration with all 18 frontend screens.

The current schema has several design constraints that must be addressed before production use: polymorphic custody party IDs, reviewer/actor IDs without FKs, disposal certificate ownership, and the request-level acceptance rule versus per-item inspection/credit fields. This pass does not silently alter those model columns.

## Database safety
The API does not call `Base.metadata.drop_all()`. Do not use destructive schema reset commands. Use versioned Alembic migrations for future schema changes. Existing local tables are preserved.

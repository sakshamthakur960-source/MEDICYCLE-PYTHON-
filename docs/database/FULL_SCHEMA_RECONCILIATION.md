# MediCycle — Full 39-Entity Schema Reconciliation

**Baseline:** approved database design document (39 proposed tables, 8 modules)  
**Implementation inspected:** SQLAlchemy `models.py` on `feature/medicine-expiry-tracking-sync`  
**Purpose:** audit artifact only; no production schema or application behavior changed by this report.

## Executive result

- Specification entities: **39**
- Specification attributes: **376**
- SQLAlchemy model classes: **40**
- SQLAlchemy mapped columns: **364**
- All specified entities mapped: **39/39**
- Extra implementation table(s): `returnBucketItem`

### Systemic incompatibilities

1. Specification requires plural snake_case table names; current models use singular camelCase table names.
2. Specification requires snake_case columns; current models use camelCase attributes.
3. Specification requires BIGINT UNSIGNED AUTO_INCREMENT primary keys and matching BIGINT UNSIGNED foreign keys; current models use UUID identifiers.
4. Most model string columns use generic `String(255)`, while the specification defines specific lengths.
5. Python-side datetime defaults do not necessarily reproduce database-side `CURRENT_TIMESTAMP` and `ON UPDATE CURRENT_TIMESTAMP` behavior.
6. The live database schema was not introspected as part of this comparison; this report compares the approved design document to the branch's ORM source only.

## Entity-by-entity detail

### 3.1 `users`

**Specification attributes (11):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `user_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `account_type` | VARCHAR(30) | NN; proposed values: `customer`, `driver`, `facility_staff`, `administrator` |
| `full_name` | VARCHAR(100) | NN |
| `email` | VARCHAR(255) | NN, UQ; normalize to lowercase before storage |
| `phone` | VARCHAR(20) | NN, UQ; store country code where applicable |
| `password_hash` | VARCHAR(255) | NN; store an Argon2id or bcrypt password hash, never a plaintext password |
| `account_status` | VARCHAR(20) | NN, DEFAULT `active`; allowed: `active`, `suspended`, `deactivated`, `pending` |
| `email_verified_at` | DATETIME | NULL; proposed |
| `phone_verified_at` | DATETIME | NULL; proposed |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP |

**SQLAlchemy model:** `User` (`user`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `userId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `fullName` | `str` | `String(255), nullable=False` |
| `email` | `str | None` | `String(255), nullable=True, unique=True` |
| `phone` | `str | None` | `String(255), nullable=True, unique=True` |
| `passwordHash` | `str` | `String(255), nullable=False` |
| `accountStatus` | `str` | `String(255), nullable=False` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `updatedAt` | `datetime | None` | `DateTime, nullable=True` |
| `emailVerified` | `bool` | `Boolean, nullable=False, default=False` |
| `phoneVerified` | `bool` | `Boolean, nullable=False, default=False` |
| `lastLoginAt` | `datetime | None` | `DateTime, nullable=True` |

**Name-equivalent gaps:** missing from model: `account_type`, `email_verified_at`, `phone_verified_at`; model-only fields: `emailVerified`, `phoneVerified`, `lastLoginAt`.

**Specified relationships:**
- `users` 1:N `user_addresses` through `user_addresses.user_id`.
- `users` 1:N `user_documents` through `user_documents.user_id`.
- `users` 1:N `verifications` through `verifications.user_id`.
- `users` 1:1 `drivers` where a driver profile exists (`drivers.user_id` is UNIQUE).
- `users` 1:N `facility_staff` through `facility_staff.user_id`.
- `users` 1:1 `wallets` (`wallets.user_id` is UNIQUE).
- `users` 1:N `return_requests`, `reward_redemptions`, `disposal_certificates`, `notifications`, and `audit_logs` where applicable.

**Specified indexes / business constraints:**
- Unique indexes on `email` and `phone`.
- `account_type` must match the profile being created. If an account may hold multiple roles, replace this single field with a separate role-mapping table in a future schema revision; that would be an additional table beyond the current 39.
- Deactivate accounts rather than deleting users who have operational or financial history.

### 3.2 `user_addresses`

**Specification attributes (13):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `address_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `user_id` | BIGINT UNSIGNED | NN, FK → `users.user_id` |
| `address_label` | VARCHAR(40) | NULL; e.g. Home, Work; proposed |
| `address_line` | VARCHAR(255) | NN |
| `city` | VARCHAR(100) | NN |
| `state` | VARCHAR(100) | NN |
| `postal_code` | VARCHAR(10) | NN; supports Indian PIN codes and other formats |
| `latitude` | DECIMAL(10,7) | NULL |
| `longitude` | DECIMAL(10,7) | NULL |
| `is_default` | BOOLEAN | NN, DEFAULT FALSE |
| `is_active` | BOOLEAN | NN, DEFAULT TRUE; proposed |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP |

**SQLAlchemy model:** `UserAddress` (`userAddress`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `addressId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `userId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False` |
| `addressLine` | `str` | `String(255), nullable=False` |
| `city` | `str` | `String(255), nullable=False` |
| `state` | `str` | `String(255), nullable=False` |
| `postalCode` | `str` | `String(255), nullable=False` |
| `latitude` | `Decimal | None` | `Numeric(10, 7), nullable=True` |
| `longitude` | `Decimal | None` | `Numeric(10, 7), nullable=True` |
| `isDefault` | `bool` | `Boolean, nullable=False` |
| `addressLabel` | `str | None` | `String(255), nullable=True` |
| `landmark` | `str | None` | `String(255), nullable=True` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |

**Name-equivalent gaps:** missing from model: `is_active`, `updated_at`; model-only fields: `landmark`.

**Specified relationships:**
- Each address belongs to exactly one user.
- One user can have many addresses.
- One address can be referenced by many historical `return_requests`, but the application should prevent new use of an inactive address.

**Specified indexes / business constraints:**
- Index `user_id`.
- Validate latitude between -90 and 90 and longitude between -180 and 180 when supplied.
- Allow at most one active default address per user. Enforce this through a transaction in the application or a generated-column/unique-index strategy compatible with the deployed MySQL version.
- When an address is used by a return, preserve the address details for that request. If customers may edit/delete their address later, consider storing a pickup-address snapshot in `return_requests` in a future revision.

### 3.3 `user_documents`

**Specification attributes (11):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `document_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `user_id` | BIGINT UNSIGNED | NN, FK → `users.user_id` |
| `document_type` | VARCHAR(50) | NN; e.g. identity_proof, address_proof, prescription |
| `document_reference` | VARCHAR(100) | NULL; masked reference only, where legally appropriate |
| `storage_key` | VARCHAR(512) | NN; private object-storage key, not a public URL |
| `original_file_name` | VARCHAR(255) | NULL |
| `mime_type` | VARCHAR(100) | NN |
| `file_size_bytes` | BIGINT UNSIGNED | NULL |
| `document_status` | VARCHAR(20) | NN, DEFAULT `pending`; allowed: `pending`, `accepted`, `rejected`, `expired` |
| `uploaded_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `deleted_at` | DATETIME | NULL; proposed soft-delete timestamp |

**SQLAlchemy model:** `UserDocument` (`userDocument`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `documentId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `userId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False` |
| `documentType` | `str` | `String(255), nullable=False` |
| `documentNumber` | `str | None` | `String(255), nullable=True` |
| `filePath` | `str` | `String(255), nullable=False` |
| `uploadedAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `documentStatus` | `str` | `String(255), nullable=False` |
| `reviewedAt` | `datetime | None` | `DateTime, nullable=True` |

**Name-equivalent gaps:** missing from model: `document_reference`, `storage_key`, `original_file_name`, `mime_type`, `file_size_bytes`, `deleted_at`; model-only fields: `documentNumber`, `filePath`, `reviewedAt`.

**Specified relationships:**
- One user can upload many documents.
- One document can be referenced by many `verifications` if repeated review attempts are allowed.
- A prescription document can be referenced by one `prescriptions` row (`prescriptions.user_document_id` UNIQUE).

**Specified indexes / business constraints:**
- Index `(user_id, document_status)`.
- Restrict access to `storage_key`; never expose unrestricted document paths in API responses.
- Validate MIME type, file size, file signature, and upload permissions in the backend.
- Retention and deletion must follow the project's privacy and legal requirements.

### 3.4 `verifications`

**Specification attributes (9):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `verification_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `user_id` | BIGINT UNSIGNED | NN, FK → `users.user_id` |
| `document_id` | BIGINT UNSIGNED | NULL, FK → `user_documents.document_id`; NULL for verification not based on a file |
| `verification_type` | VARCHAR(50) | NN; e.g. identity, address, phone, prescription |
| `verification_status` | VARCHAR(20) | NN, DEFAULT `pending`; allowed: `pending`, `approved`, `rejected`, `requires_review` |
| `reviewed_by_user_id` | BIGINT UNSIGNED | NULL, FK → `users.user_id`; internal reviewer |
| `remarks` | TEXT | NULL; do not store unnecessary sensitive data |
| `submitted_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `reviewed_at` | DATETIME | NULL |

**SQLAlchemy model:** `Verification` (`verification`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `verificationId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `userId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False` |
| `documentId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("userDocument.documentId"), nullable=True, default=None` |
| `verificationType` | `str` | `String(255), nullable=False` |
| `verificationStatus` | `str` | `String(255), nullable=False` |
| `verifiedBy` | `UUID | None` | `Uuid(as_uuid=True), nullable=True, default=None` |
| `rejectionReason` | `str | None` | `Text, nullable=True` |
| `verifiedAt` | `datetime | None` | `DateTime, nullable=True` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |

**Name-equivalent gaps:** missing from model: `reviewed_by_user_id`, `remarks`, `submitted_at`, `reviewed_at`; model-only fields: `verifiedBy`, `rejectionReason`, `verifiedAt`, `createdAt`.

**Specified relationships:**
- One user can have many verification attempts.
- One document can have many verification attempts.
- One reviewer account can review many verification records.

**Specified indexes / business constraints:**
- Index `(user_id, verification_status)` and `document_id`.
- Require `reviewed_at` and `reviewed_by_user_id` when a review reaches a final state, subject to system-generated verification flows.
- A rejected attempt should remain in history; a resubmission creates a new row.

### 3.5 `medicines`

**Specification attributes (11):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `medicine_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `name` | VARCHAR(200) | NN |
| `generic_name` | VARCHAR(200) | NULL |
| `manufacturer` | VARCHAR(150) | NULL |
| `strength` | VARCHAR(80) | NULL; e.g. 500 mg |
| `dosage_form` | VARCHAR(50) | NULL; e.g. tablet, capsule, syrup |
| `barcode` | VARCHAR(100) | NULL, UQ when supplied |
| `medicine_category` | VARCHAR(100) | NULL; proposed catalogue classification |
| `is_active` | BOOLEAN | NN, DEFAULT TRUE |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP |

**SQLAlchemy model:** `Medicine` (`medicine`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `medicineId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `name` | `str` | `String(255), nullable=False` |
| `genericName` | `str | None` | `String(255), nullable=True` |
| `manufacturer` | `str | None` | `String(255), nullable=True` |
| `strength` | `str | None` | `String(255), nullable=True` |
| `dosageForm` | `str | None` | `String(255), nullable=True` |
| `barcode` | `str | None` | `String(255), nullable=True, unique=True` |
| `description` | `str | None` | `Text, nullable=True` |
| `medicineCategory` | `str | None` | `String(255), nullable=True` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |

**Name-equivalent gaps:** missing from model: `is_active`, `updated_at`; model-only fields: `description`.

**Specified relationships:**
- One medicine can have many `medicine_batches`.
- One medicine can appear in many `user_medicines` and `return_items`.

**Specified indexes / business constraints:**
- Index `name`, `generic_name`, and `manufacturer` for catalogue search.
- A missing barcode must be NULL, not an empty string; unique constraints permit multiple NULL values in MySQL.
- Keep catalogue entries inactive rather than deleting medicines already referenced by transactions.

### 3.6 `medicine_batches`

**Specification attributes (6):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `batch_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `medicine_id` | BIGINT UNSIGNED | NN, FK → `medicines.medicine_id` |
| `batch_number` | VARCHAR(100) | NN |
| `manufactured_on` | DATE | NULL |
| `expires_on` | DATE | NN |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |

**SQLAlchemy model:** `MedicineBatch` (`medicineBatch`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `batchId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `medicineId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("medicine.medicineId"), nullable=False` |
| `batchNumber` | `str` | `String(255), nullable=False` |
| `manufacturedOn` | `date | None` | `Date, nullable=True` |
| `expiresOn` | `date` | `Date, nullable=False` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |

**Name-equivalent gaps:** missing from model: None; model-only fields: None.

**Specified relationships:**
- Each batch belongs to one medicine.
- One medicine can have many batches.
- A batch can be referenced by many `user_medicines` and `return_items`.

**Specified indexes / business constraints:**
- UQ `(medicine_id, batch_number)`; the same printed batch number may exist for different medicines.
- CHECK `manufactured_on IS NULL OR manufactured_on <= expires_on`.
- Index `(medicine_id, expires_on)` for expiry-related lookup.
- If the batch is unknown, referencing columns in `user_medicines` or `return_items` may be NULL.

### 3.7 `user_medicines`

**Specification attributes (8):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `user_medicine_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `user_id` | BIGINT UNSIGNED | NN, FK → `users.user_id` |
| `medicine_id` | BIGINT UNSIGNED | NN, FK → `medicines.medicine_id` |
| `batch_id` | BIGINT UNSIGNED | NULL, FK → `medicine_batches.batch_id` |
| `quantity` | INT UNSIGNED | NN; CHECK `quantity > 0` |
| `packaging_state` | VARCHAR(40) | NN; controlled values such as sealed, opened, damaged, unknown |
| `added_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP |

**SQLAlchemy model:** `UserMedicine` (`userMedicine`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `userMedicineId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `userId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False` |
| `medicineId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("medicine.medicineId"), nullable=False` |
| `batchId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("medicineBatch.batchId"), nullable=True, default=None` |
| `quantity` | `int` | `Integer, nullable=False` |
| `packagingState` | `str` | `String(255), nullable=False` |
| `addedAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `notes` | `str | None` | `Text, nullable=True` |
| `sourcePlatform` | `str | None` | `String(40), nullable=True` |
| `externalOrderId` | `str | None` | `String(255), nullable=True` |
| `purchaseDate` | `date | None` | `Date, nullable=True` |
| `isDemo` | `bool` | `Boolean, nullable=False, default=False` |

**Name-equivalent gaps:** missing from model: `updated_at`; model-only fields: `notes`, `sourcePlatform`, `externalOrderId`, `purchaseDate`, `isDemo`.

**Specified relationships:**
- Each saved medicine belongs to one user and one catalogue medicine.
- One user can have many saved medicine records.
- One medicine or batch can be referenced by many saved records.
- One saved medicine can have many `medicine_routines`.

**Specified indexes / business constraints:**
- Index `(user_id, added_at)` and `(medicine_id, batch_id)`.
- Confirm whether multiple saved rows for the same user/medicine/batch are allowed. If not, add an appropriate unique key after defining how NULL batch IDs should be treated.
- The quantity here is the user's declared inventory, not verified facility inventory.

### 3.8 `medicine_routines`

**Specification attributes (10):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `routine_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `user_medicine_id` | BIGINT UNSIGNED | NN, FK → `user_medicines.user_medicine_id` |
| `routine_name` | VARCHAR(100) | NULL |
| `dosage_instruction` | VARCHAR(255) | NULL |
| `frequency` | VARCHAR(40) | NN; e.g. daily, twice_daily, weekly, custom |
| `reminder_times` | JSON | NULL; structured local-time reminder list |
| `start_date` | DATE | NN |
| `end_date` | DATE | NULL |
| `routine_status` | VARCHAR(20) | NN, DEFAULT `active`; allowed: active, paused, completed, cancelled |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |

**SQLAlchemy model:** `MedicineRoutine` (`medicineRoutine`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `routineId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `userId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False` |
| `userMedicineId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("userMedicine.userMedicineId"), nullable=False` |
| `routineName` | `str | None` | `String(255), nullable=True` |
| `dosage` | `str` | `String(255), nullable=False` |
| `frequency` | `str` | `String(255), nullable=False` |
| `startDate` | `date` | `Date, nullable=False` |
| `endDate` | `date | None` | `Date, nullable=True` |
| `reminderTime` | `dict | None` | `JSON, nullable=True` |
| `routineStatus` | `str` | `String(255), nullable=False` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |

**Name-equivalent gaps:** missing from model: `dosage_instruction`, `reminder_times`; model-only fields: `userId`, `dosage`, `reminderTime`.

**Specified relationships:**
- Each routine belongs to one saved user-medicine record.
- One saved medicine can have multiple routines over time.

**Specified indexes / business constraints:**
- Index `(user_medicine_id, routine_status)`.
- CHECK `end_date IS NULL OR end_date >= start_date`.
- Validate reminder JSON structure in the backend.

### 3.9 `prescriptions`

**Specification attributes (9):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `prescription_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `user_id` | BIGINT UNSIGNED | NN, FK → `users.user_id` |
| `user_document_id` | BIGINT UNSIGNED | NN, UQ, FK → `user_documents.document_id` |
| `prescriber_name` | VARCHAR(150) | NULL |
| `prescriber_registration_no` | VARCHAR(100) | NULL; only where applicable and lawfully collected |
| `issued_on` | DATE | NULL |
| `valid_until` | DATE | NULL |
| `prescription_status` | VARCHAR(20) | NN, DEFAULT `submitted`; allowed: submitted, verified, rejected, expired |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |

**SQLAlchemy model:** `Prescription` (`prescription`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `prescriptionId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `userId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False` |
| `medicineId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("medicine.medicineId"), nullable=True, default=None` |
| `prescriptionFile` | `str` | `String(255), nullable=False` |
| `prescribingDoctor` | `str | None` | `String(255), nullable=True` |
| `prescriptionDate` | `date | None` | `Date, nullable=True` |
| `expiryDate` | `date | None` | `Date, nullable=True` |
| `verificationStatus` | `str` | `String(255), nullable=False` |
| `uploadedAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |

**Name-equivalent gaps:** missing from model: `user_document_id`, `prescriber_name`, `prescriber_registration_no`, `issued_on`, `valid_until`, `prescription_status`, `created_at`; model-only fields: `medicineId`, `prescriptionFile`, `prescribingDoctor`, `prescriptionDate`, `expiryDate`, `verificationStatus`, `uploadedAt`.

**Specified relationships:**
- Each prescription belongs to one user and one uploaded document.
- One user document can map to at most one prescription record.

**Specified indexes / business constraints:**
- Index `(user_id, prescription_status)`.
- The application must verify that the referenced document belongs to the same user.
- This table records prescription metadata; it is not a prescription-line table. If MediCycle later needs structured medicine items per prescription, an additional `prescription_items` table would be required and would increase the table count beyond 39.

### 3.10 `return_requests`

**Specification attributes (10):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `return_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `user_id` | BIGINT UNSIGNED | NN, FK → `users.user_id` |
| `address_id` | BIGINT UNSIGNED | NULL, FK → `user_addresses.address_id`; required for pickup method |
| `return_method` | VARCHAR(20) | NN; allowed: pickup, pharmacy_dropoff |
| `pickup_slot_id` | BIGINT UNSIGNED | NULL, FK → `pickup_slots.pickup_slot_id`; required for scheduled pickup |
| `dropoff_facility_id` | BIGINT UNSIGNED | NULL, FK → `facilities.facility_id`; proposed, required for pharmacy drop-off |
| `status` | VARCHAR(30) | NN, DEFAULT `submitted`; controlled return workflow status |
| `customer_notes` | TEXT | NULL |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP |

**SQLAlchemy model:** `ReturnRequest` (`returnRequest`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `returnId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `userId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False` |
| `addressId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("userAddress.addressId"), nullable=True, default=None` |
| `returnMethod` | `str` | `String(255), nullable=False` |
| `pickupSlotId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("pickupSlot.pickupSlotId"), nullable=True, default=None` |
| `status` | `str` | `String(255), nullable=False` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `facilityId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=True, default=None` |
| `requestNotes` | `str | None` | `Text, nullable=True` |
| `verifiedAt` | `datetime | None` | `DateTime, nullable=True` |
| `rejectionReason` | `str | None` | `Text, nullable=True` |
| `completedAt` | `datetime | None` | `DateTime, nullable=True` |

**Name-equivalent gaps:** missing from model: `dropoff_facility_id`, `customer_notes`, `updated_at`; model-only fields: `facilityId`, `requestNotes`, `verifiedAt`, `rejectionReason`, `completedAt`.

**Specified relationships:**
- Each return belongs to one user.
- One return contains one or more `return_items`.
- One address and one pickup slot can be referenced by many return requests over time.
- One return can have multiple historical `pickup_assignments`.
- One return has many `return_status_history` rows.
- One return may eventually receive one `disposal_certificate`.

**Specified indexes / business constraints:**
- Index `(user_id, created_at)` and `(status, created_at)`.
- For `pickup`, require `address_id` and `pickup_slot_id`; for `pharmacy_dropoff`, require `dropoff_facility_id`. Enforce this using CHECK constraints where practical and backend validation in all cases.
- Confirm whether drop-off returns can be accepted at any facility or only an authorized facility.
- Do not delete submitted returns; use cancellation/status transitions.

### 3.11 `return_items`

**Specification attributes (13):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `return_item_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `return_id` | BIGINT UNSIGNED | NN, FK → `return_requests.return_id` |
| `medicine_id` | BIGINT UNSIGNED | NN, FK → `medicines.medicine_id` |
| `batch_id` | BIGINT UNSIGNED | NULL, FK → `medicine_batches.batch_id` |
| `quantity` | INT UNSIGNED | NN; CHECK `quantity > 0` |
| `quantity_unit` | VARCHAR(20) | NN, DEFAULT `unit`; proposed unit label, e.g. tablet, bottle, pack |
| `packaging_condition` | VARCHAR(40) | NULL; customer-declared or inspected condition must be distinguished in the workflow |
| `inspection_status` | VARCHAR(20) | NN, DEFAULT `pending`; allowed: pending, accepted, partially_accepted, rejected |
| `accepted_quantity` | INT UNSIGNED | NN, DEFAULT 0 |
| `rejected_quantity` | INT UNSIGNED | NN, DEFAULT 0 |
| `credits_awarded` | DECIMAL(12,2) | NULL; credits attributed to this item if the reward policy calculates item-level credits |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP |

**SQLAlchemy model:** `ReturnItem` (`returnItem`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `returnItemId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `returnId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=False` |
| `medicineId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("medicine.medicineId"), nullable=False` |
| `batchId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("medicineBatch.batchId"), nullable=True, default=None` |
| `quantity` | `int` | `Integer, nullable=False` |
| `packagingCondition` | `str | None` | `String(255), nullable=True` |
| `inspectionStatus` | `str` | `String(255), nullable=False` |
| `creditsAwarded` | `Decimal` | `Numeric(12, 2), nullable=False` |

**Name-equivalent gaps:** missing from model: `quantity_unit`, `accepted_quantity`, `rejected_quantity`, `created_at`, `updated_at`; model-only fields: None.

**Specified relationships:**
- Each return item belongs to one return request and one catalogue medicine.
- A batch may be referenced by many return items.
- A return item can have many `inspection_records`, `bin_items`, `custody_transfers`, and `disposal_records` over its lifecycle.

**Specified indexes / business constraints:**
- Index `return_id`, `(medicine_id, batch_id)`, and `inspection_status`.
- CHECK `accepted_quantity + rejected_quantity <= quantity`.
- Accepted and rejected quantities are set after inspection; the initial customer submission should not be treated as accepted inventory.
- If units are split across multiple inspection/disposal events, quantities must be updated transactionally and checked against the original quantity.

### 3.12 `pickup_slots`

**Specification attributes (8):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `pickup_slot_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `slot_start` | DATETIME | NN |
| `slot_end` | DATETIME | NN |
| `service_postal_code` | VARCHAR(10) | NULL; proposed service-area restriction |
| `max_bookings` | INT UNSIGNED | NN; CHECK `max_bookings > 0` |
| `booked_count` | INT UNSIGNED | NN, DEFAULT 0; maintained transactionally |
| `slot_status` | VARCHAR(20) | NN, DEFAULT `available`; allowed: available, full, closed, cancelled |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |

**SQLAlchemy model:** `PickupSlot` (`pickupSlot`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `pickupSlotId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `facilityId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False` |
| `slotDate` | `date` | `Date, nullable=False` |
| `startTime` | `datetime` | `DateTime, nullable=False` |
| `endTime` | `datetime` | `DateTime, nullable=False` |
| `capacity` | `int` | `Integer, nullable=False` |
| `bookedCount` | `int` | `Integer, nullable=False` |
| `slotStatus` | `str` | `String(255), nullable=False` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |

**Name-equivalent gaps:** missing from model: `slot_start`, `slot_end`, `service_postal_code`, `max_bookings`; model-only fields: `facilityId`, `slotDate`, `startTime`, `endTime`, `capacity`.

**Specified relationships:**
- One pickup slot can be selected by many return requests, up to its capacity.
- Each return request references at most one selected slot.

**Specified indexes / business constraints:**
- CHECK `slot_end > slot_start` and `booked_count <= max_bookings`.
- Index `(slot_start, slot_status)` and `service_postal_code`.
- Booking must use a transaction/row lock so two users cannot claim the final slot simultaneously.
- Do not allow new bookings for a closed or cancelled slot.

### 3.13 `pickup_assignments`

**Specification attributes (9):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `assignment_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `return_id` | BIGINT UNSIGNED | NN, FK → `return_requests.return_id` |
| `driver_id` | BIGINT UNSIGNED | NN, FK → `drivers.driver_id` |
| `vehicle_id` | BIGINT UNSIGNED | NULL, FK → `vehicles.vehicle_id` |
| `collection_manifest_id` | BIGINT UNSIGNED | NULL, FK → `collection_manifests.manifest_id`; proposed grouping link |
| `assigned_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `assignment_status` | VARCHAR(20) | NN, DEFAULT `assigned`; allowed: assigned, accepted, in_progress, completed, failed, cancelled, reassigned |
| `completed_at` | DATETIME | NULL |
| `assignment_notes` | TEXT | NULL |

**SQLAlchemy model:** `PickupAssignment` (`pickupAssignment`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `assignmentId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `returnId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=False` |
| `driverId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("driver.driverId"), nullable=False` |
| `vehicleId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("vehicle.vehicleId"), nullable=True, default=None` |
| `assignedAt` | `datetime` | `DateTime, nullable=False` |
| `status` | `str` | `String(255), nullable=False` |
| `routeId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("route.routeId"), nullable=True, default=None` |
| `acceptedAt` | `datetime | None` | `DateTime, nullable=True` |
| `completedAt` | `datetime | None` | `DateTime, nullable=True` |

**Name-equivalent gaps:** missing from model: `collection_manifest_id`, `assignment_status`, `assignment_notes`; model-only fields: `status`, `routeId`, `acceptedAt`.

**Specified relationships:**
- One return can have multiple assignments over time; only one assignment should be active at a time.
- One driver and one vehicle can be associated with many assignments over time.
- One collection manifest can group many pickup assignments.
- A route stop may reference a pickup assignment.

**Specified indexes / business constraints:**
- Index `(driver_id, assignment_status)`, `(return_id, assigned_at)`, and `collection_manifest_id`.
- Enforce one active assignment per return in application logic using a transaction/locking strategy. MySQL does not provide a simple partial unique index for this rule.
- Validate that the selected vehicle is available and appropriate for the driver/route.

### 3.14 `return_status_history`

**Specification attributes (8):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `history_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `return_id` | BIGINT UNSIGNED | NN, FK → `return_requests.return_id` |
| `old_status` | VARCHAR(30) | NULL for the first event |
| `new_status` | VARCHAR(30) | NN |
| `changed_by_user_id` | BIGINT UNSIGNED | NULL, FK → `users.user_id` |
| `changed_by_driver_id` | BIGINT UNSIGNED | NULL, FK → `drivers.driver_id` |
| `reason` | TEXT | NULL |
| `changed_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |

**SQLAlchemy model:** Not found

**Model attributes:** no corresponding model class was found.

**Specified relationships:**
- One return request has many status-history rows.
- A user or driver may be recorded as the actor for a status change.

**Specified indexes / business constraints:**
- Index `(return_id, changed_at)`.
- Status-history rows are append-only; do not update or delete them during normal operation.
- At most one actor field should be populated when the change is performed by an individual. System-generated events may have both actor fields NULL.
- The current `return_requests.status` must be updated in the same transaction as the history row.

### 3.15 `wallets`

**Specification attributes (6):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `wallet_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `user_id` | BIGINT UNSIGNED | NN, UQ, FK → `users.user_id`; one wallet per user |
| `available_balance` | DECIMAL(12,2) | NN, DEFAULT 0.00; cached current balance |
| `wallet_status` | VARCHAR(20) | NN, DEFAULT `active`; allowed: active, frozen, closed |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP |

**SQLAlchemy model:** `Wallet` (`wallet`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `walletId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `userId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False, unique=True` |
| `availableBalance` | `Decimal` | `Numeric(12, 2), nullable=False` |
| `walletStatus` | `str` | `String(255), nullable=False` |
| `updatedAt` | `datetime` | `DateTime, nullable=False` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |

**Name-equivalent gaps:** missing from model: None; model-only fields: None.

**Specified relationships:**
- Each wallet belongs to exactly one user.
- One wallet has many wallet transactions.

**Specified indexes / business constraints:**
- Unique `user_id` enforces one wallet per user.
- Balance changes must be performed only by backend service operations, never by direct customer edits.
- Update the wallet balance and insert the corresponding `wallet_transactions` row in the same database transaction.
- Reconciliation must be possible by comparing the cached balance with the sum of ledger movements.

### 3.16 `wallet_transactions`

**Specification attributes (10):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `transaction_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `wallet_id` | BIGINT UNSIGNED | NN, FK → `wallets.wallet_id` |
| `return_id` | BIGINT UNSIGNED | NULL, FK → `return_requests.return_id`; source for earning credits |
| `redemption_id` | BIGINT UNSIGNED | NULL, UQ, FK → `reward_redemptions.redemption_id`; one debit transaction per redemption |
| `transaction_type` | VARCHAR(20) | NN; allowed: earn, redeem, donate, adjustment |
| `amount` | DECIMAL(12,2) | NN; signed amount: positive credits the wallet, negative debits it |
| `balance_after` | DECIMAL(12,2) | NN; balance after this transaction |
| `idempotency_key` | VARCHAR(100) | NULL, UQ; proposed duplicate-request protection |
| `description` | VARCHAR(255) | NULL |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |

**SQLAlchemy model:** `WalletTransaction` (`walletTransaction`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `transactionId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `walletId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("wallet.walletId"), nullable=False` |
| `returnId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=True, default=None` |
| `redemptionId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("rewardRedemption.redemptionId"), nullable=True, default=None` |
| `transactionType` | `str` | `String(255), nullable=False` |
| `amount` | `Decimal` | `Numeric(12, 2), nullable=False` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `referenceCode` | `str | None` | `String(255), nullable=True, unique=True` |
| `description` | `str | None` | `Text, nullable=True` |

**Name-equivalent gaps:** missing from model: `balance_after`, `idempotency_key`; model-only fields: `referenceCode`.

**Specified relationships:**
- Each transaction belongs to one wallet.
- A return may generate one or more earning/adjustment transactions, depending on the rewards rules.
- A reward redemption has one corresponding redemption debit transaction.

**Specified indexes / business constraints:**
- Index `(wallet_id, created_at)` and `return_id`.
- CHECK `amount <> 0`.
- For a redemption transaction, `amount` must be negative and `redemption_id` must be present. For an earn transaction, amount must be positive.
- A transaction is immutable after posting. Corrections should be made with a compensating adjustment transaction, not by editing the original row.
- Insert the transaction and update `wallets.available_balance` atomically. Lock the wallet row during concurrent spending operations.

### 3.17 `rewards`

**Specification attributes (10):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `reward_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `partner_name` | VARCHAR(150) | NN |
| `title` | VARCHAR(150) | NN |
| `description` | TEXT | NULL |
| `credits_required` | DECIMAL(12,2) | NN; CHECK `credits_required > 0` |
| `valid_until` | DATETIME | NULL |
| `status` | VARCHAR(20) | NN, DEFAULT `available`; allowed: available, unavailable, expired, archived |
| `stock_quantity` | INT UNSIGNED | NULL; NULL means not quantity-limited |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP |

**SQLAlchemy model:** `Reward` (`reward`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `rewardId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `partnerName` | `str` | `String(255), nullable=False` |
| `title` | `str` | `String(255), nullable=False` |
| `description` | `str | None` | `Text, nullable=True` |
| `creditsRequired` | `Decimal` | `Numeric(12, 2), nullable=False` |
| `validUntil` | `datetime | None` | `DateTime, nullable=True` |
| `status` | `str` | `String(255), nullable=False` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `imagePath` | `str | None` | `String(255), nullable=True` |

**Name-equivalent gaps:** missing from model: `stock_quantity`, `updated_at`; model-only fields: `imagePath`.

**Specified relationships:**
- One reward can have many reward redemptions.

**Specified indexes / business constraints:**
- Index `(status, valid_until)`.
- Do not delete a reward that has historical redemptions; archive it instead.
- Check expiry and available stock within the redemption transaction.

### 3.18 `reward_redemptions`

**Specification attributes (8):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `redemption_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `user_id` | BIGINT UNSIGNED | NN, FK → `users.user_id` |
| `reward_id` | BIGINT UNSIGNED | NN, FK → `rewards.reward_id` |
| `credits_used` | DECIMAL(12,2) | NN; CHECK `credits_used > 0` |
| `redemption_code` | VARCHAR(100) | NULL, UQ; may be generated by the partner after fulfilment |
| `status` | VARCHAR(20) | NN, DEFAULT `pending`; allowed: pending, issued, fulfilled, failed, cancelled, reversed |
| `redeemed_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `fulfilled_at` | DATETIME | NULL |

**SQLAlchemy model:** `RewardRedemption` (`rewardRedemption`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `redemptionId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `userId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False` |
| `rewardId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("reward.rewardId"), nullable=False` |
| `creditsUsed` | `Decimal` | `Numeric(12, 2), nullable=False` |
| `redemptionCode` | `str` | `String(255), nullable=False, unique=True` |
| `status` | `str` | `String(255), nullable=False` |
| `redeemedAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `expiresAt` | `datetime | None` | `DateTime, nullable=True` |

**Name-equivalent gaps:** missing from model: `fulfilled_at`; model-only fields: `expiresAt`.

**Specified relationships:**
- Each redemption belongs to one user and one reward.
- One redemption has one corresponding debit row in `wallet_transactions` when credits are charged.

**Specified indexes / business constraints:**
- Index `(user_id, redeemed_at)` and `(reward_id, status)`.
- Validate reward availability and wallet balance before charging credits.
- Create the redemption, wallet transaction, and wallet balance update in one transaction. If partner fulfilment is external, use a pending/issued workflow and compensating reversal where necessary.
- Do not assume `credits_used` will always equal the current reward price; it records the price at redemption time.

### 3.19 `disposal_certificates`

**Specification attributes (7):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `certificate_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `certificate_code` | VARCHAR(100) | NN, UQ; public reference |
| `user_id` | BIGINT UNSIGNED | NN, FK → `users.user_id` |
| `return_id` | BIGINT UNSIGNED | NN, UQ, FK → `return_requests.return_id`; proposed one certificate per return |
| `issued_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `certificate_status` | VARCHAR(20) | NN, DEFAULT `issued`; allowed: issued, revoked |
| `file_storage_key` | VARCHAR(512) | NULL; private certificate file location |

**SQLAlchemy model:** `DisposalCertificate` (`disposalCertificate`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `certificateId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `returnId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=False` |
| `disposalRecordId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("disposalRecord.disposalRecordId"), nullable=True, default=None` |
| `certificateNumber` | `str` | `String(255), nullable=False, unique=True` |
| `certificateFile` | `str` | `String(255), nullable=False` |
| `issuedAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `certificateStatus` | `str` | `String(255), nullable=False` |

**Name-equivalent gaps:** missing from model: `certificate_code`, `user_id`, `file_storage_key`; model-only fields: `disposalRecordId`, `certificateNumber`, `certificateFile`.

**Specified relationships:**
- Each certificate belongs to one user and one return request.
- A user can receive many certificates across different returns.
- A return request can have at most one certificate under the proposed one-certificate-per-return rule.
- Disposal completion is established through the return items and disposal records; the certificate does not replace those records.

**Specified indexes / business constraints:**
- Unique `certificate_code` and `return_id`.
- Before issue, verify that every accepted return item linked to the return has a completed disposal record. The exact eligibility rule must be finalized with the business workflow.
- Do not issue a certificate merely because a pickup has occurred.

### 3.20 `facilities`

**Specification attributes (14):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `facility_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `facility_name` | VARCHAR(150) | NN |
| `facility_type` | VARCHAR(30) | NN; allowed: pharmacy, hub, disposal_centre |
| `address` | VARCHAR(500) | NN |
| `city` | VARCHAR(100) | NN |
| `state` | VARCHAR(100) | NN |
| `postal_code` | VARCHAR(10) | NN |
| `latitude` | DECIMAL(10,7) | NULL |
| `longitude` | DECIMAL(10,7) | NULL |
| `authorization_status` | VARCHAR(20) | NN; e.g. pending, authorized, suspended, expired |
| `operating_status` | VARCHAR(20) | NN, DEFAULT `active`; e.g. active, inactive, temporarily_closed |
| `contact_phone` | VARCHAR(20) | NULL |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP |

**SQLAlchemy model:** `Facility` (`facility`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `facilityId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `facilityName` | `str` | `String(255), nullable=False` |
| `facilityType` | `str` | `String(255), nullable=False` |
| `address` | `str` | `String(255), nullable=False` |
| `latitude` | `Decimal | None` | `Numeric(10, 7), nullable=True` |
| `longitude` | `Decimal | None` | `Numeric(10, 7), nullable=True` |
| `authorizationStatus` | `str` | `String(255), nullable=False` |
| `operatingStatus` | `str` | `String(255), nullable=False` |
| `contactPhone` | `str | None` | `String(255), nullable=True` |
| `contactEmail` | `str | None` | `String(255), nullable=True` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |

**Name-equivalent gaps:** missing from model: `city`, `state`, `postal_code`, `updated_at`; model-only fields: `contactEmail`.

**Specified relationships:**
- One facility has many `facility_staff`, `storage_bins`, and `vehicles`.
- A facility may be an origin or destination for many `collection_manifests`.
- A facility receives many `facility_intakes` and processes many `disposal_batches` and `disposal_records`.
- A facility may be selected as a drop-off location by many return requests.

**Specified indexes / business constraints:**
- Index `(facility_type, authorization_status, operating_status)` and postal code.
- Only an authorized, operational facility can be offered for relevant workflows.
- Coordinates must be within valid latitude/longitude ranges.

### 3.21 `facility_staff`

**Specification attributes (7):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `staff_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `facility_id` | BIGINT UNSIGNED | NN, FK → `facilities.facility_id` |
| `user_id` | BIGINT UNSIGNED | NN, FK → `users.user_id` |
| `staff_role` | VARCHAR(40) | NN; e.g. pharmacist, intake_operator, facility_manager, inspector |
| `staff_status` | VARCHAR(20) | NN, DEFAULT `active`; allowed: active, inactive, suspended |
| `joined_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `left_at` | DATETIME | NULL |

**SQLAlchemy model:** Not found

**Model attributes:** no corresponding model class was found.

**Specified relationships:**
- Each staff membership belongs to one facility and one user.
- One facility can have many staff memberships.
- One user can have multiple facility memberships if the business permits it.
- Staff records can be referenced by inspections, intakes, tamper-seal operations, disposal batches, and custody transfers.

**Specified indexes / business constraints:**
- UQ `(facility_id, user_id)` to prevent duplicate active membership rows for the same facility/user. If rejoining history must be retained, use a separate membership lifecycle rule instead of deleting old rows.
- Index `(user_id, staff_status)`.
- Validate that `users.account_type` is `facility_staff` or an appropriately authorized account type.

### 3.22 `storage_bins`

**Specification attributes (8):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `bin_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `facility_id` | BIGINT UNSIGNED | NN, FK → `facilities.facility_id` |
| `bin_code` | VARCHAR(80) | NN; QR/printed identifier |
| `storage_category` | VARCHAR(50) | NN; e.g. quarantined, inspected, accepted, hazardous_pending |
| `capacity_units` | INT UNSIGNED | NN; CHECK `capacity_units > 0` |
| `current_units` | INT UNSIGNED | NN, DEFAULT 0; maintained transactionally |
| `bin_status` | VARCHAR(20) | NN, DEFAULT `active`; allowed: active, full, blocked, decommissioned |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |

**SQLAlchemy model:** `StorageBin` (`storageBin`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `binId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `facilityId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False` |
| `binCode` | `str` | `String(255), nullable=False` |
| `storageCategory` | `str` | `String(255), nullable=False` |
| `capacityUnits` | `int` | `Integer, nullable=False` |
| `currentUnits` | `int` | `Integer, nullable=False` |
| `sealCode` | `str | None` | `String(255), nullable=True` |
| `binStatus` | `str` | `String(255), nullable=False` |
| `lastInspectedAt` | `datetime | None` | `DateTime, nullable=True` |

**Name-equivalent gaps:** missing from model: `created_at`; model-only fields: `sealCode`, `lastInspectedAt`.

**Specified relationships:**
- Each bin belongs to one facility.
- One bin can have many historical/current `bin_items` placement rows.
- One bin can have many `tamper_seals` over time.

**Specified indexes / business constraints:**
- UQ `(facility_id, bin_code)`.
- Index `(facility_id, storage_category, bin_status)`.
- CHECK `current_units <= capacity_units`.
- Maintain `current_units` in the same transaction as insert/move/remove of `bin_items`; periodically reconcile it against active placements.
- The original `sealCode` idea is represented by the `tamper_seals` table rather than storing duplicate seal details on the bin.

### 3.23 `bin_items`

**Specification attributes (9):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `bin_item_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `bin_id` | BIGINT UNSIGNED | NN, FK → `storage_bins.bin_id` |
| `return_item_id` | BIGINT UNSIGNED | NN, FK → `return_items.return_item_id` |
| `facility_intake_id` | BIGINT UNSIGNED | NN, FK → `facility_intakes.intake_id` |
| `quantity` | INT UNSIGNED | NN; CHECK `quantity > 0` |
| `placement_status` | VARCHAR(20) | NN, DEFAULT `stored`; allowed: stored, removed, transferred, quarantined |
| `stored_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `removed_at` | DATETIME | NULL |
| `removal_reason` | VARCHAR(100) | NULL |

**SQLAlchemy model:** `BinItem` (`binItem`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `binItemId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `binId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("storageBin.binId"), nullable=False` |
| `returnItemId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("returnItem.returnItemId"), nullable=False` |
| `quantityStored` | `int` | `Integer, nullable=False` |
| `storedAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `removedAt` | `datetime | None` | `DateTime, nullable=True` |
| `storageStatus` | `str` | `String(255), nullable=False` |

**Name-equivalent gaps:** missing from model: `facility_intake_id`, `quantity`, `placement_status`, `removal_reason`; model-only fields: `quantityStored`, `storageStatus`.

**Specified relationships:**
- Each placement belongs to one storage bin, one return item, and one facility intake.
- A return item can have multiple bin placement rows over time or across bins.
- A facility intake can result in many bin placements.

**Specified indexes / business constraints:**
- Index `(bin_id, placement_status)` and `(return_item_id, stored_at)`.
- A placement's facility must match the facility of its bin and intake; enforce this in the service layer or use composite keys if strict database enforcement is required.
- Moving a placement must update the previous row, insert the new row, and update bin quantities atomically.
- Do not represent unreceived customer-declared items as facility inventory.

### 3.24 `inspection_records`

**Specification attributes (9):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `inspection_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `facility_intake_id` | BIGINT UNSIGNED | NN, FK → `facility_intakes.intake_id` |
| `return_item_id` | BIGINT UNSIGNED | NN, FK → `return_items.return_item_id` |
| `facility_id` | BIGINT UNSIGNED | NN, FK → `facilities.facility_id` |
| `inspected_by_staff_id` | BIGINT UNSIGNED | NN, FK → `facility_staff.staff_id` |
| `inspection_result` | VARCHAR(30) | NN; e.g. accepted, rejected, quarantined, requires_review |
| `packaging_condition` | VARCHAR(40) | NULL |
| `inspection_notes` | TEXT | NULL |
| `inspected_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |

**SQLAlchemy model:** `InspectionRecord` (`inspectionRecord`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `inspectionId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `facilityId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False` |
| `binId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("storageBin.binId"), nullable=True, default=None` |
| `inspectedBy` | `UUID` | `Uuid(as_uuid=True), ForeignKey("facilityStaff.facilityStaffId"), nullable=False` |
| `inspectionType` | `str` | `String(255), nullable=False` |
| `inspectionResult` | `str` | `String(255), nullable=False` |
| `findings` | `str | None` | `Text, nullable=True` |
| `inspectedAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `correctiveAction` | `str | None` | `Text, nullable=True` |

**Name-equivalent gaps:** missing from model: `facility_intake_id`, `return_item_id`, `inspected_by_staff_id`, `packaging_condition`, `inspection_notes`; model-only fields: `binId`, `inspectedBy`, `inspectionType`, `findings`, `correctiveAction`.

**Specified relationships:**
- Each inspection refers to one intake, one return item, one facility, and one staff member.
- One return item can have multiple inspection records.
- One facility intake can include many inspections.

**Specified indexes / business constraints:**
- Index `(return_item_id, inspected_at)`, `facility_intake_id`, and `inspected_by_staff_id`.
- Validate that the staff member and intake belong to the stated facility.
- Update `return_items.inspection_status` and accepted/rejected quantities in the same transaction as the inspection decision.

### 3.25 `tamper_seals`

**Specification attributes (9):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `tamper_seal_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `bin_id` | BIGINT UNSIGNED | NN, FK → `storage_bins.bin_id` |
| `seal_code` | VARCHAR(100) | NN, UQ; printed/QR seal identifier |
| `seal_status` | VARCHAR(20) | NN, DEFAULT `applied`; allowed: applied, removed, broken, replaced |
| `applied_by_staff_id` | BIGINT UNSIGNED | NN, FK → `facility_staff.staff_id` |
| `removed_by_staff_id` | BIGINT UNSIGNED | NULL, FK → `facility_staff.staff_id` |
| `applied_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `removed_at` | DATETIME | NULL |
| `seal_notes` | TEXT | NULL |

**SQLAlchemy model:** `TamperSeal` (`tamperSeal`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `tamperSealId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `binId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("storageBin.binId"), nullable=True, default=None` |
| `manifestId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("collectionManifest.manifestId"), nullable=True, default=None` |
| `sealCode` | `str` | `String(255), nullable=False, unique=True` |
| `sealStatus` | `str` | `String(255), nullable=False` |
| `appliedBy` | `UUID | None` | `Uuid(as_uuid=True), nullable=True, default=None` |
| `appliedAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `brokenBy` | `UUID | None` | `Uuid(as_uuid=True), nullable=True, default=None` |
| `brokenAt` | `datetime | None` | `DateTime, nullable=True` |
| `breakReason` | `str | None` | `Text, nullable=True` |

**Name-equivalent gaps:** missing from model: `applied_by_staff_id`, `removed_by_staff_id`, `removed_at`, `seal_notes`; model-only fields: `manifestId`, `appliedBy`, `brokenBy`, `brokenAt`, `breakReason`.

**Specified relationships:**
- Each seal record belongs to one bin.
- A bin can have many seal records over time.
- Staff members are recorded as the people who apply/remove seals.

**Specified indexes / business constraints:**
- Unique `seal_code`; index `(bin_id, seal_status)`.
- A bin should have no more than one currently applied seal. Enforce through a transaction/application rule or a suitable generated-column unique key.
- Seal removal/replacement must preserve the previous record rather than overwrite it.

### 3.26 `drivers`

**Specification attributes (7):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `driver_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `user_id` | BIGINT UNSIGNED | NN, UQ, FK → `users.user_id`; one driver profile per account |
| `verification_status` | VARCHAR(20) | NN, DEFAULT `pending`; allowed: pending, verified, rejected, suspended |
| `availability_status` | VARCHAR(20) | NN, DEFAULT `unavailable`; allowed: available, unavailable, on_task, suspended |
| `license_reference` | VARCHAR(100) | NULL; store only the necessary reference, not excess personal data |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP |

**SQLAlchemy model:** `Driver` (`driver`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `driverId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `fullName` | `str` | `String(255), nullable=False` |
| `phone` | `str` | `String(255), nullable=False, unique=True` |
| `verificationStatus` | `str` | `String(255), nullable=False` |
| `availabilityStatus` | `str` | `String(255), nullable=False` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `userId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=True` |
| `licenseNumber` | `str | None` | `String(255), nullable=True, unique=True` |
| `licenseExpiry` | `date | None` | `Date, nullable=True` |

**Name-equivalent gaps:** missing from model: `license_reference`, `updated_at`; model-only fields: `fullName`, `phone`, `licenseNumber`, `licenseExpiry`.

**Specified relationships:**
- Each driver profile belongs to one user account.
- One driver can have many pickup assignments, routes, manifests, tracking logs, and custody transfers.

**Specified indexes / business constraints:**
- Unique `user_id`.
- Index `(availability_status, verification_status)`.
- Only verified, active drivers may receive assignments.
- Driver name and phone are read from the linked `users` record to avoid duplicate authoritative copies.

### 3.27 `vehicles`

**Specification attributes (7):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `vehicle_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `facility_id` | BIGINT UNSIGNED | NULL, FK → `facilities.facility_id`; owning/operating facility |
| `registration_number` | VARCHAR(30) | NN, UQ |
| `vehicle_type` | VARCHAR(40) | NN; e.g. two_wheeler, van, truck |
| `capacity_kg` | DECIMAL(10,2) | NULL; CHECK `capacity_kg > 0` when supplied |
| `vehicle_status` | VARCHAR(20) | NN, DEFAULT `active`; allowed: active, maintenance, inactive |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |

**SQLAlchemy model:** `Vehicle` (`vehicle`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `vehicleId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `registrationNumber` | `str` | `String(255), nullable=False, unique=True` |
| `vehicleType` | `str` | `String(255), nullable=False` |
| `capacityKg` | `Decimal` | `Numeric(12, 2), nullable=False` |
| `vehicleStatus` | `str` | `String(255), nullable=False` |
| `assignedDriverId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("driver.driverId"), nullable=True, default=None` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |

**Name-equivalent gaps:** missing from model: `facility_id`; model-only fields: `assignedDriverId`.

**Specified relationships:**
- A facility may operate many vehicles.
- One vehicle can be used in many pickup assignments and routes over time.
- A vehicle may be associated with many collection manifests over time.

**Specified indexes / business constraints:**
- Unique registration number; index `(facility_id, vehicle_status)`.
- Confirm vehicle ownership/lease model and whether vehicles may move between facilities.
- Validate that the vehicle is not simultaneously assigned to incompatible active routes or pickups.

### 3.28 `routes`

**Specification attributes (10):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `route_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `driver_id` | BIGINT UNSIGNED | NN, FK → `drivers.driver_id` |
| `vehicle_id` | BIGINT UNSIGNED | NULL, FK → `vehicles.vehicle_id` |
| `route_date` | DATE | NN |
| `planned_start_at` | DATETIME | NULL |
| `planned_end_at` | DATETIME | NULL |
| `actual_start_at` | DATETIME | NULL |
| `actual_end_at` | DATETIME | NULL |
| `route_status` | VARCHAR(20) | NN, DEFAULT `planned`; allowed: planned, assigned, in_progress, completed, cancelled |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |

**SQLAlchemy model:** `Route` (`route`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `routeId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `routeName` | `str` | `String(255), nullable=False` |
| `driverId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("driver.driverId"), nullable=False` |
| `vehicleId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("vehicle.vehicleId"), nullable=True, default=None` |
| `originFacilityId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=True, default=None` |
| `destinationFacilityId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=True, default=None` |
| `routeDate` | `date` | `Date, nullable=False` |
| `routeStatus` | `str` | `String(255), nullable=False` |
| `plannedStartAt` | `datetime | None` | `DateTime, nullable=True` |
| `actualStartAt` | `datetime | None` | `DateTime, nullable=True` |
| `completedAt` | `datetime | None` | `DateTime, nullable=True` |

**Name-equivalent gaps:** missing from model: `planned_end_at`, `actual_end_at`, `created_at`; model-only fields: `routeName`, `originFacilityId`, `destinationFacilityId`, `completedAt`.

**Specified relationships:**
- Each route belongs to one driver and optionally one vehicle.
- One route has many route stops.
- One route can be referenced by many tracking logs.

**Specified indexes / business constraints:**
- Index `(driver_id, route_date)` and `(route_status, route_date)`.
- Planned end must be later than planned start when both are supplied; actual end must not precede actual start.
- Confirm whether a driver can operate more than one route per day and whether a route can be reassigned.

### 3.29 `route_stops`

**Specification attributes (9):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `route_stop_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `route_id` | BIGINT UNSIGNED | NN, FK → `routes.route_id` |
| `stop_number` | INT UNSIGNED | NN; sequence within route |
| `pickup_assignment_id` | BIGINT UNSIGNED | NULL, FK → `pickup_assignments.assignment_id` |
| `facility_id` | BIGINT UNSIGNED | NULL, FK → `facilities.facility_id` |
| `planned_arrival_at` | DATETIME | NULL |
| `actual_arrival_at` | DATETIME | NULL |
| `stop_status` | VARCHAR(20) | NN, DEFAULT `pending`; allowed: pending, arrived, completed, skipped, failed |
| `stop_notes` | TEXT | NULL |

**SQLAlchemy model:** `RouteStop` (`routeStop`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `routeStopId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `routeId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("route.routeId"), nullable=False` |
| `facilityId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=True, default=None` |
| `returnId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=True, default=None` |
| `stopSequence` | `int` | `Integer, nullable=False` |
| `stopType` | `str` | `String(255), nullable=False` |
| `plannedArrivalAt` | `datetime | None` | `DateTime, nullable=True` |
| `actualArrivalAt` | `datetime | None` | `DateTime, nullable=True` |
| `stopStatus` | `str` | `String(255), nullable=False` |

**Name-equivalent gaps:** missing from model: `stop_number`, `pickup_assignment_id`, `stop_notes`; model-only fields: `returnId`, `stopSequence`, `stopType`.

**Specified relationships:**
- Each route stop belongs to one route.
- A stop references exactly one target: either a pickup assignment or a facility.
- A route has many stops; a pickup assignment should be scheduled on no more than one active route stop at a time.
- Tracking logs may reference a route stop.

**Specified indexes / business constraints:**
- UQ `(route_id, stop_number)`.
- CHECK exactly one of `pickup_assignment_id` and `facility_id` is non-NULL.
- Index `(route_id, stop_status)` and `pickup_assignment_id`.
- The service layer must verify that the pickup assignment's driver is the same as the route's driver and that all stops are operationally valid.

### 3.30 `collection_manifests`

**Specification attributes (11):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `manifest_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `manifest_code` | VARCHAR(80) | NN, UQ; human-readable reference |
| `driver_id` | BIGINT UNSIGNED | NN, FK → `drivers.driver_id` |
| `vehicle_id` | BIGINT UNSIGNED | NULL, FK → `vehicles.vehicle_id`; proposed |
| `origin_facility_id` | BIGINT UNSIGNED | NN, FK → `facilities.facility_id` |
| `destination_facility_id` | BIGINT UNSIGNED | NN, FK → `facilities.facility_id` |
| `total_weight_kg` | DECIMAL(10,2) | NULL; CHECK `total_weight_kg >= 0` |
| `manifest_status` | VARCHAR(20) | NN, DEFAULT `created`; allowed: created, in_transit, arrived, partially_received, received, cancelled |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `dispatched_at` | DATETIME | NULL |
| `arrived_at` | DATETIME | NULL |

**SQLAlchemy model:** `CollectionManifest` (`collectionManifest`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `manifestId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `manifestCode` | `str` | `String(255), nullable=False, unique=True` |
| `driverId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("driver.driverId"), nullable=False` |
| `originFacilityId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False` |
| `destinationFacilityId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False` |
| `totalWeightKg` | `Decimal` | `Numeric(12, 2), nullable=False` |
| `status` | `str` | `String(255), nullable=False` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `vehicleId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("vehicle.vehicleId"), nullable=True, default=None` |
| `routeId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("route.routeId"), nullable=True, default=None` |
| `dispatchedAt` | `datetime | None` | `DateTime, nullable=True` |
| `receivedAt` | `datetime | None` | `DateTime, nullable=True, default=datetime.utcnow` |

**Name-equivalent gaps:** missing from model: `manifest_status`, `arrived_at`; model-only fields: `status`, `routeId`, `receivedAt`.

**Specified relationships:**
- Each manifest has one driver, one origin facility, and one destination facility; vehicle is optional.
- One manifest can group many pickup assignments through `pickup_assignments.collection_manifest_id`.
- One manifest can have one facility intake (`facility_intakes.manifest_id` is UNIQUE in this design).
- One manifest can have many tracking logs, custody transfers indirectly through items, and disposal records where applicable.

**Specified indexes / business constraints:**
- Unique `manifest_code`.
- Index `(driver_id, manifest_status)` and `(destination_facility_id, created_at)`.
- The manifest's driver/vehicle must match the driver/vehicle recorded on its included assignments where required.
- `total_weight_kg` is a declared or calculated shipment total; define whether it is measured or estimated.

### 3.31 `custody_transfers`

**Specification attributes (15):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `custody_transfer_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `return_item_id` | BIGINT UNSIGNED | NN, FK → `return_items.return_item_id` |
| `manifest_id` | BIGINT UNSIGNED | NULL, FK → `collection_manifests.manifest_id`; shipment context |
| `from_user_id` | BIGINT UNSIGNED | NULL, FK → `users.user_id` |
| `from_driver_id` | BIGINT UNSIGNED | NULL, FK → `drivers.driver_id` |
| `from_staff_id` | BIGINT UNSIGNED | NULL, FK → `facility_staff.staff_id` |
| `from_facility_id` | BIGINT UNSIGNED | NULL, FK → `facilities.facility_id` |
| `to_user_id` | BIGINT UNSIGNED | NULL, FK → `users.user_id` |
| `to_driver_id` | BIGINT UNSIGNED | NULL, FK → `drivers.driver_id` |
| `to_staff_id` | BIGINT UNSIGNED | NULL, FK → `facility_staff.staff_id` |
| `to_facility_id` | BIGINT UNSIGNED | NULL, FK → `facilities.facility_id` |
| `transfer_status` | VARCHAR(20) | NN, DEFAULT `recorded`; allowed: recorded, acknowledged, disputed, cancelled |
| `handover_reference` | VARCHAR(100) | NULL, UQ; optional scan/QR reference |
| `transferred_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `notes` | TEXT | NULL |

**SQLAlchemy model:** `CustodyTransfer` (`custodyTransfer`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `custodyTransferId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `manifestId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("collectionManifest.manifestId"), nullable=True, default=None` |
| `returnId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=True, default=None` |
| `fromPartyType` | `str` | `String(255), nullable=False` |
| `fromPartyId` | `UUID` | `Uuid(as_uuid=True), nullable=False` |
| `toPartyType` | `str` | `String(255), nullable=False` |
| `toPartyId` | `UUID` | `Uuid(as_uuid=True), nullable=False` |
| `transferredBy` | `UUID | None` | `Uuid(as_uuid=True), nullable=True, default=None` |
| `receivedBy` | `UUID | None` | `Uuid(as_uuid=True), nullable=True, default=None` |
| `transferStatus` | `str` | `String(255), nullable=False` |
| `transferredAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `remarks` | `str | None` | `Text, nullable=True` |

**Name-equivalent gaps:** missing from model: `return_item_id`, `from_user_id`, `from_driver_id`, `from_staff_id`, `from_facility_id`, `to_user_id`, `to_driver_id`, `to_staff_id`, `to_facility_id`, `handover_reference`, `notes`; model-only fields: `returnId`, `fromPartyType`, `fromPartyId`, `toPartyType`, `toPartyId`, `transferredBy`, `receivedBy`, `remarks`.

**Specified relationships:**
- Each custody transfer belongs to one return item.
- A transfer may be associated with a manifest.
- The from/to actor fields reference a user, driver, facility staff member, or facility.
- One return item can have many custody transfers over its lifecycle.

**Specified indexes / business constraints:**
- Add CHECK constraints so exactly one `from_*` actor column and exactly one `to_*` actor column are populated in each transfer row.
- Index `(return_item_id, transferred_at)` and `manifest_id`.
- Validate that the handover sequence follows the prior custody record and that the receiving actor acknowledges the transfer where required.
- Do not edit an acknowledged transfer to rewrite history; create a corrective transfer/event instead.

### 3.32 `tracking_logs`

**Specification attributes (11):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `tracking_log_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `manifest_id` | BIGINT UNSIGNED | NN, FK → `collection_manifests.manifest_id` |
| `driver_id` | BIGINT UNSIGNED | NULL, FK → `drivers.driver_id` |
| `route_id` | BIGINT UNSIGNED | NULL, FK → `routes.route_id` |
| `route_stop_id` | BIGINT UNSIGNED | NULL, FK → `route_stops.route_stop_id` |
| `event_type` | VARCHAR(40) | NN; e.g. picked_up, departed, arrived, delay, exception |
| `event_status` | VARCHAR(30) | NULL; controlled event result/status |
| `latitude` | DECIMAL(10,7) | NULL |
| `longitude` | DECIMAL(10,7) | NULL |
| `description` | VARCHAR(500) | NULL |
| `recorded_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |

**SQLAlchemy model:** `TrackingLog` (`trackingLog`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `trackingLogId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `driverId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("driver.driverId"), nullable=False` |
| `routeId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("route.routeId"), nullable=True, default=None` |
| `assignmentId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("pickupAssignment.assignmentId"), nullable=True, default=None` |
| `latitude` | `Decimal` | `Numeric(12, 2), nullable=False` |
| `longitude` | `Decimal` | `Numeric(12, 2), nullable=False` |
| `recordedAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `trackingStatus` | `str | None` | `String(255), nullable=True` |

**Name-equivalent gaps:** missing from model: `manifest_id`, `route_stop_id`, `event_type`, `event_status`, `description`; model-only fields: `assignmentId`, `trackingStatus`.

**Specified relationships:**
- Each log belongs to one manifest.
- A log may reference the driver, route, and route stop associated with the event.
- One manifest can have many tracking logs.

**Specified indexes / business constraints:**
- Index `(manifest_id, recorded_at)` and `(driver_id, recorded_at)`.
- Validate coordinate ranges when supplied.
- Treat tracking rows as append-only. Limit location-data retention and access according to the product's privacy policy.
- If live driver location is required at high frequency, consider a dedicated location history design/retention strategy rather than storing every GPS sample indefinitely.

### 3.33 `facility_intakes`

**Specification attributes (7):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `intake_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `manifest_id` | BIGINT UNSIGNED | NN, UQ, FK → `collection_manifests.manifest_id`; one intake header per manifest in this design |
| `facility_id` | BIGINT UNSIGNED | NN, FK → `facilities.facility_id` |
| `received_by_staff_id` | BIGINT UNSIGNED | NN, FK → `facility_staff.staff_id` |
| `intake_status` | VARCHAR(20) | NN, DEFAULT `received`; allowed: received, partially_received, rejected, under_inspection, completed |
| `received_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `notes` | TEXT | NULL |

**SQLAlchemy model:** `FacilityIntake` (`facilityIntake`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `intakeId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `facilityId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False` |
| `manifestId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("collectionManifest.manifestId"), nullable=True, default=None` |
| `returnId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=True, default=None` |
| `receivedBy` | `UUID | None` | `Uuid(as_uuid=True), nullable=True, default=None` |
| `intakeStatus` | `str` | `String(255), nullable=False` |
| `receivedAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `declaredQuantity` | `Decimal | None` | `Numeric(12, 2), nullable=True` |
| `receivedQuantity` | `Decimal | None` | `Numeric(12, 2), nullable=True` |
| `intakeNotes` | `str | None` | `Text, nullable=True` |

**Name-equivalent gaps:** missing from model: `received_by_staff_id`, `notes`; model-only fields: `returnId`, `receivedBy`, `declaredQuantity`, `receivedQuantity`, `intakeNotes`.

**Specified relationships:**
- Each intake belongs to one manifest, one receiving facility, and one staff member.
- One intake has many `bin_items` and `inspection_records`.
- Intake items are identified through `bin_items` and/or `inspection_records` linked to the relevant `return_item`.

**Specified indexes / business constraints:**
- Unique `manifest_id` in this one-intake-per-manifest design.
- Validate that `facility_id` matches the manifest's `destination_facility_id` and that the staff member belongs to that facility.
- If the business requires multiple receipts or partial receipts on different dates for one manifest, remove the unique constraint and introduce a receipt sequence/status model.

### 3.34 `disposal_batches`

**Specification attributes (10):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `disposal_batch_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `batch_code` | VARCHAR(80) | NN, UQ; operational disposal batch reference |
| `facility_id` | BIGINT UNSIGNED | NN, FK → `facilities.facility_id` |
| `created_by_staff_id` | BIGINT UNSIGNED | NN, FK → `facility_staff.staff_id` |
| `batch_status` | VARCHAR(20) | NN, DEFAULT `planned`; allowed: planned, ready, processing, completed, cancelled |
| `scheduled_at` | DATETIME | NULL |
| `started_at` | DATETIME | NULL |
| `completed_at` | DATETIME | NULL |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `notes` | TEXT | NULL |

**SQLAlchemy model:** `DisposalBatch` (`disposalBatch`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `disposalBatchId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `facilityId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False` |
| `batchCode` | `str` | `String(255), nullable=False, unique=True` |
| `batchStatus` | `str` | `String(255), nullable=False` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `processingStartedAt` | `datetime | None` | `DateTime, nullable=True` |
| `processingCompletedAt` | `datetime | None` | `DateTime, nullable=True` |
| `totalQuantity` | `Decimal | None` | `Numeric(12, 2), nullable=True` |
| `createdBy` | `UUID | None` | `Uuid(as_uuid=True), nullable=True, default=None` |

**Name-equivalent gaps:** missing from model: `created_by_staff_id`, `scheduled_at`, `started_at`, `completed_at`, `notes`; model-only fields: `processingStartedAt`, `processingCompletedAt`, `totalQuantity`, `createdBy`.

**Specified relationships:**
- Each disposal batch belongs to one disposal facility and one staff creator.
- One disposal batch contains many `disposal_records`.

**Specified indexes / business constraints:**
- Unique `batch_code`.
- Index `(facility_id, batch_status)`.
- Only authorized disposal facilities can create/complete disposal batches.
- Do not mark the batch completed until its required disposal records and evidence have been recorded.

### 3.35 `disposal_records`

**Specification attributes (14):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `disposal_record_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `disposal_batch_id` | BIGINT UNSIGNED | NN, FK → `disposal_batches.disposal_batch_id` |
| `facility_id` | BIGINT UNSIGNED | NN, FK → `facilities.facility_id` |
| `facility_intake_id` | BIGINT UNSIGNED | NN, FK → `facility_intakes.intake_id` |
| `manifest_id` | BIGINT UNSIGNED | NN, FK → `collection_manifests.manifest_id` |
| `return_item_id` | BIGINT UNSIGNED | NN, FK → `return_items.return_item_id`; proposed item-level traceability |
| `medicine_category` | VARCHAR(100) | NN |
| `quantity` | DECIMAL(12,3) | NN; CHECK `quantity > 0`; unit must be defined by the operation |
| `quantity_unit` | VARCHAR(20) | NN; e.g. units, kg, g |
| `disposal_method` | VARCHAR(100) | NN |
| `processed_by_staff_id` | BIGINT UNSIGNED | NN, FK → `facility_staff.staff_id` |
| `processed_at` | DATETIME | NN |
| `certificate_reference` | VARCHAR(150) | NULL, UQ; external processor/audit reference |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |

**SQLAlchemy model:** `DisposalRecord` (`disposalRecord`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `disposalRecordId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `facilityId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False` |
| `manifestId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("collectionManifest.manifestId"), nullable=True, default=None` |
| `medicineCategory` | `str` | `String(255), nullable=False` |
| `quantity` | `Decimal` | `Numeric(12, 2), nullable=False` |
| `disposalMethod` | `str` | `String(255), nullable=False` |
| `processedAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `certificateReference` | `str | None` | `String(255), nullable=True` |
| `disposalBatchId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("disposalBatch.disposalBatchId"), nullable=True, default=None` |
| `intakeId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("facilityIntake.intakeId"), nullable=True, default=None` |
| `processedBy` | `UUID | None` | `Uuid(as_uuid=True), nullable=True, default=None` |
| `disposalStatus` | `str` | `String(255), nullable=False` |
| `remarks` | `str | None` | `Text, nullable=True` |

**Name-equivalent gaps:** missing from model: `facility_intake_id`, `return_item_id`, `quantity_unit`, `processed_by_staff_id`, `created_at`; model-only fields: `intakeId`, `processedBy`, `disposalStatus`, `remarks`.

**Specified relationships:**
- Each disposal record belongs to one disposal batch, facility, intake, manifest, return item, and processing staff member.
- One disposal batch can have many disposal records.
- A return item may have multiple disposal records if accepted quantities are processed in separate batches.
- The user-facing disposal certificate is linked to the return request, whose items link to these disposal records.

**Specified indexes / business constraints:**
- Index `(return_item_id, processed_at)`, `disposal_batch_id`, and `manifest_id`.
- Validate that batch facility, intake facility, record facility, and intake destination are consistent.
- CHECK quantity greater than zero; do not mix units without explicit conversion rules.
- Preserve processor/certificate references and completed records; corrections should be audit-trailed.

### 3.36 `staff_commissions`

**Specification attributes (11):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `commission_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `staff_id` | BIGINT UNSIGNED | NN, FK → `facility_staff.staff_id` |
| `return_id` | BIGINT UNSIGNED | NULL, FK → `return_requests.return_id` |
| `pickup_assignment_id` | BIGINT UNSIGNED | NULL, FK → `pickup_assignments.assignment_id` |
| `commission_amount` | DECIMAL(12,2) | NN; CHECK `commission_amount >= 0` |
| `currency_code` | CHAR(3) | NN, DEFAULT `INR`; proposed ISO currency code |
| `commission_status` | VARCHAR(20) | NN, DEFAULT `pending`; allowed: pending, approved, paid, void |
| `payout_id` | BIGINT UNSIGNED | NULL, FK → `commission_payouts.payout_id`; added when included in a payout |
| `earned_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `approved_at` | DATETIME | NULL |
| `notes` | TEXT | NULL |

**SQLAlchemy model:** `StaffCommission` (`staffCommission`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `commissionId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `facilityStaffId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("facilityStaff.facilityStaffId"), nullable=False` |
| `returnId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=True, default=None` |
| `commissionAmount` | `Decimal` | `Numeric(12, 2), nullable=False` |
| `commissionStatus` | `str` | `String(255), nullable=False` |
| `calculatedAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `approvedAt` | `datetime | None` | `DateTime, nullable=True` |

**Name-equivalent gaps:** missing from model: `staff_id`, `pickup_assignment_id`, `currency_code`, `payout_id`, `earned_at`, `notes`; model-only fields: `facilityStaffId`, `calculatedAt`.

**Specified relationships:**
- Each commission belongs to one facility staff member.
- A commission may reference the qualifying return and/or pickup assignment.
- One commission payout can include many commission rows through `payout_id`.

**Specified indexes / business constraints:**
- Add CHECK `((return_id IS NOT NULL) + (pickup_assignment_id IS NOT NULL)) = 1` so exactly one qualifying source is selected. If the business rule requires both, change this constraint accordingly.
- Index `(staff_id, commission_status)` and `payout_id`.
- Define the commission calculation, qualifying statuses, approval authority, currency, and reversal process before implementation.
- Paid commission rows must not be edited; use an adjustment/reversal record or an audited correction process.

### 3.37 `commission_payouts`

**Specification attributes (10):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `payout_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `staff_id` | BIGINT UNSIGNED | NN, FK → `facility_staff.staff_id` |
| `payout_reference` | VARCHAR(100) | NN, UQ; bank/payment reference or internal reference |
| `total_amount` | DECIMAL(12,2) | NN; CHECK `total_amount > 0` |
| `currency_code` | CHAR(3) | NN, DEFAULT `INR`; proposed ISO currency code |
| `payout_status` | VARCHAR(20) | NN, DEFAULT `pending`; allowed: pending, processing, paid, failed, cancelled |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `paid_at` | DATETIME | NULL |
| `payment_method` | VARCHAR(40) | NULL |
| `payment_notes` | TEXT | NULL |

**SQLAlchemy model:** `CommissionPayout` (`commissionPayout`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `payoutId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `facilityStaffId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("facilityStaff.facilityStaffId"), nullable=False` |
| `payoutReference` | `str` | `String(255), nullable=False, unique=True` |
| `totalAmount` | `Decimal` | `Numeric(12, 2), nullable=False` |
| `payoutStatus` | `str` | `String(255), nullable=False` |
| `payoutMethod` | `str | None` | `String(255), nullable=True` |
| `initiatedAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `completedAt` | `datetime | None` | `DateTime, nullable=True` |

**Name-equivalent gaps:** missing from model: `staff_id`, `currency_code`, `created_at`, `paid_at`, `payment_method`, `payment_notes`; model-only fields: `facilityStaffId`, `payoutMethod`, `initiatedAt`, `completedAt`.

**Specified relationships:**
- Each payout belongs to one staff member.
- One payout can settle many commission rows through `staff_commissions.payout_id`.

**Specified indexes / business constraints:**
- Unique payout reference; index `(staff_id, payout_status, created_at)`.
- Sum of commission rows assigned to the payout must equal `total_amount`, subject to the approved payout policy.
- Mark linked commission rows as paid in the same transaction when payout success is confirmed.
- Store payment references securely and do not store bank credentials.

### 3.38 `notifications`

**Specification attributes (11):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `notification_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `user_id` | BIGINT UNSIGNED | NN, FK → `users.user_id` |
| `notification_type` | VARCHAR(50) | NN; e.g. return_update, pickup_update, verification, wallet, reward, certificate |
| `channel` | VARCHAR(20) | NN, DEFAULT `in_app`; allowed: in_app, email, sms, push |
| `title` | VARCHAR(150) | NN |
| `message` | TEXT | NN |
| `reference_type` | VARCHAR(50) | NULL; e.g. return_request, redemption, certificate |
| `reference_id` | BIGINT UNSIGNED | NULL; ID of the related record; polymorphic reference, not a database FK |
| `notification_status` | VARCHAR(20) | NN, DEFAULT `unread`; allowed: unread, read, archived, failed |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |
| `read_at` | DATETIME | NULL |

**SQLAlchemy model:** `Notification` (`notification`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `notificationId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `userId` | `UUID` | `Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False` |
| `notificationType` | `str` | `String(255), nullable=False` |
| `title` | `str` | `String(255), nullable=False` |
| `message` | `str` | `Text, nullable=False` |
| `relatedReturnId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=True, default=None` |
| `isRead` | `bool` | `Boolean, nullable=False` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |
| `readAt` | `datetime | None` | `DateTime, nullable=True` |

**Name-equivalent gaps:** missing from model: `channel`, `reference_type`, `reference_id`, `notification_status`; model-only fields: `relatedReturnId`, `isRead`.

**Specified relationships:**
- Each notification belongs to one user.
- A user can have many notifications.
- `reference_type` and `reference_id` can point to different business entities; this is intentionally polymorphic and cannot be protected by one ordinary foreign key.

**Specified indexes / business constraints:**
- Index `(user_id, notification_status, created_at)`.
- Validate the reference type and referenced record in application code.
- Delivery status for external email/SMS/push providers may require additional fields or a separate delivery log if retry-level tracking becomes necessary.

### 3.39 `audit_logs`

**Specification attributes (10):**

| Column | MySQL type | Required constraints / notes |
|---|---|---|
| `audit_log_id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `actor_user_id` | BIGINT UNSIGNED | NULL, FK → `users.user_id`; NULL for system jobs |
| `action` | VARCHAR(80) | NN; e.g. create, update, approve, reject, assign, dispose |
| `entity_type` | VARCHAR(80) | NN; table/resource name |
| `entity_id` | BIGINT UNSIGNED | NN; ID of affected row; polymorphic reference, not a database FK |
| `before_data` | JSON | NULL; redact sensitive fields |
| `after_data` | JSON | NULL; redact sensitive fields |
| `ip_address` | VARCHAR(45) | NULL; supports IPv4 and IPv6 |
| `user_agent` | VARCHAR(500) | NULL |
| `created_at` | DATETIME | NN, DEFAULT CURRENT_TIMESTAMP |

**SQLAlchemy model:** `AuditLog` (`auditLog`)

| Model attribute | Python type | SQLAlchemy mapping |
|---|---|---|
| `auditLogId` | `UUID` | `Uuid(as_uuid=True), primary_key=True, default=uuid4` |
| `actorUserId` | `UUID | None` | `Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=True, default=None` |
| `action` | `str` | `String(255), nullable=False` |
| `entityName` | `str` | `String(255), nullable=False` |
| `entityId` | `str | None` | `String(255), nullable=True` |
| `oldValue` | `dict | None` | `JSON, nullable=True` |
| `newValue` | `dict | None` | `JSON, nullable=True` |
| `ipAddress` | `str | None` | `String(255), nullable=True` |
| `createdAt` | `datetime` | `DateTime, nullable=False, default=datetime.utcnow` |

**Name-equivalent gaps:** missing from model: `entity_type`, `before_data`, `after_data`, `user_agent`; model-only fields: `entityName`, `oldValue`, `newValue`.

**Specified relationships:**
- An audit log may belong to one user actor; system-generated entries can have no user actor.
- Audit entries refer to business records through `entity_type` and `entity_id`, which form an intentional polymorphic reference.

**Specified indexes / business constraints:**
- Index `(entity_type, entity_id, created_at)` and `(actor_user_id, created_at)`.
- Treat audit logs as append-only; application roles must not update or delete them in normal operation.
- Never record password hashes, access tokens, full payment credentials, or unnecessary sensitive document contents in JSON snapshots.
- Define retention, access, and export policies.



> **Mapping correction (2026-11-27):** The initial report's summary used a naive pluralization rule and incorrectly treated the already-existing `returnStatusHistory` and `facilityStaff` model tables as extra. Rechecking the ORM's declared `__tablename__` values against the specification confirms that all 39 specified entities have corresponding model classes. The only additional implementation table is `returnBucketItem`. This correction changes the entity-mapping count only; it does not change the field-level differences or establish that the live TiDB schema matches either representation.

## Reconciliation decisions still required

The following are not safe to resolve by automatic renaming alone:

- UUID-to-BIGINT identifier conversion and preservation of existing foreign-key relationships.
- Model-only fields and PR #8 additions, including purchase metadata and `ReturnBucketItem`.
- Generic party references versus typed foreign keys in custody transfers.
- Prescription document ownership and one-to-one document linkage.
- Verification actor references and history semantics.
- Whether application-only fields are intentional extensions or implementation drift.
- Existing live TiDB schema, indexes, constraints, and data compatibility.

## Safety and deployment status

This report does not execute DDL, update ORM models, change migrations, seed data, or mutate TiDB. Any schema conversion must be tested against a separate database and validated against a fresh live-schema inspection before deployment. Existing data must be preserved.

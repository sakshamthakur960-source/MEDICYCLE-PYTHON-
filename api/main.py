from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import (
    User, UserAddress, Medicine, MedicineBatch, UserMedicine, ReturnRequest,
    ReturnItem, ReturnBucketItem, PickupSlot, Wallet, WalletTransaction, Reward,
    RewardRedemption, DisposalCertificate, ReturnStatusHistory, Facility,
    FacilityStaff, Driver,
)
from api.dependencies import get_db, get_current_user
from api.schemas import (
    RegisterIn, LoginIn, UserOut, AddressIn, MedicineOut, UserMedicineIn,
    ReturnCreateIn, ReturnDecisionIn, RewardRedemptionIn, MedicinePurchaseIn, ReturnBucketSubmitIn,
)
from api.security import hash_password, verify_password, create_access_token

app = FastAPI(
    title="MediCycle API",
    version="1.0.0",
    description="API for medicine returns, reverse logistics, rewards and responsible disposal.",
)

origins = [x.strip() for x in __import__("os").getenv("CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "medicycle-api"}


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    try:
        user = User(
            fullName=payload.fullName.strip(),
            email=str(payload.email).lower() if payload.email else None,
            phone=payload.phone,
            passwordHash=hash_password(payload.password),
            accountStatus="active",
            emailVerified=False,
            phoneVerified=False,
        )

        db.add(user)
        db.flush()

        # One-time customer welcome bonus: 100 MediCredits.
        # The wallet and its CREDIT ledger entry are committed atomically.
        welcome_bonus = Decimal("100.00")
        wallet = Wallet(
            userId=user.userId,
            availableBalance=welcome_bonus,
            walletStatus="active",
            updatedAt=datetime.utcnow(),
        )

        db.add(wallet)
        db.flush()

        db.add(WalletTransaction(
            walletId=wallet.walletId,
            transactionType="CREDIT",
            amount=welcome_bonus,
            referenceCode=f"WELCOME-{uuid4().hex[:12].upper()}",
            description="One-time 100 MediCredits customer welcome bonus",
        ))
        db.commit()
        db.refresh(user)

        return {
            "user": UserOut.model_validate(user),
            "accessToken": create_access_token(user.userId),
            "tokenType": "bearer",
        }

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An account already exists with this email or phone",
        )


@app.post("/api/auth/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    identifier = payload.identifier.strip()
    user = db.scalar(select(User).where(or_(User.email == identifier.lower(), User.phone == identifier)))
    if user is None or not verify_password(payload.password, user.passwordHash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.accountStatus.lower() != "active":
        raise HTTPException(status_code=403, detail="Account is not active")
    user.lastLoginAt = datetime.utcnow()
    db.commit()
    return {"user": UserOut.model_validate(user), "accessToken": create_access_token(user.userId), "tokenType": "bearer"}


@app.get("/api/users/me", response_model=UserOut)
def get_profile(user: User = Depends(get_current_user)):
    return user


@app.get("/api/wallet/welcome-bonus-status")
def welcome_bonus_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wallet = db.scalar(select(Wallet).where(Wallet.userId == user.userId))
    if wallet is None:
        return {"claimed": False}

    existing_bonus = db.scalar(
        select(WalletTransaction.transactionId)
        .where(
            WalletTransaction.walletId == wallet.walletId,
            or_(
                WalletTransaction.referenceCode.like("WELCOME-%"),
                WalletTransaction.description.ilike("%welcome bonus%"),
            ),
        )
        .limit(1)
    )
    return {"claimed": existing_bonus is not None}


@app.post("/api/wallet/claim-welcome-bonus")
def claim_welcome_bonus(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Serialize claims for this account, including when its wallet does not yet exist.
    db.scalar(
        select(User)
        .where(User.userId == user.userId)
        .with_for_update()
    )

    # Exclude facility staff and drivers.
    is_staff = db.scalar(
        select(FacilityStaff.facilityStaffId)
        .where(FacilityStaff.userId == user.userId)
        .limit(1)
    )

    is_driver = db.scalar(
        select(Driver.driverId)
        .where(Driver.userId == user.userId)
        .limit(1)
    )

    if is_staff or is_driver:
        raise HTTPException(
            status_code=403,
            detail="Welcome bonus is available only to customer accounts",
        )

    try:
        # Lock the wallet to prevent simultaneous duplicate claims.
        wallet = db.scalar(
            select(Wallet)
            .where(Wallet.userId == user.userId)
            .with_for_update()
        )

        if wallet is None:
            wallet = Wallet(
                userId=user.userId,
                availableBalance=Decimal("0.00"),
                walletStatus="active",
                updatedAt=datetime.utcnow(),
            )
            db.add(wallet)
            db.flush()

        # Registration already records welcome transactions with WELCOME-.
        existing_bonus = db.scalar(
            select(WalletTransaction.transactionId)
            .where(
                WalletTransaction.walletId == wallet.walletId,
                or_(
                    WalletTransaction.referenceCode.like("WELCOME-%"),
                    WalletTransaction.description.ilike("%welcome bonus%"),
                ),
            )
            .limit(1)
        )

        if existing_bonus:
            raise HTTPException(
                status_code=409,
                detail="Welcome bonus has already been credited",
            )

        bonus = Decimal("100.00")
        wallet.availableBalance += bonus
        wallet.updatedAt = datetime.utcnow()

        db.add(
            WalletTransaction(
                walletId=wallet.walletId,
                transactionType="CREDIT",
                amount=bonus,
                referenceCode=f"WELCOME-{uuid4().hex[:12].upper()}",
                description="One-time 100 MediCredits customer welcome bonus",
            )
        )

        db.commit()

        return {
            "message": "Welcome bonus credited successfully",
            "creditedAmount": str(bonus),
            "availableBalance": str(wallet.availableBalance),
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise



@app.patch("/api/users/me", response_model=UserOut)
def update_profile(payload: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    allowed = {"fullName", "email", "phone"}
    unknown = set(payload) - allowed
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unsupported profile fields: {', '.join(sorted(unknown))}")
    for key, value in payload.items():
        if key == "fullName" and (not isinstance(value, str) or not value.strip()):
            raise HTTPException(status_code=422, detail="fullName cannot be empty")
        if key == "email" and value:
            value = value.strip().lower()
        setattr(user, key, value)
    user.updatedAt = datetime.utcnow()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email or phone is already in use")
    db.refresh(user)
    return user


@app.get("/api/users/me/addresses")
def list_addresses(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(UserAddress).where(UserAddress.userId == user.userId).order_by(UserAddress.isDefault.desc(), UserAddress.createdAt.desc())).all()
    return rows


@app.post("/api/users/me/addresses", status_code=201)
def create_address(payload: AddressIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.latitude is not None and not Decimal("-90") <= payload.latitude <= Decimal("90"):
        raise HTTPException(status_code=422, detail="Latitude must be between -90 and 90")
    if payload.longitude is not None and not Decimal("-180") <= payload.longitude <= Decimal("180"):
        raise HTTPException(status_code=422, detail="Longitude must be between -180 and 180")
    if payload.isDefault:
        db.query(UserAddress).filter(UserAddress.userId == user.userId).update({UserAddress.isDefault: False})
    address = UserAddress(userId=user.userId, **payload.model_dump())
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


@app.patch("/api/users/me/addresses/{address_id}")
def update_address(address_id: UUID, payload: AddressIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Update one of the authenticated customer's saved addresses."""
    address = db.get(UserAddress, address_id)
    if address is None or address.userId != user.userId:
        raise HTTPException(status_code=404, detail="Address not found for this user")
    if payload.latitude is not None and not Decimal("-90") <= payload.latitude <= Decimal("90"):
        raise HTTPException(status_code=422, detail="Latitude must be between -90 and 90")
    if payload.longitude is not None and not Decimal("-180") <= payload.longitude <= Decimal("180"):
        raise HTTPException(status_code=422, detail="Longitude must be between -180 and 180")
    if payload.isDefault:
        db.query(UserAddress).filter(
            UserAddress.userId == user.userId,
            UserAddress.addressId != address.addressId,
        ).update({UserAddress.isDefault: False})
    for key, value in payload.model_dump().items():
        setattr(address, key, value)
    db.commit()
    db.refresh(address)
    return address


@app.get("/api/medicines/catalogue", response_model=list[MedicineOut])
def medicine_catalogue(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Return the active catalogue options for customer return forms."""
    return db.scalars(select(Medicine).order_by(Medicine.name, Medicine.strength).limit(limit)).all()


@app.get("/api/medicines/search", response_model=list[MedicineOut])
def search_medicines(q: str = Query(min_length=1, max_length=120), limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    term = f"%{q.strip()}%"
    return db.scalars(select(Medicine).where(or_(Medicine.name.ilike(term), Medicine.genericName.ilike(term), Medicine.manufacturer.ilike(term), Medicine.barcode == q.strip())).order_by(Medicine.name).limit(limit)).all()


@app.get("/api/user-medicines")
def list_user_medicines(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(UserMedicine).where(UserMedicine.userId == user.userId).order_by(UserMedicine.addedAt.desc())).all()


@app.post("/api/user-medicines", status_code=201)
def add_user_medicine(payload: UserMedicineIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.get(Medicine, payload.medicineId) is None:
        raise HTTPException(status_code=404, detail="Medicine not found")
    if payload.batchId is not None:
        batch = db.get(MedicineBatch, payload.batchId)
        if batch is None or batch.medicineId != payload.medicineId:
            raise HTTPException(status_code=422, detail="Batch does not belong to the selected medicine")
    item = UserMedicine(userId=user.userId, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _sync_expired_bucket(db: Session, user: User):
    """Stage missing expired bucket rows; caller owns the transaction."""
    today = date.today()
    expired_ids = db.scalars(select(UserMedicine.userMedicineId).join(
        MedicineBatch, UserMedicine.batchId == MedicineBatch.batchId
    ).where(UserMedicine.userId == user.userId, MedicineBatch.expiresOn < today)).all()
    existing = set(db.scalars(select(ReturnBucketItem.userMedicineId).where(ReturnBucketItem.userId == user.userId)).all())
    for inventory_id in expired_ids:
        if inventory_id in existing:
            continue
        # Concurrent page loads can discover the same expired item. The unique
        # constraint is the final guard; isolate a duplicate insert in a savepoint.
        try:
            with db.begin_nested():
                db.add(ReturnBucketItem(userId=user.userId, userMedicineId=inventory_id, status="IN_BUCKET"))
                db.flush()
        except IntegrityError:
            continue

@app.post("/api/return-bucket/sync")
def sync_return_bucket(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Explicitly stage newly expired tracked medicines; safe to call repeatedly."""
    before = set(db.scalars(
        select(ReturnBucketItem.userMedicineId).where(ReturnBucketItem.userId == user.userId)
    ).all())
    _sync_expired_bucket(db, user)
    after = set(db.scalars(
        select(ReturnBucketItem.userMedicineId).where(ReturnBucketItem.userId == user.userId)
    ).all())
    db.commit()
    return {"created": len(after - before), "message": "Expired medicines synchronized"}


@app.get("/api/my-medicines")
def my_medicines(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(
        select(UserMedicine, Medicine, MedicineBatch)
        .join(Medicine, UserMedicine.medicineId == Medicine.medicineId)
        .outerjoin(MedicineBatch, UserMedicine.batchId == MedicineBatch.batchId)
        .where(UserMedicine.userId == user.userId).order_by(UserMedicine.addedAt.desc())
    ).all()
    today = date.today()
    result = []
    for inventory, medicine, batch in rows:
        expiry = batch.expiresOn if batch else None
        days = (expiry - today).days if expiry else None
        state = "EXPIRED" if days is not None and days < 0 else "NEAR_EXPIRY" if days is not None and days <= 30 else "ACTIVE"
        result.append({
            "userMedicineId": str(inventory.userMedicineId), "medicineId": str(medicine.medicineId),
            "name": medicine.name, "strength": medicine.strength, "dosageForm": medicine.dosageForm,
            "quantity": inventory.quantity, "packagingState": inventory.packagingState,
            "batchId": str(batch.batchId) if batch else None, "batchNumber": batch.batchNumber if batch else None,
            "expiresOn": expiry.isoformat() if expiry else None, "daysToExpiry": days, "expiryStatus": state,
            "sourcePlatform": inventory.sourcePlatform, "externalOrderId": inventory.externalOrderId,
            "purchaseDate": inventory.purchaseDate.isoformat() if inventory.purchaseDate else None, "isDemo": inventory.isDemo
        })
    return result


@app.post("/api/my-medicines", status_code=201)
def add_my_medicine(payload: MedicinePurchaseIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    medicine = db.get(Medicine, payload.medicineId)
    if medicine is None:
        raise HTTPException(status_code=404, detail="Medicine not found")
    batch = db.scalar(select(MedicineBatch).where(MedicineBatch.medicineId == medicine.medicineId, MedicineBatch.batchNumber == payload.batchNumber))
    if batch is None:
        batch = MedicineBatch(medicineId=medicine.medicineId, batchNumber=payload.batchNumber,
                              manufacturedOn=payload.manufacturedOn, expiresOn=payload.expiresOn)
        db.add(batch)
        db.flush()
    elif batch.expiresOn != payload.expiresOn:
        raise HTTPException(status_code=409, detail="This batch number already exists with a different expiry date")
    inventory = UserMedicine(userId=user.userId, medicineId=medicine.medicineId, batchId=batch.batchId,
        quantity=payload.quantity, packagingState=payload.packagingState, notes=payload.notes,
        sourcePlatform=payload.sourcePlatform, externalOrderId=payload.externalOrderId,
        purchaseDate=payload.purchaseDate, isDemo=False)
    db.add(inventory)
    db.commit()
    db.refresh(inventory)
    return {"userMedicineId": str(inventory.userMedicineId), "message": "Medicine added to your tracker"}


@app.post("/api/my-medicines/demo")
def load_demo_medicines(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Idempotently add 24 illustrative purchases, split evenly across two pharmacy apps."""
    catalogue = db.scalars(select(Medicine).order_by(Medicine.name).limit(3)).all()
    if len(catalogue) < 3:
        raise HTTPException(status_code=409, detail="At least three catalogue medicines are required for the pharmacy demo.")

    today = date.today()
    purchase_date = today - timedelta(days=60)
    # Every sample has its own expiry date; the one-day offset keeps the two
    # pharmacy inventories distinct while showing expired, near-expiry and active stock.
    expiry_offsets = (-45, -15, -5, 7, 14, 25, 35, 60, 90, 120, 180, 270)
    apps = (("TATA_1MG", "TATA1MG", 0), ("PHARMEASY", "PHARMEASY", 1))
    created = 0

    for source, source_tag, day_offset in apps:
        for index, offset in enumerate(expiry_offsets, start=1):
            medicine = catalogue[(index - 1) % len(catalogue)]
            expiry = today + timedelta(days=offset + day_offset)
            order_id = f"MC-DEMO-{source_tag}-{index:02d}-2026"
            exists = db.scalar(select(UserMedicine.userMedicineId).where(
                UserMedicine.userId == user.userId,
                UserMedicine.externalOrderId == order_id,
                UserMedicine.isDemo.is_(True),
            ))
            if exists:
                continue

            batch_number = f"{user.userId}-MCDEMO-{source_tag}-{index:02d}"
            batch = db.scalar(select(MedicineBatch).where(
                MedicineBatch.medicineId == medicine.medicineId,
                MedicineBatch.batchNumber == batch_number,
            ))
            if batch is None:
                batch = MedicineBatch(
                    medicineId=medicine.medicineId,
                    batchNumber=batch_number,
                    expiresOn=expiry,
                )
                db.add(batch)
                db.flush()
            elif batch.expiresOn != expiry:
                raise HTTPException(status_code=409, detail=f"Demo batch {source_tag}-{index:02d} has an unexpected expiry date.")

            db.add(UserMedicine(
                userId=user.userId,
                medicineId=medicine.medicineId,
                batchId=batch.batchId,
                quantity=2 if offset < 0 else 1,
                packagingState="SEALED",
                sourcePlatform=source,
                externalOrderId=order_id,
                purchaseDate=purchase_date,
                isDemo=True,
                notes="Illustrative demo purchase; not a real pharmacy order",
            ))
            created += 1

    db.commit()
    _sync_expired_bucket(db, user)
    return {
        "created": created,
        "message": "24 illustrative purchases loaded (12 each for Tata 1mg and PharmEasy); expired items synchronized to Return Bucket.",
    }

@app.get("/api/return-bucket")
def list_return_bucket(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(select(ReturnBucketItem, UserMedicine, Medicine, MedicineBatch)
        .join(UserMedicine, ReturnBucketItem.userMedicineId == UserMedicine.userMedicineId)
        .join(Medicine, UserMedicine.medicineId == Medicine.medicineId)
        .outerjoin(MedicineBatch, UserMedicine.batchId == MedicineBatch.batchId)
        .where(ReturnBucketItem.userId == user.userId, ReturnBucketItem.status == "IN_BUCKET")
        .order_by(ReturnBucketItem.createdAt)).all()
    return [{"bucketItemId": str(b.bucketItemId), "userMedicineId": str(u.userMedicineId),
             "medicineId": str(m.medicineId), "batchId": str(batch.batchId) if batch else None,
             "name": m.name, "strength": m.strength, "quantity": u.quantity,
             "expiresOn": batch.expiresOn.isoformat() if batch else None} for b,u,m,batch in rows]


@app.post("/api/return-bucket/submit", status_code=201)
def submit_return_bucket(payload: ReturnBucketSubmitIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _sync_expired_bucket(db, user)
    selected_ids = set(payload.bucketItemIds)
    if len(selected_ids) != len(payload.bucketItemIds):
        raise HTTPException(status_code=422, detail="Duplicate Return Bucket item IDs are not allowed")
    bucket_rows = db.scalars(
        select(ReturnBucketItem)
        .where(
            ReturnBucketItem.userId == user.userId,
            ReturnBucketItem.status == "IN_BUCKET",
            ReturnBucketItem.bucketItemId.in_(selected_ids),
        )
        .with_for_update()
    ).all()
    if len(bucket_rows) != len(selected_ids):
        raise HTTPException(status_code=404, detail="One or more selected medicines are not in your active Return Bucket")
    if payload.addressId is not None:
        address = db.get(UserAddress, payload.addressId)
        if address is None or address.userId != user.userId:
            raise HTTPException(status_code=404, detail="Address not found for this user")
    slot = None
    if payload.returnMethod == "DOORSTEP_PICKUP":
        if payload.addressId is None:
            raise HTTPException(status_code=422, detail="A pickup address is required for doorstep pickup")
        # Lock the slot row so simultaneous submissions cannot overbook it.
        slot = db.scalar(
            select(PickupSlot)
            .where(PickupSlot.pickupSlotId == payload.pickupSlotId)
            .with_for_update()
        )
        if slot is None or slot.slotStatus.lower() != "available" or slot.bookedCount >= slot.capacity or slot.slotDate < date.today():
            raise HTTPException(status_code=409, detail="Pickup slot is unavailable")
        slot_facility = db.get(Facility, slot.facilityId)
        if slot_facility is None or slot_facility.operatingStatus.lower() not in {"operational", "active"} or slot_facility.authorizationStatus.lower() not in {"approved", "authorized"}:
            raise HTTPException(status_code=409, detail="Pickup slot facility is unavailable")
    else:
        facility = db.get(Facility, payload.facilityId)
        if facility is None or facility.operatingStatus.lower() not in {"operational", "active"} or facility.authorizationStatus.lower() not in {"approved", "authorized"}:
            raise HTTPException(status_code=404, detail="Drop-off facility is unavailable")
    inventory_rows = []
    for bucket in bucket_rows:
        inventory = db.get(UserMedicine, bucket.userMedicineId)
        if inventory is None or inventory.userId != user.userId or inventory.batchId is None:
            raise HTTPException(status_code=409, detail="A bucket medicine record is no longer valid")
        batch = db.get(MedicineBatch, inventory.batchId)
        if batch is None or batch.medicineId != inventory.medicineId or batch.expiresOn >= date.today():
            raise HTTPException(status_code=409, detail="Only expired medicines can be submitted from the Return Bucket")
        inventory_rows.append(inventory)
    request = ReturnRequest(userId=user.userId, addressId=payload.addressId, returnMethod=payload.returnMethod, pickupSlotId=payload.pickupSlotId, facilityId=payload.facilityId, requestNotes=payload.requestNotes or "Submitted from My Medicines Return Bucket", status="SUBMITTED")
    db.add(request)
    db.flush()
    for inventory in inventory_rows:
        db.add(ReturnItem(returnId=request.returnId, medicineId=inventory.medicineId, batchId=inventory.batchId, quantity=inventory.quantity, packagingCondition=inventory.packagingState, inspectionStatus="PENDING", creditsAwarded=Decimal("0.00")))
    if slot is not None:
        slot.bookedCount += 1
        if slot.bookedCount >= slot.capacity:
            slot.slotStatus = "FULL"
    db.add(ReturnStatusHistory(returnId=request.returnId, previousStatus=None, newStatus="SUBMITTED", changeReason="Customer submitted expired medicines from Return Bucket"))
    for bucket in bucket_rows:
        bucket.status = "SUBMITTED"
        bucket.submittedReturnId = request.returnId
    db.commit()
    return {"returnId": str(request.returnId), "submittedItems": len(bucket_rows), "status": "SUBMITTED"}

@app.get("/api/facilities")
def list_customer_dropoff_facilities(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Facility).where(func.lower(Facility.operatingStatus).in_(["operational", "active"]), func.lower(Facility.authorizationStatus).in_(["approved", "authorized"])).order_by(Facility.facilityName)).all()

@app.get("/api/pickup-slots")
def list_pickup_slots(facility_id: UUID | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(PickupSlot).where(PickupSlot.slotStatus.in_(["available", "AVAILABLE", "Available"]), PickupSlot.bookedCount < PickupSlot.capacity)
    if facility_id:
        stmt = stmt.where(PickupSlot.facilityId == facility_id)
    return db.scalars(stmt.order_by(PickupSlot.slotDate, PickupSlot.startTime)).all()


@app.post("/api/returns", status_code=201)
def create_return(payload: ReturnCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.addressId is not None:
        address = db.get(UserAddress, payload.addressId)
        if address is None or address.userId != user.userId:
            raise HTTPException(status_code=404, detail="Address not found for this user")
    if payload.returnMethod == "DOORSTEP_PICKUP":
        if payload.addressId is None:
            raise HTTPException(status_code=422, detail="A pickup address is required for doorstep pickup")
        slot = db.get(PickupSlot, payload.pickupSlotId)
        if slot is None or slot.slotStatus.lower() not in {"available"} or slot.bookedCount >= slot.capacity:
            raise HTTPException(status_code=409, detail="Pickup slot is unavailable")
    if payload.returnMethod == "PHARMACY_DROPOFF":
        facility = db.get(Facility, payload.facilityId)
        if facility is None or facility.operatingStatus.lower() not in {"operational", "active"} or facility.authorizationStatus.lower() not in {"approved", "authorized"}:
            raise HTTPException(status_code=404, detail="Drop-off facility is unavailable")
    for item in payload.items:
        if db.get(Medicine, item.medicineId) is None:
            raise HTTPException(status_code=404, detail=f"Medicine not found: {item.medicineId}")
        if item.batchId:
            batch = db.get(MedicineBatch, item.batchId)
            if batch is None or batch.medicineId != item.medicineId:
                raise HTTPException(status_code=422, detail="Medicine batch mismatch")
    request = ReturnRequest(
        userId=user.userId,
        addressId=payload.addressId,
        returnMethod=payload.returnMethod,
        pickupSlotId=payload.pickupSlotId,
        facilityId=payload.facilityId,
        requestNotes=payload.requestNotes,
        status="SUBMITTED",
    )
    db.add(request)
    db.flush()
    for item in payload.items:
        db.add(ReturnItem(
            returnId=request.returnId,
            medicineId=item.medicineId,
            batchId=item.batchId,
            quantity=item.quantity,
            packagingCondition=item.packagingCondition,
            inspectionStatus="PENDING",
            creditsAwarded=Decimal("0.00"),
        ))
    if payload.returnMethod == "DOORSTEP_PICKUP":
        slot.bookedCount += 1
        if slot.bookedCount >= slot.capacity:
            slot.slotStatus = "FULL"
    db.add(ReturnStatusHistory(returnId=request.returnId, previousStatus=None, newStatus="SUBMITTED", changeReason="Customer submitted return request"))
    db.commit()
    db.refresh(request)
    return {"return": request, "items": db.scalars(select(ReturnItem).where(ReturnItem.returnId == request.returnId)).all()}


@app.get("/api/returns")
def list_returns(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(ReturnRequest).where(ReturnRequest.userId == user.userId).order_by(ReturnRequest.createdAt.desc())).all()


@app.get("/api/returns/{return_id}")
def get_return(return_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    request = db.get(ReturnRequest, return_id)
    if request is None or request.userId != user.userId:
        raise HTTPException(status_code=404, detail="Return request not found")
    items = db.scalars(select(ReturnItem).where(ReturnItem.returnId == request.returnId)).all()
    history = db.scalars(select(ReturnStatusHistory).where(ReturnStatusHistory.returnId == request.returnId).order_by(ReturnStatusHistory.changedAt)).all()
    return {"return": request, "items": items, "history": history}


@app.get("/api/wallet")
def wallet_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wallet = db.scalar(select(Wallet).where(Wallet.userId == user.userId))
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@app.get("/api/rewards")
def list_rewards(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    now = datetime.utcnow()
    # Case-insensitive status match: seed data stores 'AVAILABLE' and redeem_reward() already uses .lower().
    # Hide the known seeded demo coupons from the customer catalogue.
    # Their database rows are intentionally left untouched until redemption references
    # can be checked safely in the live TiDB database.
    return db.scalars(
        select(Reward).where(
            func.lower(Reward.status) == "available",
            or_(Reward.validUntil.is_(None), Reward.validUntil >= now),
            func.lower(Reward.partnerName) != "demo partner",
            ~func.lower(Reward.title).like("demo voucher -%"),
        ).order_by(Reward.creditsRequired)
    ).all()


@app.get("/api/wallet/transactions")
def wallet_transactions(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wallet = db.scalar(select(Wallet).where(Wallet.userId == user.userId))
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return db.scalars(select(WalletTransaction).where(WalletTransaction.walletId == wallet.walletId).order_by(WalletTransaction.createdAt.desc()).limit(limit)).all()


@app.get("/api/certificates")
def list_certificates(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(DisposalCertificate).join(ReturnRequest, DisposalCertificate.returnId == ReturnRequest.returnId).where(ReturnRequest.userId == user.userId).order_by(DisposalCertificate.issuedAt.desc())).all()


@app.post("/api/reward-redemptions", status_code=201)
def redeem_reward(payload: RewardRedemptionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wallet = db.scalar(select(Wallet).where(Wallet.userId == user.userId).with_for_update())
    reward = db.scalar(select(Reward).where(Reward.rewardId == payload.rewardId).with_for_update())
    if wallet is None or reward is None:
        raise HTTPException(status_code=404, detail="Wallet or reward not found")
    now = datetime.utcnow()
    if wallet.walletStatus.lower() != "active" or reward.status.lower() != "available" or (reward.validUntil and reward.validUntil < now):
        raise HTTPException(status_code=409, detail="Wallet or reward is not available")
    if wallet.availableBalance < reward.creditsRequired:
        raise HTTPException(status_code=409, detail="Insufficient MediCredits")
    code = f"MC-{uuid4().hex[:12].upper()}"
    redemption = RewardRedemption(userId=user.userId, rewardId=reward.rewardId, creditsUsed=reward.creditsRequired, redemptionCode=code, status="ISSUED")
    db.add(redemption)
    db.flush()
    wallet.availableBalance -= reward.creditsRequired
    wallet.updatedAt = now
    db.add(WalletTransaction(walletId=wallet.walletId, redemptionId=redemption.redemptionId, transactionType="DEBIT", amount=reward.creditsRequired, referenceCode=code, description=f"Reward redemption: {reward.title}"))
    db.commit()
    db.refresh(redemption)
    return {"redemption": redemption, "remainingBalance": wallet.availableBalance}


# Operational APIs are kept in a separate router so the customer-facing API remains focused.
from api.operations import router as operations_router

app.include_router(operations_router)

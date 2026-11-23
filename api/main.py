from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import (
    User, UserAddress, Medicine, MedicineBatch, UserMedicine, ReturnRequest,
    ReturnItem, PickupSlot, Wallet, WalletTransaction, Reward,
    RewardRedemption, DisposalCertificate, ReturnStatusHistory, Facility,
    FacilityStaff, Driver,
)
from api.dependencies import get_db, get_current_user
from api.schemas import (
    RegisterIn, LoginIn, UserOut, AddressIn, MedicineOut, UserMedicineIn,
    ReturnCreateIn, ReturnDecisionIn, RewardRedemptionIn,
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


@app.get("/api/medicines/search", response_model=list[MedicineOut])
def search_medicines(q: str = Query(min_length=1, max_length=120), limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    term = f"%{q.strip()}%"
    return db.scalars(select(Medicine).where(or_(Medicine.name.ilike(term), Medicine.genericName.ilike(term), Medicine.manufacturer.ilike(term), Medicine.barcode == q.strip())).limit(limit)).all()


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
    return db.scalars(select(Reward).where(Reward.status == "available", or_(Reward.validUntil.is_(None), Reward.validUntil >= now))).all()


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

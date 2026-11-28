"""Operational endpoints for MediCycle logistics and facility workflows.

Staff authorization is derived from active FacilityStaff rows; driver authorization
is derived from Driver.userId. No role column is added to User.
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import (
    User, Facility, FacilityStaff, Driver, PickupAssignment, ReturnRequest,
    ReturnItem, ReturnStatusHistory, FacilityIntake, InspectionRecord,
    StorageBin, BinItem, TamperSeal, CollectionManifest, CustodyTransfer,
    TrackingLog, Route, RouteStop, Vehicle, DisposalBatch, DisposalRecord,
    DisposalCertificate, StaffCommission, CommissionPayout, Notification,
    AuditLog, Wallet, WalletTransaction, Reward, PickupSlot
)
from api.dependencies import get_db, get_current_user

router = APIRouter(prefix="/api", tags=["operations"])


def active_staff(db: Session, user: User) -> list[FacilityStaff]:
    return list(db.scalars(select(FacilityStaff).where(
        FacilityStaff.userId == user.userId,
        FacilityStaff.employmentStatus.in_(["ACTIVE", "active", "EMPLOYED", "employed"])
    )).all())


def require_staff(db: Session, user: User) -> list[FacilityStaff]:
    rows = active_staff(db, user)
    if not rows:
        raise HTTPException(403, "Active facility staff access required")
    return rows


def audit(db: Session, user: User, action: str, entity: str, entity_id, new=None):
    db.add(AuditLog(actorUserId=user.userId, action=action, entityName=entity,
                    entityId=str(entity_id) if entity_id else None,
                    newValue=new if isinstance(new, dict) else None))


class StatusUpdate(BaseModel):
    status: str = Field(min_length=2, max_length=255)
    reason: str | None = None

class IntakeIn(BaseModel):
    facilityId: UUID
    declaredQuantity: Decimal | None = Field(default=None, ge=0)
    receivedQuantity: Decimal | None = Field(default=None, ge=0)
    intakeNotes: str | None = None

class ItemInspection(BaseModel):
    returnItemId: UUID
    inspectionStatus: str = Field(pattern="^(ACCEPTED|REJECTED)$")
    packagingCondition: str | None = None
    findings: str | None = None

class ReturnDecision(BaseModel):
    decision: str = Field(pattern="^(ACCEPTED|REJECTED)$")
    rejectionReason: str | None = None
    itemInspections: list[ItemInspection] = Field(min_length=1)
    creditsByItem: dict[str, Decimal] = Field(default_factory=dict)

class BinIn(BaseModel):
    facilityId: UUID
    binCode: str
    storageCategory: str
    capacityUnits: int = Field(gt=0)
    binStatus: str = "ACTIVE"

class StoreIn(BaseModel):
    returnItemId: UUID
    quantityStored: int = Field(gt=0)

class SealIn(BaseModel):
    binId: UUID | None = None
    manifestId: UUID | None = None
    sealCode: str = Field(min_length=2, max_length=255)

class TrackingIn(BaseModel):
    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)
    trackingStatus: str | None = None
    routeId: UUID | None = None
    assignmentId: UUID | None = None

class DisposalIn(BaseModel):
    facilityId: UUID
    medicineCategory: str
    quantity: Decimal = Field(gt=0)
    disposalMethod: str
    disposalBatchId: UUID | None = None
    intakeId: UUID | None = None
    remarks: str | None = None


@router.get("/facilities")
def facilities(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Facility).where(
        Facility.authorizationStatus.in_(["APPROVED", "approved", "AUTHORIZED", "authorized"]),
        Facility.operatingStatus.in_(["OPERATIONAL", "operational", "ACTIVE", "active"])
    ).order_by(Facility.facilityName)).all()

@router.get("/notifications")
def notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Notification).where(Notification.userId == user.userId).order_by(Notification.createdAt.desc()).limit(100)).all()

@router.patch("/notifications/{notification_id}/read")
def read_notification(notification_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(Notification, notification_id)
    if row is None or row.userId != user.userId:
        raise HTTPException(404, "Notification not found")
    row.isRead = True; row.readAt = datetime.utcnow(); db.commit(); return row

@router.get("/staff/me")
def staff_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = require_staff(db, user)
    return [{"facilityStaff": r, "facility": db.get(Facility, r.facilityId)} for r in rows]

@router.get("/staff/returns")
def staff_returns(status_filter: str | None = Query(default=None, alias="status"), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    staff = require_staff(db, user); facility_ids = [x.facilityId for x in staff]
    stmt = select(ReturnRequest).where(or_(ReturnRequest.facilityId.in_(facility_ids), ReturnRequest.facilityId.is_(None))).order_by(ReturnRequest.createdAt.desc())
    if status_filter: stmt = stmt.where(ReturnRequest.status == status_filter)
    return db.scalars(stmt.limit(200)).all()

@router.post("/staff/returns/{return_id}/intake", status_code=201)
def receive_return(return_id: UUID, payload: IntakeIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    staff = require_staff(db, user)
    if payload.facilityId not in [x.facilityId for x in staff]: raise HTTPException(403, "Facility access denied")
    req = db.get(ReturnRequest, return_id)
    if req is None: raise HTTPException(404, "Return not found")
    if req.returnMethod == "PHARMACY_DROPOFF" and req.facilityId != payload.facilityId:
        raise HTTPException(409, "Drop-off must be received at the selected facility")
    if req.status not in {"SUBMITTED", "VERIFIED", "ASSIGNED", "PICKED_UP", "IN_TRANSIT", "ARRIVED"}:
        raise HTTPException(409, f"Cannot intake a return in {req.status} state")
    intake = FacilityIntake(facilityId=payload.facilityId, returnId=return_id,
        receivedBy=user.userId, intakeStatus="RECEIVED", declaredQuantity=payload.declaredQuantity,
        receivedQuantity=payload.receivedQuantity, intakeNotes=payload.intakeNotes)
    old=req.status; req.status="RECEIVED"
    db.add(intake); db.add(ReturnStatusHistory(returnId=return_id, previousStatus=old, newStatus="RECEIVED", changedBy=user.userId, changeReason="Physical facility receipt"))
    audit(db,user,"RETURN_RECEIVED","ReturnRequest",return_id,{"facilityId":str(payload.facilityId)})
    db.commit(); db.refresh(intake); return intake

@router.post("/staff/returns/{return_id}/decision")
def decide_return(return_id: UUID, payload: ReturnDecision, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    staff=require_staff(db,user)
    req=db.scalar(select(ReturnRequest).where(ReturnRequest.returnId==return_id).with_for_update())
    if req is None: raise HTTPException(404,"Return not found")
    if req.status in {"ACCEPTED","REJECTED","COMPLETED"}: raise HTTPException(409,"This return has already received a final decision")
    if req.facilityId and req.facilityId not in [x.facilityId for x in staff]: raise HTTPException(403,"Facility access denied")
    intake=db.scalar(select(FacilityIntake).where(FacilityIntake.returnId==return_id))
    if intake is None: raise HTTPException(409,"Physical receipt must be recorded before inspection")
    if intake.facilityId not in [x.facilityId for x in staff]: raise HTTPException(403,"Intake facility access denied")
    items=list(db.scalars(select(ReturnItem).where(ReturnItem.returnId==return_id)).all())
    submitted={x.returnItemId for x in payload.itemInspections}
    if len(payload.itemInspections) != len(items) or submitted != {x.returnItemId for x in items}: raise HTTPException(422,"Inspection must cover every return item exactly once")
    if payload.decision=="REJECTED" and not payload.rejectionReason: raise HTTPException(422,"A rejection reason is required")
    if payload.decision=="ACCEPTED" and any(x.inspectionStatus!="ACCEPTED" for x in payload.itemInspections):
        raise HTTPException(422,"Request-level acceptance requires every item inspection to be ACCEPTED")
    if payload.decision=="REJECTED" and any(x.inspectionStatus!="REJECTED" for x in payload.itemInspections):
        raise HTTPException(422,"Request-level rejection applies to every item; partial decisions are not allowed")
    wallet=db.scalar(select(Wallet).where(Wallet.userId==req.userId).with_for_update())
    if payload.decision=="ACCEPTED":
        if set(payload.creditsByItem) != {str(x.returnItemId) for x in items}:
            raise HTTPException(422,"Provide an explicit credit amount for every item; no credit formula is assumed")
        if any(v < 0 for v in payload.creditsByItem.values()): raise HTTPException(422,"Credits cannot be negative")
        if wallet is None: raise HTTPException(409,"Customer wallet does not exist")
    elif payload.creditsByItem and any(v != 0 for v in payload.creditsByItem.values()):
        raise HTTPException(422,"Rejected returns cannot receive credits")
    inspection={x.returnItemId:x for x in payload.itemInspections}
    inspector=next((x for x in staff if x.facilityId==intake.facilityId),None)
    if inspector is None: raise HTTPException(403,"No active staff membership for the receiving facility")
    total=Decimal("0")
    for item in items:
        spec=inspection[item.returnItemId]
        item.inspectionStatus=spec.inspectionStatus
        item.packagingCondition=spec.packagingCondition or item.packagingCondition
        amount=payload.creditsByItem.get(str(item.returnItemId),Decimal("0"))
        item.creditsAwarded=amount; total+=amount
        db.add(InspectionRecord(facilityId=intake.facilityId,binId=None,inspectedBy=inspector.facilityStaffId,inspectionType="RETURN_ITEM",inspectionResult=spec.inspectionStatus,findings=spec.findings,correctiveAction=None))
    old=req.status; req.status=payload.decision; req.verifiedAt=datetime.utcnow()
    req.rejectionReason=payload.rejectionReason if payload.decision=="REJECTED" else None
    req.completedAt=datetime.utcnow()
    if payload.decision=="ACCEPTED" and total>0:
        wallet.availableBalance += total; wallet.updatedAt=datetime.utcnow()
        db.add(WalletTransaction(walletId=wallet.walletId,returnId=req.returnId,transactionType="CREDIT",amount=total,referenceCode=f"RET-{uuid4().hex[:12].upper()}",description="MediCredits awarded after facility receipt and verification"))
    db.add(ReturnStatusHistory(returnId=return_id,previousStatus=old,newStatus=payload.decision,changedBy=user.userId,changeReason=payload.rejectionReason or "Facility inspection completed"))
    db.add(Notification(userId=req.userId,notificationType="RETURN_UPDATE",title=f"Return {payload.decision.lower()}",message=f"Your return request was {payload.decision.lower()}.",relatedReturnId=req.returnId,isRead=False))
    audit(db,user,"RETURN_DECIDED","ReturnRequest",return_id,{"decision":payload.decision,"totalCredits":str(total)})
    db.commit(); return {"returnId":str(return_id),"status":req.status,"totalCreditsAwarded":str(total)}

@router.get("/staff/bins")
def list_bins(facility_id: UUID | None=None, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    staff=require_staff(db,user); ids=[x.facilityId for x in staff]
    stmt=select(StorageBin).where(StorageBin.facilityId.in_(ids))
    if facility_id:
        if facility_id not in ids: raise HTTPException(403,"Facility access denied")
        stmt=stmt.where(StorageBin.facilityId==facility_id)
    return db.scalars(stmt.order_by(StorageBin.binCode)).all()

@router.post("/staff/bins",status_code=201)
def create_bin(payload:BinIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    staff=require_staff(db,user)
    if payload.facilityId not in [x.facilityId for x in staff]: raise HTTPException(403,"Facility access denied")
    row=StorageBin(**payload.model_dump(),currentUnits=0)
    db.add(row); db.commit(); db.refresh(row); return row

@router.post("/staff/bins/{bin_id}/items",status_code=201)
def store_item(bin_id:UUID,payload:StoreIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    staff=require_staff(db,user); binrow=db.get(StorageBin,bin_id)
    if binrow is None or binrow.facilityId not in [x.facilityId for x in staff]: raise HTTPException(404,"Bin not found")
    item=db.get(ReturnItem,payload.returnItemId)
    if item is None: raise HTTPException(404,"Return item not found")
    req=db.get(ReturnRequest,item.returnId)
    if req.status!="ACCEPTED": raise HTTPException(409,"Only accepted return items can be stored")
    if binrow.currentUnits+payload.quantityStored>binrow.capacityUnits: raise HTTPException(409,"Bin capacity exceeded")
    row=BinItem(binId=bin_id,returnItemId=item.returnItemId,quantityStored=payload.quantityStored,storageStatus="STORED")
    binrow.currentUnits+=payload.quantityStored; db.add(row); db.commit(); db.refresh(row); return row

@router.post("/staff/seals",status_code=201)
def apply_seal(payload:SealIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    staff=require_staff(db,user)
    if payload.binId:
        b=db.get(StorageBin,payload.binId)
        if b is None or b.facilityId not in [x.facilityId for x in staff]: raise HTTPException(404,"Bin not found")
    row=TamperSeal(**payload.model_dump(),sealStatus="APPLIED",appliedBy=user.userId)
    db.add(row); db.commit(); db.refresh(row); return row

@router.get("/driver/me")
def driver_profile(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=db.scalar(select(Driver).where(Driver.userId==user.userId))
    if row is None: raise HTTPException(403,"Driver profile is not linked to this account")
    return row

@router.get("/driver/assignments")
def driver_assignments(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    driver=db.scalar(select(Driver).where(Driver.userId==user.userId))
    if driver is None: raise HTTPException(403,"Driver profile is not linked to this account")
    return db.scalars(select(PickupAssignment).where(PickupAssignment.driverId==driver.driverId).order_by(PickupAssignment.assignedAt.desc())).all()

@router.post("/driver/assignments/{assignment_id}/status")
def update_assignment(assignment_id:UUID,payload:StatusUpdate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    driver=db.scalar(select(Driver).where(Driver.userId==user.userId))
    row=db.get(PickupAssignment,assignment_id)
    if driver is None or row is None or row.driverId!=driver.driverId: raise HTTPException(404,"Assignment not found")
    allowed={"ACCEPTED","EN_ROUTE","ARRIVED","PICKED_UP","COMPLETED","CANCELLED"}
    if payload.status not in allowed: raise HTTPException(422,"Unsupported assignment status")
    row.status=payload.status
    if payload.status=="ACCEPTED": row.acceptedAt=datetime.utcnow()
    if payload.status in {"COMPLETED","CANCELLED"}: row.completedAt=datetime.utcnow()
    req=db.get(ReturnRequest,row.returnId); old=req.status
    mapping={"PICKED_UP":"PICKED_UP","EN_ROUTE":"IN_TRANSIT","ARRIVED":"ARRIVED","COMPLETED":"IN_TRANSIT"}
    if payload.status in mapping and old!=mapping[payload.status]:
        req.status=mapping[payload.status]
        db.add(ReturnStatusHistory(returnId=req.returnId,previousStatus=old,newStatus=req.status,changedBy=user.userId,changeReason=payload.reason or "Driver status update"))
    db.commit(); return row

@router.post("/driver/tracking",status_code=201)
def add_tracking(payload:TrackingIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    driver=db.scalar(select(Driver).where(Driver.userId==user.userId))
    if driver is None: raise HTTPException(403,"Driver profile is not linked to this account")
    if payload.assignmentId:
        assignment=db.get(PickupAssignment,payload.assignmentId)
        if assignment is None or assignment.driverId!=driver.driverId: raise HTTPException(403,"Assignment access denied")
    row=TrackingLog(driverId=driver.driverId,**payload.model_dump())
    db.add(row); db.commit(); db.refresh(row); return row

@router.get("/staff/commissions")
def commissions(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    staff=require_staff(db,user); staff_ids=[x.facilityStaffId for x in staff]
    return db.scalars(select(StaffCommission).where(StaffCommission.facilityStaffId.in_(staff_ids)).order_by(StaffCommission.calculatedAt.desc())).all()

@router.get("/staff/commission-payouts")
def commission_payouts(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    staff=require_staff(db,user); staff_ids=[x.facilityStaffId for x in staff]
    return db.scalars(select(CommissionPayout).where(CommissionPayout.facilityStaffId.in_(staff_ids)).order_by(CommissionPayout.initiatedAt.desc())).all()

@router.get("/staff/disposal-batches")
def disposal_batches(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    staff=require_staff(db,user); ids=[x.facilityId for x in staff]
    return db.scalars(select(DisposalBatch).where(DisposalBatch.facilityId.in_(ids)).order_by(DisposalBatch.createdAt.desc())).all()

@router.post("/staff/disposal-records",status_code=201)
def create_disposal(payload:DisposalIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    staff=require_staff(db,user)
    if payload.facilityId not in [x.facilityId for x in staff]: raise HTTPException(403,"Facility access denied")
    if payload.intakeId:
        intake=db.get(FacilityIntake,payload.intakeId)
        if intake is None or intake.facilityId!=payload.facilityId: raise HTTPException(422,"Intake does not belong to this facility")
    row=DisposalRecord(**payload.model_dump(),processedAt=datetime.utcnow(),processedBy=user.userId,disposalStatus="PROCESSED")
    db.add(row); db.commit(); db.refresh(row); return row

@router.get("/tracking/returns/{return_id}")
def return_tracking(return_id:UUID,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    req=db.get(ReturnRequest,return_id)
    if req is None: raise HTTPException(404,"Return not found")
    staff=active_staff(db,user); driver=db.scalar(select(Driver).where(Driver.userId==user.userId))
    owns=req.userId==user.userId
    staff_access=bool(req.facilityId and req.facilityId in [x.facilityId for x in staff])
    driver_access=bool(driver and db.scalar(select(PickupAssignment).where(PickupAssignment.returnId==return_id,PickupAssignment.driverId==driver.driverId)))
    if not (owns or staff_access or driver_access): raise HTTPException(403,"Return access denied")
    assignment=db.scalar(select(PickupAssignment).where(PickupAssignment.returnId==return_id).order_by(PickupAssignment.assignedAt.desc()))
    logs=[]
    if assignment: logs=db.scalars(select(TrackingLog).where(TrackingLog.assignmentId==assignment.assignmentId).order_by(TrackingLog.recordedAt.desc()).limit(50)).all()
    return {"return":req,"assignment":assignment,"tracking":logs}

def auto_assign_pickup(db: Session, req: ReturnRequest):
    """Assign the least-loaded verified, available driver to a verified doorstep return.

    The caller owns the transaction. Driver rows are locked while selecting so
    concurrent return submissions do not all select the same candidate blindly.
    A vehicle is intentionally optional in the existing assignment model.
    """
    eligible = db.scalars(
        select(Driver)
        .where(
            func.lower(Driver.verificationStatus).in_(["verified", "approved", "active"]),
            func.lower(Driver.availabilityStatus).in_(["available"]),
        )
        .order_by(Driver.createdAt, Driver.driverId)
        .with_for_update()
    ).all()
    if not eligible:
        return None, None

    ranked = []
    for driver in eligible:
        active_count = len(db.scalars(
            select(PickupAssignment.assignmentId).where(
                PickupAssignment.driverId == driver.driverId,
                PickupAssignment.status.not_in(["CANCELLED", "COMPLETED"]),
            )
        ).all())
        ranked.append((active_count, driver.createdAt, str(driver.driverId), driver))
    driver = min(ranked, key=lambda row: row[:3])[3]

    assignment = PickupAssignment(
        returnId=req.returnId,
        driverId=driver.driverId,
        vehicleId=None,
        routeId=None,
        assignedAt=datetime.utcnow(),
        status="ASSIGNED",
    )
    previous = req.status
    req.status = "ASSIGNED"
    db.add(assignment)
    db.add(ReturnStatusHistory(
        returnId=req.returnId,
        previousStatus=previous,
        newStatus="ASSIGNED",
        changedBy=None,
        changeReason="System automatically assigned the least-loaded verified available driver",
    ))
    db.add(Notification(
        userId=req.userId,
        notificationType="PICKUP_ASSIGNED",
        title="Driver assigned",
        message=f"{driver.fullName} has been assigned to collect your medicine return.",
        relatedReturnId=req.returnId,
        isRead=False,
    ))
    return assignment, driver


class AssignmentIn(BaseModel):
    returnId: UUID
    driverId: UUID
    vehicleId: UUID | None = None
    routeId: UUID | None = None

@router.get("/staff/dashboard")
def staff_dashboard(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    staff=require_staff(db,user); ids=[x.facilityId for x in staff]
    requests=db.scalars(select(ReturnRequest).where(or_(ReturnRequest.facilityId.in_(ids),ReturnRequest.facilityId.is_(None))).order_by(ReturnRequest.createdAt.desc()).limit(100)).all()
    bins=db.scalars(select(StorageBin).where(StorageBin.facilityId.in_(ids))).all()
    intakes=db.scalars(select(FacilityIntake).where(FacilityIntake.facilityId.in_(ids)).order_by(FacilityIntake.receivedAt.desc()).limit(20)).all()
    return {"returnCount":len(requests),"pendingInspection":sum(1 for x in requests if x.status=="RECEIVED"),"activeBins":sum(1 for x in bins if x.binStatus.upper()=="ACTIVE"),"binCount":len(bins),"recentReturns":requests[:10],"recentIntakes":intakes}

@router.post("/staff/assignments",status_code=201)
def create_assignment(payload:AssignmentIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    staff=require_staff(db,user); req=db.get(ReturnRequest,payload.returnId)
    if req is None: raise HTTPException(404,"Return not found")
    if req.facilityId and req.facilityId not in [x.facilityId for x in staff]: raise HTTPException(403,"Facility access denied")
    driver=db.get(Driver,payload.driverId)
    if driver is None or driver.verificationStatus.lower() not in {"verified","approved","active"}: raise HTTPException(409,"Driver is not verified")
    vehicle=None
    if payload.vehicleId:
        vehicle=db.get(Vehicle,payload.vehicleId)
        if vehicle is None or vehicle.vehicleStatus.lower() not in {"available","active"}: raise HTTPException(409,"Vehicle is not available")
    existing=db.scalar(select(PickupAssignment).where(PickupAssignment.returnId==req.returnId,PickupAssignment.status.not_in(["CANCELLED","COMPLETED"])))
    if existing: raise HTTPException(409,"An active assignment already exists for this return")
    row=PickupAssignment(returnId=req.returnId,driverId=driver.driverId,vehicleId=payload.vehicleId,routeId=payload.routeId,assignedAt=datetime.utcnow(),status="ASSIGNED")
    db.add(row); old=req.status; req.status="ASSIGNED"
    db.add(ReturnStatusHistory(returnId=req.returnId,previousStatus=old,newStatus="ASSIGNED",changedBy=user.userId,changeReason="Driver assigned"))
    db.add(Notification(userId=req.userId,notificationType="PICKUP_ASSIGNED",title="Courier assigned",message="A courier has been assigned to your medicine return.",relatedReturnId=req.returnId,isRead=False))
    audit(db,user,"PICKUP_ASSIGNED","PickupAssignment",row.assignmentId,{"driverId":str(driver.driverId)})
    db.commit();db.refresh(row);return row

@router.get("/staff/drivers")
def staff_drivers(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    require_staff(db,user)
    return db.scalars(select(Driver).where(Driver.verificationStatus.in_(["VERIFIED","verified","APPROVED","approved"]),Driver.availabilityStatus.in_(["AVAILABLE","available"]))).all()

@router.get("/staff/vehicles")
def staff_vehicles(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    require_staff(db,user)
    return db.scalars(select(Vehicle).where(Vehicle.vehicleStatus.in_(["AVAILABLE","available","ACTIVE","active"]))).all()

@router.get("/staff/manifests")
def staff_manifests(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    staff=require_staff(db,user);ids=[x.facilityId for x in staff]
    return db.scalars(select(CollectionManifest).where(or_(CollectionManifest.originFacilityId.in_(ids),CollectionManifest.destinationFacilityId.in_(ids))).order_by(CollectionManifest.createdAt.desc())).all()

@router.get("/staff/disposal-records")
def staff_disposal_records(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    staff=require_staff(db,user);ids=[x.facilityId for x in staff]
    return db.scalars(select(DisposalRecord).where(DisposalRecord.facilityId.in_(ids)).order_by(DisposalRecord.processedAt.desc())).all()

class PickupSlotIn(BaseModel):
    facilityId: UUID
    slotDate: datetime
    startTime: datetime
    endTime: datetime
    capacity: int = Field(gt=0)

@router.get("/staff/pickup-slots")
def staff_pickup_slots(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    staff=require_staff(db,user);ids=[x.facilityId for x in staff]
    return db.scalars(select(PickupSlot).where(PickupSlot.facilityId.in_(ids)).order_by(PickupSlot.slotDate,PickupSlot.startTime)).all()

@router.post("/staff/pickup-slots",status_code=201)
def create_pickup_slot(payload:PickupSlotIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    staff=require_staff(db,user)
    if payload.facilityId not in [x.facilityId for x in staff]: raise HTTPException(403,"Facility access denied")
    if payload.endTime<=payload.startTime: raise HTTPException(422,"End time must be after start time")
    row=PickupSlot(facilityId=payload.facilityId,slotDate=payload.slotDate.date(),startTime=payload.startTime,endTime=payload.endTime,capacity=payload.capacity,bookedCount=0,slotStatus="AVAILABLE")
    db.add(row);db.commit();db.refresh(row);return row

@router.get("/staff/returns/{return_id}")
def staff_return_detail(return_id:UUID,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    staff=require_staff(db,user); req=db.get(ReturnRequest,return_id)
    if req is None: raise HTTPException(404,"Return not found")
    intake=db.scalar(select(FacilityIntake).where(FacilityIntake.returnId==return_id))
    allowed_ids=[x.facilityId for x in staff]
    if (req.facilityId and req.facilityId not in allowed_ids) and (intake is None or intake.facilityId not in allowed_ids): raise HTTPException(403,"Return access denied")
    items=db.scalars(select(ReturnItem).where(ReturnItem.returnId==return_id)).all()
    return {"return":req,"items":items,"intake":intake}

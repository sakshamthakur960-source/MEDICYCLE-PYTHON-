from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text,
    UniqueConstraint, Uuid
)
from sqlalchemy.orm import Mapped, mapped_column
from Database import Base


class User(Base):
    __tablename__ = 'user'
    userId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    fullName: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    phone: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    passwordHash: Mapped[str] = mapped_column(String(255), nullable=False)
    accountStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updatedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    emailVerified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    phoneVerified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lastLoginAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class UserAddress(Base):
    __tablename__ = 'userAddress'
    addressId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    userId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False)
    addressLine: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(255), nullable=False)
    postalCode: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    isDefault: Mapped[bool] = mapped_column(Boolean, nullable=False)
    addressLabel: Mapped[str | None] = mapped_column(String(255), nullable=True)
    landmark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class UserDocument(Base):
    __tablename__ = 'userDocument'
    documentId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    userId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False)
    documentType: Mapped[str] = mapped_column(String(255), nullable=False)
    documentNumber: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filePath: Mapped[str] = mapped_column(String(255), nullable=False)
    uploadedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    documentStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    reviewedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Verification(Base):
    __tablename__ = 'verification'
    verificationId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    userId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False)
    documentId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("userDocument.documentId"), nullable=True, default=None)
    verificationType: Mapped[str] = mapped_column(String(255), nullable=False)
    verificationStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    verifiedBy: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, default=None)
    rejectionReason: Mapped[str | None] = mapped_column(Text, nullable=True)
    verifiedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class Medicine(Base):
    __tablename__ = 'medicine'
    medicineId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    genericName: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    strength: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dosageForm: Mapped[str | None] = mapped_column(String(255), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    medicineCategory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class MedicineBatch(Base):
    __tablename__ = 'medicineBatch'
    __table_args__ = (UniqueConstraint('medicineId', 'batchNumber', name='uq_medicine_batch_number'),)
    batchId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    medicineId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("medicine.medicineId"), nullable=False)
    batchNumber: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturedOn: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiresOn: Mapped[date] = mapped_column(Date, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class UserMedicine(Base):
    __tablename__ = 'userMedicine'
    userMedicineId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    userId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False)
    medicineId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("medicine.medicineId"), nullable=False)
    batchId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("medicineBatch.batchId"), nullable=True, default=None)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    packagingState: Mapped[str] = mapped_column(String(255), nullable=False)
    addedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class MedicineRoutine(Base):
    __tablename__ = 'medicineRoutine'
    routineId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    userId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False)
    userMedicineId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("userMedicine.userMedicineId"), nullable=False)
    routineName: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dosage: Mapped[str] = mapped_column(String(255), nullable=False)
    frequency: Mapped[str] = mapped_column(String(255), nullable=False)
    startDate: Mapped[date] = mapped_column(Date, nullable=False)
    endDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    reminderTime: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    routineStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class Prescription(Base):
    __tablename__ = 'prescription'
    prescriptionId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    userId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False)
    medicineId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("medicine.medicineId"), nullable=True, default=None)
    prescriptionFile: Mapped[str] = mapped_column(String(255), nullable=False)
    prescribingDoctor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prescriptionDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiryDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    verificationStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    uploadedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class ReturnRequest(Base):
    __tablename__ = 'returnRequest'
    returnId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    userId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False)
    addressId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("userAddress.addressId"), nullable=True, default=None)
    returnMethod: Mapped[str] = mapped_column(String(255), nullable=False)
    pickupSlotId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("pickupSlot.pickupSlotId"), nullable=True, default=None)
    status: Mapped[str] = mapped_column(String(255), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    facilityId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=True, default=None)
    requestNotes: Mapped[str | None] = mapped_column(Text, nullable=True)
    verifiedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejectionReason: Mapped[str | None] = mapped_column(Text, nullable=True)
    completedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReturnItem(Base):
    __tablename__ = 'returnItem'
    returnItemId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    returnId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=False)
    medicineId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("medicine.medicineId"), nullable=False)
    batchId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("medicineBatch.batchId"), nullable=True, default=None)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    packagingCondition: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inspectionStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    creditsAwarded: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class PickupSlot(Base):
    __tablename__ = 'pickupSlot'
    pickupSlotId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    facilityId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False)
    slotDate: Mapped[date] = mapped_column(Date, nullable=False)
    startTime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    endTime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    bookedCount: Mapped[int] = mapped_column(Integer, nullable=False)
    slotStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class PickupAssignment(Base):
    __tablename__ = 'pickupAssignment'
    assignmentId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    returnId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=False)
    driverId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("driver.driverId"), nullable=False)
    vehicleId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("vehicle.vehicleId"), nullable=True, default=None)
    assignedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(255), nullable=False)
    routeId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("route.routeId"), nullable=True, default=None)
    acceptedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReturnStatusHistory(Base):
    __tablename__ = 'returnStatusHistory'
    historyId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    returnId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=False)
    previousStatus: Mapped[str | None] = mapped_column(String(255), nullable=True)
    newStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    changedBy: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, default=None)
    changeReason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class Wallet(Base):
    __tablename__ = 'wallet'
    walletId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    userId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False, unique=True)
    availableBalance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    walletStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class WalletTransaction(Base):
    __tablename__ = 'walletTransaction'
    transactionId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    walletId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("wallet.walletId"), nullable=False)
    returnId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=True, default=None)
    redemptionId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("rewardRedemption.redemptionId"), nullable=True, default=None)
    transactionType: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    referenceCode: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Reward(Base):
    __tablename__ = 'reward'
    rewardId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    partnerName: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    creditsRequired: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    validUntil: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(255), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    imagePath: Mapped[str | None] = mapped_column(String(255), nullable=True)


class RewardRedemption(Base):
    __tablename__ = 'rewardRedemption'
    redemptionId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    userId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False)
    rewardId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("reward.rewardId"), nullable=False)
    creditsUsed: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    redemptionCode: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(255), nullable=False)
    redeemedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    expiresAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DisposalCertificate(Base):
    __tablename__ = 'disposalCertificate'
    certificateId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    returnId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=False)
    disposalRecordId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("disposalRecord.disposalRecordId"), nullable=True, default=None)
    certificateNumber: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    certificateFile: Mapped[str] = mapped_column(String(255), nullable=False)
    issuedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    certificateStatus: Mapped[str] = mapped_column(String(255), nullable=False)


class Facility(Base):
    __tablename__ = 'facility'
    facilityId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    facilityName: Mapped[str] = mapped_column(String(255), nullable=False)
    facilityType: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    authorizationStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    operatingStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    contactPhone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contactEmail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FacilityStaff(Base):
    __tablename__ = 'facilityStaff'
    facilityStaffId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    facilityId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False)
    userId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False)
    staffRole: Mapped[str] = mapped_column(String(255), nullable=False)
    employmentStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    joinedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    endedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StorageBin(Base):
    __tablename__ = 'storageBin'
    __table_args__ = (UniqueConstraint('facilityId', 'binCode', name='uq_facility_bin_code'),)
    binId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    facilityId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False)
    binCode: Mapped[str] = mapped_column(String(255), nullable=False)
    storageCategory: Mapped[str] = mapped_column(String(255), nullable=False)
    capacityUnits: Mapped[int] = mapped_column(Integer, nullable=False)
    currentUnits: Mapped[int] = mapped_column(Integer, nullable=False)
    sealCode: Mapped[str | None] = mapped_column(String(255), nullable=True)
    binStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    lastInspectedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BinItem(Base):
    __tablename__ = 'binItem'
    binItemId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    binId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("storageBin.binId"), nullable=False)
    returnItemId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("returnItem.returnItemId"), nullable=False)
    quantityStored: Mapped[int] = mapped_column(Integer, nullable=False)
    storedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    removedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    storageStatus: Mapped[str] = mapped_column(String(255), nullable=False)


class InspectionRecord(Base):
    __tablename__ = 'inspectionRecord'
    inspectionId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    facilityId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False)
    binId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("storageBin.binId"), nullable=True, default=None)
    inspectedBy: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("facilityStaff.facilityStaffId"), nullable=False)
    inspectionType: Mapped[str] = mapped_column(String(255), nullable=False)
    inspectionResult: Mapped[str] = mapped_column(String(255), nullable=False)
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    inspectedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    correctiveAction: Mapped[str | None] = mapped_column(Text, nullable=True)


class TamperSeal(Base):
    __tablename__ = 'tamperSeal'
    tamperSealId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    binId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("storageBin.binId"), nullable=True, default=None)
    manifestId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("collectionManifest.manifestId"), nullable=True, default=None)
    sealCode: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    sealStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    appliedBy: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, default=None)
    appliedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    brokenBy: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, default=None)
    brokenAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    breakReason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Driver(Base):
    __tablename__ = 'driver'
    driverId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    fullName: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    verificationStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    availabilityStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    userId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=True)
    licenseNumber: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    licenseExpiry: Mapped[date | None] = mapped_column(Date, nullable=True)


class Vehicle(Base):
    __tablename__ = 'vehicle'
    vehicleId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    registrationNumber: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    vehicleType: Mapped[str] = mapped_column(String(255), nullable=False)
    capacityKg: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    vehicleStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    assignedDriverId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("driver.driverId"), nullable=True, default=None)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class Route(Base):
    __tablename__ = 'route'
    routeId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    routeName: Mapped[str] = mapped_column(String(255), nullable=False)
    driverId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("driver.driverId"), nullable=False)
    vehicleId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("vehicle.vehicleId"), nullable=True, default=None)
    originFacilityId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=True, default=None)
    destinationFacilityId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=True, default=None)
    routeDate: Mapped[date] = mapped_column(Date, nullable=False)
    routeStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    plannedStartAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actualStartAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RouteStop(Base):
    __tablename__ = 'routeStop'
    __table_args__ = (UniqueConstraint('routeId', 'stopSequence', name='uq_route_stop_sequence'),)
    routeStopId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    routeId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("route.routeId"), nullable=False)
    facilityId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=True, default=None)
    returnId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=True, default=None)
    stopSequence: Mapped[int] = mapped_column(Integer, nullable=False)
    stopType: Mapped[str] = mapped_column(String(255), nullable=False)
    plannedArrivalAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actualArrivalAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stopStatus: Mapped[str] = mapped_column(String(255), nullable=False)


class CollectionManifest(Base):
    __tablename__ = 'collectionManifest'
    manifestId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    manifestCode: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    driverId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("driver.driverId"), nullable=False)
    originFacilityId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False)
    destinationFacilityId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False)
    totalWeightKg: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(255), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    vehicleId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("vehicle.vehicleId"), nullable=True, default=None)
    routeId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("route.routeId"), nullable=True, default=None)
    dispatchedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    receivedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=datetime.utcnow)


class CustodyTransfer(Base):
    __tablename__ = 'custodyTransfer'
    custodyTransferId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    manifestId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("collectionManifest.manifestId"), nullable=True, default=None)
    returnId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=True, default=None)
    fromPartyType: Mapped[str] = mapped_column(String(255), nullable=False)
    fromPartyId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    toPartyType: Mapped[str] = mapped_column(String(255), nullable=False)
    toPartyId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    transferredBy: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, default=None)
    receivedBy: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, default=None)
    transferStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    transferredAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)


class TrackingLog(Base):
    __tablename__ = 'trackingLog'
    trackingLogId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    driverId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("driver.driverId"), nullable=False)
    routeId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("route.routeId"), nullable=True, default=None)
    assignmentId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("pickupAssignment.assignmentId"), nullable=True, default=None)
    latitude: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    recordedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    trackingStatus: Mapped[str | None] = mapped_column(String(255), nullable=True)


class FacilityIntake(Base):
    __tablename__ = 'facilityIntake'
    intakeId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    facilityId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False)
    manifestId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("collectionManifest.manifestId"), nullable=True, default=None)
    returnId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=True, default=None)
    receivedBy: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, default=None)
    intakeStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    receivedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    declaredQuantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    receivedQuantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    intakeNotes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DisposalBatch(Base):
    __tablename__ = 'disposalBatch'
    disposalBatchId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    facilityId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False)
    batchCode: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    batchStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    processingStartedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processingCompletedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    totalQuantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    createdBy: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, default=None)


class DisposalRecord(Base):
    __tablename__ = 'disposalRecord'
    disposalRecordId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    facilityId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("facility.facilityId"), nullable=False)
    manifestId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("collectionManifest.manifestId"), nullable=True, default=None)
    medicineCategory: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    disposalMethod: Mapped[str] = mapped_column(String(255), nullable=False)
    processedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    certificateReference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    disposalBatchId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("disposalBatch.disposalBatchId"), nullable=True, default=None)
    intakeId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("facilityIntake.intakeId"), nullable=True, default=None)
    processedBy: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, default=None)
    disposalStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)


class StaffCommission(Base):
    __tablename__ = 'staffCommission'
    commissionId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    facilityStaffId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("facilityStaff.facilityStaffId"), nullable=False)
    returnId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=True, default=None)
    commissionAmount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    commissionStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    calculatedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    approvedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CommissionPayout(Base):
    __tablename__ = 'commissionPayout'
    payoutId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    facilityStaffId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("facilityStaff.facilityStaffId"), nullable=False)
    payoutReference: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    totalAmount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payoutStatus: Mapped[str] = mapped_column(String(255), nullable=False)
    payoutMethod: Mapped[str | None] = mapped_column(String(255), nullable=True)
    initiatedAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    completedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Notification(Base):
    __tablename__ = 'notification'
    notificationId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    userId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=False)
    notificationType: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    relatedReturnId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("returnRequest.returnId"), nullable=True, default=None)
    isRead: Mapped[bool] = mapped_column(Boolean, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    readAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = 'auditLog'
    auditLogId: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    actorUserId: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("user.userId"), nullable=True, default=None)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    entityName: Mapped[str] = mapped_column(String(255), nullable=False)
    entityId: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oldValue: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    newValue: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ipAddress: Mapped[str | None] = mapped_column(String(255), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

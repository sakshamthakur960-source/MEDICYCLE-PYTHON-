from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class RegisterIn(BaseModel):
    fullName: str = Field(min_length=2, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=30)
    password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def require_contact(self):
        if not self.email and not self.phone:
            raise ValueError("Provide an email address or phone number")
        return self


class LoginIn(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    userId: UUID
    fullName: str
    email: str | None
    phone: str | None
    accountStatus: str
    emailVerified: bool
    phoneVerified: bool


class AddressIn(BaseModel):
    addressLine: str = Field(min_length=3, max_length=255)
    city: str = Field(min_length=2, max_length=255)
    state: str = Field(min_length=2, max_length=255)
    postalCode: str = Field(min_length=4, max_length=20)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    isDefault: bool = False
    addressLabel: str | None = Field(default=None, max_length=255)
    landmark: str | None = Field(default=None, max_length=255)


class MedicineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    medicineId: UUID
    name: str
    genericName: str | None
    manufacturer: str | None
    strength: str | None
    dosageForm: str | None
    barcode: str | None


class UserMedicineIn(BaseModel):
    medicineId: UUID
    batchId: UUID | None = None
    quantity: int = Field(gt=0)
    packagingState: str = Field(min_length=1, max_length=255)
    notes: str | None = None


class MedicinePurchaseIn(BaseModel):
    medicineId: UUID
    batchNumber: str = Field(min_length=1, max_length=255)
    expiresOn: date
    manufacturedOn: date | None = None
    quantity: int = Field(gt=0)
    packagingState: str = Field(default="SEALED", min_length=1, max_length=255)
    sourcePlatform: str = Field(pattern="^(TATA_1MG|PHARMEASY)$")
    externalOrderId: str | None = Field(default=None, max_length=255)
    purchaseDate: date | None = None
    notes: str | None = None


class ReturnItemIn(BaseModel):
    medicineId: UUID
    batchId: UUID | None = None
    quantity: int = Field(gt=0)
    packagingCondition: str | None = None


class ReturnCreateIn(BaseModel):
    addressId: UUID | None = None
    returnMethod: str = Field(pattern="^(DOORSTEP_PICKUP|PHARMACY_DROPOFF)$")
    pickupSlotId: UUID | None = None
    facilityId: UUID | None = None
    requestNotes: str | None = None
    items: list[ReturnItemIn] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_method_fields(self):
        if self.returnMethod == "DOORSTEP_PICKUP" and self.pickupSlotId is None:
            raise ValueError("A pickup slot is required for doorstep pickup")
        if self.returnMethod == "PHARMACY_DROPOFF" and self.facilityId is None:
            raise ValueError("A drop-off facility is required for pharmacy drop-off")
        return self


class ReturnDecisionIn(BaseModel):
    decision: str = Field(pattern="^(ACCEPTED|REJECTED)$")
    rejectionReason: str | None = None
    totalCreditsAwarded: Decimal = Field(default=Decimal("0.00"), ge=0)

    @model_validator(mode="after")
    def validate_decision(self):
        if self.decision == "REJECTED" and not self.rejectionReason:
            raise ValueError("A rejection reason is required")
        if self.decision == "REJECTED" and self.totalCreditsAwarded != 0:
            raise ValueError("Rejected returns cannot receive credits")
        return self


class RewardRedemptionIn(BaseModel):
    rewardId: UUID

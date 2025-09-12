from datetime import datetime

from pydantic import BaseModel, Field


class Price(BaseModel):
    """Model for price information"""

    id: str
    value: float
    pennies: int
    currency: str
    formatted: str

    def to_record(self, prefix: str) -> dict:
        return {f"{prefix}{k}": v for k, v in self.model_dump(include={"value", "currency"}).items()}


class PriceData(BaseModel):
    """Wrapper for price data"""

    data: Price


class Vehicle(BaseModel):
    """Model for vehicle information"""

    id: int
    make: str
    model: str
    registration: str
    colour: str | None = None
    is_primary: bool
    auto_pay: bool
    is_auto_pay_eligible: bool


class VehicleData(BaseModel):
    """Wrapper for vehicle data"""

    data: Vehicle


class Driver(BaseModel):
    """Model for driver information"""

    id: int
    name: str
    first_name: str
    last_name: str
    profile_photo: str
    is_managed: bool
    registration_date: datetime
    email: str
    email_verified: bool
    phone_number: str | None = None
    phone_number_verified: str | bool | None = None
    company_name: str


class DriverData(BaseModel):
    """Wrapper for driver data"""

    data: Driver


class Booking(BaseModel):
    """Model for a JustPark booking"""

    id: int
    start_date: datetime
    end_date: datetime
    listing_id: int
    owner_id: int
    driver_id: int
    vehicle_id: int
    type: str
    status: str
    timezone: str
    title: str
    photos: list[str]
    infinite: bool
    booking_type: str
    auto_pay: bool
    ev_charging: bool
    vehicle: VehicleData
    driver: DriverData
    driver_price: PriceData
    space_owner_earnings: PriceData

    def to_record(self) -> dict:
        return (
            self.model_dump(exclude={"vehicle", "driver", "driver_price", "space_owner_earnings"})
            | self.driver_price.data.to_record("paid_")
            | self.space_owner_earnings.data.to_record("earnings_")
        )


class BookingResponse(BaseModel):
    """Model for the complete booking response"""

    fetchedAt: datetime = Field(alias="fetchedAt")
    total: int
    items: list[Booking]

    model_config = {"populate_by_name": True}

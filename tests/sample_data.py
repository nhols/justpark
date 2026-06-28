import json
from datetime import datetime, timedelta


def payload() -> dict:
    base = datetime.fromisoformat("2026-02-20T09:00:00+00:00")
    people = [
        (
            1,
            "Amelia Hart",
            "amelia@example.com",
            "07111 111111",
            "AA24 MLF",
            "Volvo",
            "XC40",
            10,
        ),
        (
            2,
            "Marcus Chen",
            "marcus@example.com",
            "07222 222222",
            "LK73 ZNN",
            "Tesla",
            "Model 3",
            6,
        ),
        (
            3,
            "Priya Shah",
            "priya@example.com",
            "07333 333333",
            "PN21 YRT",
            "BMW",
            "i4",
            4,
        ),
        (4, "Theo Martin", "theo@example.com", None, "GX19 KWP", "Ford", "Focus", 2),
    ]
    bookings = []
    booking_id = 100
    for person_index, (
        driver_id,
        name,
        email,
        phone,
        reg,
        make,
        model,
        count,
    ) in enumerate(people):
        for index in range(count):
            start = base + timedelta(
                days=person_index * 5 + index * 9, hours=(index * 3) % 8
            )
            duration = 3 + ((index + person_index) % 5) * 4
            status = (
                "cancelled" if driver_id == 2 and index == count - 1 else "confirmed"
            )
            bookings.append(
                booking(
                    booking_id,
                    start,
                    start + timedelta(hours=duration),
                    driver_id,
                    name,
                    email,
                    phone,
                    reg,
                    make,
                    model,
                    7.5 + duration * 0.85,
                    status,
                )
            )
            booking_id += 1
    return {
        "fetchedAt": "2026-06-28T13:18:00Z",
        "total": len(bookings),
        "items": bookings,
    }


def booking(
    booking_id: int,
    start: datetime,
    end: datetime,
    driver_id: int,
    name: str,
    email: str,
    phone: str | None,
    registration: str,
    make: str,
    model: str,
    earnings: float,
    status: str = "confirmed",
) -> dict:
    def price(value: float) -> dict:
        return {
            "data": {
                "id": str(booking_id),
                "value": value,
                "pennies": round(value * 100),
                "currency": "GBP",
                "formatted": f"£{value:.2f}",
            }
        }

    return {
        "id": booking_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "listing_id": 1,
        "owner_id": 1,
        "driver_id": driver_id,
        "vehicle_id": driver_id,
        "type": "booking",
        "status": status,
        "timezone": "Europe/London",
        "title": "Driveway parking",
        "photos": [],
        "infinite": False,
        "booking_type": "standard",
        "auto_pay": False,
        "ev_charging": False,
        "vehicle": {
            "data": {
                "id": driver_id,
                "make": make,
                "model": model,
                "registration": registration,
                "colour": "Midnight blue",
                "is_primary": True,
                "auto_pay": False,
                "is_auto_pay_eligible": True,
            }
        },
        "driver": {
            "data": {
                "id": driver_id,
                "name": name,
                "first_name": name.split()[0],
                "last_name": name.split()[-1],
                "profile_photo": "",
                "is_managed": False,
                "registration_date": "2024-01-10T10:00:00",
                "email": email,
                "email_verified": True,
                "phone_number": phone,
                "phone_number_verified": bool(phone),
                "company_name": "",
            }
        },
        "driver_price": price(round(earnings * 1.25, 2)),
        "space_owner_earnings": price(round(earnings, 2)),
    }


if __name__ == "__main__":
    print(json.dumps(payload()))

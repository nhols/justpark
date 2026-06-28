from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from src.bookings.models import Booking, BookingResponse

LONDON = ZoneInfo("Europe/London")
WINDOWS = (7, 14, 30, 90)


def tax_year_start(today: date | None = None) -> date:
    today = today or datetime.now(LONDON).date()
    return date(today.year if today >= date(today.year, 4, 6) else today.year - 1, 4, 6)


def build_dashboard(raw: str | bytes, now: datetime | None = None) -> dict[str, Any]:
    data = BookingResponse.model_validate_json(raw)
    now = now or datetime.now(LONDON)
    active = [booking for booking in data.items if booking.status != "cancelled"]
    cancelled = [booking for booking in data.items if booking.status == "cancelled"]

    return {
        "schemaVersion": 2,
        "fetchedAt": data.fetchedAt.isoformat(),
        "generatedAt": now.isoformat(),
        "summary": {
            "bookings": len(active),
            "cancelled": len(cancelled),
            "drivers": len({booking.driver_id for booking in active}),
        },
        "bookings": [
            _booking_row(booking)
            for booking in sorted(data.items, key=lambda b: b.start_date)
        ],
        "earnings": _earnings(active, now.date()),
        "occupancy": _occupancy(active),
        "drivers": _drivers(data.items),
        "driverHighlights": _driver_highlights(active, now.date()),
        "vehicles": _vehicles(data.items),
    }


def _booking_row(booking: Booking) -> dict[str, Any]:
    driver = booking.driver.data
    vehicle = booking.vehicle.data
    return {
        "id": booking.id,
        "start": booking.start_date.isoformat(),
        "end": booking.end_date.isoformat(),
        "status": booking.status,
        "title": booking.title,
        "bookingType": booking.booking_type,
        "driverId": driver.id,
        "driverName": driver.name,
        "driverEmail": driver.email,
        "driverPhone": driver.phone_number,
        "vehicleId": vehicle.id,
        "registration": vehicle.registration,
        "vehicle": " ".join(part for part in (vehicle.make, vehicle.model) if part),
        "vehicleColour": vehicle.colour,
        "earnings": booking.space_owner_earnings.data.value,
        "paid": booking.driver_price.data.value,
    }


def _earnings(bookings: list[Booking], today: date) -> dict[str, Any]:
    start = tax_year_start(today)
    periods: dict[str, dict[date, float]] = {
        name: defaultdict(float) for name in _period_keys(today)
    }

    for booking in bookings:
        day = booking.start_date.astimezone(LONDON).date()
        amount = booking.space_owner_earnings.data.value
        for name, key in _period_keys(day).items():
            periods[name][key] += amount

    return {
        "total": round(
            sum(booking.space_owner_earnings.data.value for booking in bookings), 2
        ),
        "taxYear": round(
            sum(
                booking.space_owner_earnings.data.value
                for booking in bookings
                if booking.start_date.astimezone(LONDON).date() >= start
            ),
            2,
        ),
        "bookings": len(bookings),
        "periods": {
            name: [
                {"date": day.isoformat(), "value": round(value, 2)}
                for day, value in sorted(values.items())
            ]
            for name, values in periods.items()
        },
    }


def _period_keys(day: date) -> dict[str, date]:
    return {
        "day": day,
        "week": day - timedelta(days=day.weekday()),
        "month": day.replace(day=1),
        "quarter": day.replace(month=((day.month - 1) // 3) * 3 + 1, day=1),
        "year": day.replace(month=1, day=1),
    }


def _occupancy(bookings: list[Booking]) -> dict[str, Any]:
    if not bookings:
        return {"windows": list(WINDOWS), "minutes": [], "days": []}

    intervals: dict[date, list[tuple[datetime, datetime]]] = defaultdict(list)
    first = min(booking.start_date.astimezone(LONDON).date() for booking in bookings)
    last = max(booking.end_date.astimezone(LONDON).date() for booking in bookings)

    for booking in bookings:
        start, end = (
            booking.start_date.astimezone(LONDON),
            booking.end_date.astimezone(LONDON),
        )
        day = start.date()
        while day <= end.date():
            day_start = datetime.combine(day, time.min, LONDON)
            day_end = day_start + timedelta(days=1)
            overlap = max(start, day_start), min(end, day_end)
            if overlap[0] < overlap[1]:
                intervals[day].append(overlap)
            day += timedelta(days=1)

    dates = [
        first + timedelta(days=offset) for offset in range((last - first).days + 1)
    ]
    minutes = [_merged_minutes(intervals[day]) for day in dates]
    return {
        "windows": list(WINDOWS),
        "minutes": _rolling_rows(dates, [value / 1440 for value in minutes]),
        "days": _rolling_rows(dates, [float(value > 0) for value in minutes]),
    }


def _merged_minutes(intervals: list[tuple[datetime, datetime]]) -> float:
    merged: list[list[datetime]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return min(1440, sum((end - start).total_seconds() / 60 for start, end in merged))


def _rolling_rows(dates: list[date], values: list[float]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, day in enumerate(dates):
        row: dict[str, Any] = {"date": day.isoformat()}
        for window in WINDOWS:
            row[str(window)] = (
                round(mean(values[index - window + 1 : index + 1]), 6)
                if index + 1 >= window
                else None
            )
        rows.append(row)
    return rows


def _drivers(bookings: list[Booking]) -> list[dict[str, Any]]:
    grouped: dict[int, list[Booking]] = defaultdict(list)
    for booking in bookings:
        grouped[booking.driver_id].append(booking)

    rows = []
    for driver_id, all_bookings in grouped.items():
        active = [booking for booking in all_bookings if booking.status != "cancelled"]
        driver = all_bookings[-1].driver.data
        durations = [_hours(booking) for booking in active]
        rows.append(
            {
                "id": driver_id,
                "name": driver.name,
                "email": driver.email,
                "phone": driver.phone_number,
                "company": driver.company_name,
                "profilePhoto": driver.profile_photo,
                "registeredAt": driver.registration_date.isoformat(),
                "bookings": len(active),
                "cancelled": len(all_bookings) - len(active),
                "earnings": round(
                    sum(booking.space_owner_earnings.data.value for booking in active),
                    2,
                ),
                "paid": round(
                    sum(booking.driver_price.data.value for booking in active), 2
                ),
                "averageHours": round(mean(durations), 1) if durations else 0,
                "longestHours": round(max(durations), 1) if durations else 0,
                "firstBooking": min(
                    (booking.start_date for booking in active), default=None
                ),
                "lastBooking": max(
                    (booking.start_date for booking in active), default=None
                ),
                "vehicles": sorted(
                    {booking.vehicle.data.registration for booking in all_bookings}
                ),
            }
        )
    for row in rows:
        for key in ("firstBooking", "lastBooking"):
            row[key] = row[key].isoformat() if row[key] else None
    return sorted(rows, key=lambda row: (-row["earnings"], row["name"]))


def _driver_highlights(bookings: list[Booking], today: date) -> dict[str, Any]:
    if not bookings:
        return {}
    grouped: dict[int, list[Booking]] = defaultdict(list)
    for booking in bookings:
        grouped[booking.driver_id].append(booking)

    earnings = {
        driver_id: sum(booking.space_owner_earnings.data.value for booking in items)
        for driver_id, items in grouped.items()
    }
    total = sum(earnings.values())
    repeat = {driver_id for driver_id, items in grouped.items() if len(items) >= 2}
    longest = max(bookings, key=_hours)
    weekdays = Counter(
        booking.start_date.astimezone(LONDON).strftime("%A") for booking in bookings
    )
    hours = Counter(booking.start_date.astimezone(LONDON).hour for booking in bookings)
    first_bookings = {
        driver_id: min(
            booking.start_date.astimezone(LONDON).date() for booking in items
        )
        for driver_id, items in grouped.items()
    }

    return {
        "repeatRate": len(repeat) / len(grouped),
        "returningRevenueShare": sum(earnings[driver_id] for driver_id in repeat)
        / total
        if total
        else 0,
        "topThreeRevenueShare": sum(sorted(earnings.values(), reverse=True)[:3]) / total
        if total
        else 0,
        "newThisTaxYear": sum(
            first >= tax_year_start(today) for first in first_bookings.values()
        ),
        "busiestWeekday": weekdays.most_common(1)[0][0],
        "busiestHour": f"{hours.most_common(1)[0][0]:02d}:00",
        "longestStay": {
            "driver": longest.driver.data.name,
            "hours": round(_hours(longest), 1),
            "date": longest.start_date.date().isoformat(),
        },
    }


def _vehicles(bookings: list[Booking]) -> list[dict[str, Any]]:
    vehicles = {booking.vehicle_id: booking.vehicle.data for booking in bookings}
    return [
        {
            "id": vehicle.id,
            "registration": vehicle.registration,
            "make": vehicle.make,
            "model": vehicle.model,
            "colour": vehicle.colour,
            "primary": vehicle.is_primary,
            "autoPay": vehicle.auto_pay,
        }
        for vehicle in sorted(
            vehicles.values(), key=lambda vehicle: vehicle.registration
        )
    ]


def _hours(booking: Booking) -> float:
    return (booking.end_date - booking.start_date).total_seconds() / 3600

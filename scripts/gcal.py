# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "boto3",
#     "google-api-python-client",
#     "google-api-python-client-stubs",
#     "pydantic",
#     "types-boto3[s3]",
# ]
# ///

import datetime
import hashlib
import json
import logging
import os
from typing import TYPE_CHECKING, cast

import boto3
from google.oauth2 import service_account
from googleapiclient.discovery import build
from zoneinfo import ZoneInfo

from src.bookings.models import Booking, BookingResponse

if TYPE_CHECKING:
    from googleapiclient._apis.calendar.v3 import CalendarResource, Event, EventDateTime

logger = logging.getLogger(__name__)

TZ = "Europe/London"
CALENDAR_ID = os.environ["CALENDAR_ID"]
S3_BUCKET = os.environ["JP_S3_BUCKET"]
S3_KEY = os.environ["JP_S3_KEY"]


def get_data() -> BookingResponse:
    if not S3_BUCKET or not S3_KEY:
        raise ValueError("S3_BUCKET and S3_KEY environment variables must be set")
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
    return BookingResponse.model_validate_json(obj["Body"].read())


def get_client() -> "CalendarResource":
    service_account_info = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not service_account_info:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON environment variable is not set")

    try:
        service_account_data = json.loads(service_account_info)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in GOOGLE_SERVICE_ACCOUNT_JSON environment variable")

    creds = service_account.Credentials.from_service_account_info(
        service_account_data, scopes=["https://www.googleapis.com/auth/calendar"]
    )
    service = build("calendar", "v3", credentials=creds)
    return cast("CalendarResource", service)


def booking_to_html(booking: Booking, s3_url: str | None = None) -> str:
    vehicle = booking.vehicle.data
    driver = booking.driver.data
    parts = [
        f"<p><strong>Booking ID:</strong> {booking.id}</p>",
        f"<p><strong>Driver:</strong> {driver.name}</p>",
        f"<p><strong>Email:</strong> {driver.email}</p>",
        f"<p><strong>Phone:</strong> {driver.phone_number or 'N/A'}</p>",
        f"<p><strong>Vehicle:</strong> {vehicle.registration or 'N/A'} - {vehicle.make or 'N/A'} {vehicle.model or ''} ({vehicle.colour or 'N/A'})</p>",
        f"<p><strong>Start:</strong> {booking.start_date.astimezone(ZoneInfo(TZ)).strftime('%Y-%m-%d %H:%M')}</p>",
        f"<p><strong>End:</strong> {booking.end_date.astimezone(ZoneInfo(TZ)).strftime('%Y-%m-%d %H:%M')}</p>",
        f"<p><strong>Paid:</strong> {booking.driver_price.data.formatted}</p>",
        f"<p><strong>Earnings:</strong> {booking.space_owner_earnings.data.formatted}</p>",
    ]
    if s3_url:
        parts.append(f'<p><a href="{s3_url}">View all bookings</a></p>')
    return "".join(parts)


def push_bookings_to_calendar(bookings: list[Booking]) -> None:
    service = get_client()

    if not bookings:
        logger.info("No bookings to push to calendar")
        return

    def callback(request_id, response, exception):
        if exception is not None:
            logger.error(f"Error creating event for request {request_id}: {exception}")
        else:
            logger.info(f"Successfully created event: {response.get('summary', 'Unknown')}")

    batch = service.new_batch_http_request()
    for i, booking in enumerate(bookings):
        logger.info(f"Adding booking to batch: {booking}")
        event = booking_to_event(booking)
        batch.add(service.events().insert(calendarId=CALENDAR_ID, body=event), callback=callback, request_id=str(i))

    logger.info(f"Executing batch request with {len(bookings)} events")
    batch.execute()


def delete_events(event_ids: list[str]) -> None:
    service = get_client()

    def callback(request_id, response, exception):
        if exception is not None:
            logger.error(f"Error deleting event for request {request_id}: {exception}")
        else:
            logger.info(f"Successfully deleted event with ID: {request_id}")

    batch = service.new_batch_http_request()
    for event_id in event_ids:
        logger.info(f"Adding delete request to batch for event ID: {event_id}")
        batch.add(
            service.events().delete(calendarId=CALENDAR_ID, eventId=event_id), callback=callback, request_id=event_id
        )

    logger.info(f"Executing batch delete request with {len(event_ids)} events")
    batch.execute()


def booking_hash(booking: Booking) -> str:
    return hashlib.md5(booking.model_dump_json().encode()).hexdigest()


def booking_to_event(booking: Booking) -> "Event":
    title = booking.vehicle.data.registration or "BPMA Track booked"
    start = {
        "dateTime": booking.start_date.isoformat(),
        "timeZone": TZ,
    }
    end = {
        "dateTime": booking.end_date.isoformat(),
        "timeZone": TZ,
    }

    data_hash = booking_hash(booking)

    private_props = {"booking_id": booking.id, "data_hash": data_hash}
    return {
        "summary": title,
        "description": booking_to_html(booking),
        "start": cast("EventDateTime", start),
        "end": cast("EventDateTime", end),
        "extendedProperties": {"private": private_props},
    }


def list_events_after(after_date: datetime.date) -> list["Event"]:
    service = get_client()

    tz = ZoneInfo(TZ)
    time_min = datetime.datetime.combine(after_date, datetime.time.min, tzinfo=tz).isoformat()

    logger.info(f"Listing events after {time_min}")
    events_result = (
        service.events()
        .list(
            calendarId=CALENDAR_ID,
            timeMin=time_min,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return events_result.get("items", [])


def get_insert_delete(future_bookings: list[Booking], events: list["Event"]) -> tuple[list[Booking], list["Event"]]:
    booking_hashes = {booking_hash(booking): booking for booking in future_bookings}
    event_hashes = {
        hash: event
        for event in events
        if (hash := event.get("extendedProperties", {}).get("private", {}).get("data_hash"))
    }
    deleted_event_hashes = set(event_hashes) - set(booking_hashes)
    new_booking_hashes = set(booking_hashes) - set(event_hashes)

    return (
        list(booking_hashes[hash] for hash in new_booking_hashes if booking_hashes[hash].status != "cancelled"),
        list(event_hashes[hash] for hash in deleted_event_hashes),
    )


def main() -> None:
    today = datetime.date.today()
    bookings = get_data()
    future_bookings = [b for b in bookings.items if b.end_date.date() >= today]
    events = list_events_after(today)
    logger.info(f"Found {len(events)} events after {today}")

    to_insert, to_delete = get_insert_delete(future_bookings, events)
    logger.info(f"{len(to_insert)} bookings to insert, {len(to_delete)} events to delete")
    if to_delete:
        delete_events([event["id"] for event in to_delete if "id" in event])
    if to_insert:
        push_bookings_to_calendar(to_insert)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()

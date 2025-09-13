import polars as pl

BOOKINGS = pl.Schema(
    {
        "id": pl.Int64,
        "start_date": pl.Datetime(time_zone="Europe/London"),
        "end_date": pl.Datetime(time_zone="Europe/London"),
        "listing_id": pl.Int64,
        "owner_id": pl.Int64,
        "driver_id": pl.Int64,
        "vehicle_id": pl.Int64,
        "type": pl.String,
        "status": pl.String,
        "timezone": pl.String,
        "title": pl.String,
        "photos": pl.List(pl.Utf8),
        "infinite": pl.Boolean,
        "booking_type": pl.String,
        "auto_pay": pl.Boolean,
        "ev_charging": pl.Boolean,
        "earnings_currency": pl.String,
        "earnings_value": pl.Float64,
        "paid_currency": pl.String,
        "paid_value": pl.Float64,
    }
)

DRIVER = pl.Schema(
    {
        "id": pl.Int64,
        "name": pl.String,
        "first_name": pl.String,
        "last_name": pl.String,
        "profile_photo": pl.String,
        "is_managed": pl.Boolean,
        "registration_date": pl.Datetime(time_zone=None),
        "email": pl.String,
        "email_verified": pl.Boolean,
        "phone_number": pl.String,
        "phone_number_verified": pl.String,
        "company_name": pl.String,
    }
)

VEHICLE = pl.Schema(
    {
        "id": pl.Int64,
        "make": pl.String,
        "model": pl.String,
        "registration": pl.String,
        "colour": pl.String,
        "is_primary": pl.Boolean,
        "auto_pay": pl.Boolean,
        "is_auto_pay_eligible": pl.Boolean,
    }
)

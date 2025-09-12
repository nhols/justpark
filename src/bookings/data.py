from datetime import datetime
from typing import Optional, Self

import polars as pl

VEHICLE_SCHEMA = pl.Schema(
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


DRIVER_SCHEMA = pl.Schema(
    {
        "id": pl.Int64,
        "name": pl.String,
        "first_name": pl.String,
        "last_name": pl.String,
        "profile_photo": pl.String,
        "is_managed": pl.Boolean,
        "registration_date": pl.String,
        "email": pl.String,
        "email_verified": pl.Boolean,
        "phone_number": pl.String,
        "phone_number_verified": pl.String,
        "company_name": pl.String,
    }
)


PRICE_SCHEMA = pl.Schema(
    {"id": pl.String, "value": pl.Float64, "pennies": pl.Int64, "currency": pl.String, "formatted": pl.String}
)


BOOKING_SCHEMA = pl.Schema(
    {
        "id": pl.Int64,
        "start_date": pl.String,
        "end_date": pl.String,
        "listing_id": pl.Int64,
        "owner_id": pl.Int64,
        "driver_id": pl.Int64,
        "vehicle_id": pl.Int64,
        "type": pl.String,
        "status": pl.String,
        "timezone": pl.String,
        "title": pl.String,
        "photos": pl.List(pl.String),
        "infinite": pl.Boolean,
        "booking_type": pl.String,
        "auto_pay": pl.Boolean,
        "ev_charging": pl.Boolean,
        "vehicle_data": pl.Struct(VEHICLE_SCHEMA),
        "driver_data": pl.Struct(DRIVER_SCHEMA),
        "driver_price_data": pl.Struct(PRICE_SCHEMA),
        "space_owner_earnings_data": pl.Struct(PRICE_SCHEMA),
    }
)


ROOT_SCHEMA = pl.Schema({"fetchedAt": pl.String, "total": pl.Int64, "items": pl.List(pl.Struct(BOOKING_SCHEMA))})


class BookingsData:
    """
    Class to handle bookings data with defined schema.
    """

    def __init__(self, data: pl.DataFrame):
        self.data = data

    @classmethod
    def from_json(cls, json_data: dict) -> Self:
        """
        Create a BookingsData instance from JSON data.

        Args:
            json_data (dict): The JSON data as a dictionary.
        """
        bookings_df = parse_bookings_json(json_data)
        return cls(bookings_df)

    def driver_details(self) -> pl.DataFrame:
        """
        Extract unique driver details from the bookings data.

        Returns:
            pl.DataFrame: A DataFrame with `DRIVER_SCHEMA` columns.
        """
        driver_details_df = (
            self.data.select(pl.col("driver").struct.field("data").alias("driver_info"), "driver_id")
            .unnest("driver_info")
            .unique("driver_id")
        )

        return driver_details_df

    def driver_stats(self) -> pl.DataFrame:
        """
        Compute statistics about drivers in the bookings data.

        Includes columns driver_id and name plus:
        - num_bookings: Number of bookings made by the driver.
        - num_cancelled: Number of bookings cancelled by the driver.
        - total_earnings: Total earnings from all bookings by the driver.
        - total_paid_by_driver: Total price paid by the driver for all bookings.
        - longest_stay: Duration of the longest booking by the driver in hours.
        - average_stay: Average duration of bookings by the driver in hours.
        - shortest_stay: Duration of the shortest booking by the driver in hours.
        - first_booking: Date of the first booking by the driver.
        - last_booking: Date of the most recent booking by the driver.

        Returns:
            pl.DataFrame: A DataFrame statistics about drivers.
        """

        working_df = self.data.select(
            pl.col("id").alias("booking_id"),
            "driver_id",
            "status",
            pl.col("start_date").str.to_datetime(format="%Y-%m-%dT%H:%M:%S%z").alias("start_datetime"),
            pl.col("end_date").str.to_datetime(format="%Y-%m-%dT%H:%M:%S%z").alias("end_datetime"),
            pl.col("driver").struct.field("data").alias("driver_info"),
            pl.col("driver_price").struct.field("data").alias("driver_price_info"),
            pl.col("space_owner_earnings").struct.field("data").alias("earnings_info"),
        ).with_columns(
            [((pl.col("end_datetime") - pl.col("start_datetime")).dt.total_seconds() / 3600).alias("duration_hours")]
        )

        active_bookings_df = working_df.filter(pl.col("status") != "cancelled")

        driver_details = (
            working_df.select("driver_id", "driver_info")
            .unnest("driver_info")
            .unique("driver_id")
            .select(["driver_id", "name"])
        )

        basic_counts = working_df.group_by("driver_id").agg(
            [pl.len().alias("num_bookings"), (pl.col("status") == "cancelled").sum().alias("num_cancelled")]
        )

        active_aggregates = active_bookings_df.group_by("driver_id").agg(
            [
                pl.col("duration_hours").max().alias("longest_stay"),
                pl.col("duration_hours").mean().alias("average_stay"),
                pl.col("duration_hours").min().alias("shortest_stay"),
                pl.col("start_datetime").min().alias("first_booking"),
                pl.col("start_datetime").max().alias("last_booking"),
                pl.col("driver_price_info").alias("all_driver_prices"),
                pl.col("earnings_info").alias("all_earnings"),
            ]
        )

        price_totals = active_aggregates.select(
            "driver_id",
            pl.col("all_driver_prices")
            .list.eval(pl.element().struct.field("value"))
            .list.sum()
            .alias("total_paid_by_driver"),
            pl.col("all_earnings").list.eval(pl.element().struct.field("value")).list.sum().alias("total_earnings"),
        )

        result = (
            driver_details.join(basic_counts, on="driver_id")
            .join(active_aggregates.drop(["all_driver_prices", "all_earnings"]), on="driver_id", how="left")
            .join(price_totals, on="driver_id", how="left")
        )

        return result

    def rolling_occupancy(self, window: int = 7) -> pl.DataFrame:
        """
        Compute the rolling occupancy rate over a specified window of days.

        Args:
            window (int): The number of days for the rolling window. Default is 7.

        Returns:
            pl.DataFrame: A DataFrame with columns 'date' and 'rolling_occupancy'.
        """
        # Filter out cancelled bookings
        active_bookings = self.data.filter(pl.col("status") != "cancelled")

        # Convert date strings to datetime and normalize to UTC
        working_df = active_bookings.select(
            [
                pl.col("start_date")
                .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%z")
                .dt.convert_time_zone("UTC")
                .alias("start_dt"),
                pl.col("end_date")
                .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%z")
                .dt.convert_time_zone("UTC")
                .alias("end_dt"),
                "listing_id",
            ]
        )

        # Get the overall date range
        date_range = working_df.select(
            [pl.col("start_dt").min().alias("min_date"), pl.col("end_dt").max().alias("max_date")]
        ).row(0)

        min_date = date_range[0].date()
        max_date = date_range[1].date()

        # Create a date range for analysis
        date_series = pl.date_range(min_date, max_date, interval="1d", eager=True)

        # Create DataFrame with all dates
        all_dates_df = pl.DataFrame({"date": date_series})

        # For each date, calculate how many hours were occupied
        daily_occupancy = []

        for single_date in date_series:
            # Convert date to start and end of day in UTC datetime
            day_start = pl.datetime(single_date.year, single_date.month, single_date.day, time_zone="UTC")
            day_end = day_start + pl.duration(days=1)

            # Find bookings that overlap with this day
            day_bookings = working_df.filter((pl.col("start_dt") < day_end) & (pl.col("end_dt") > day_start))

            if day_bookings.shape[0] == 0:
                occupied_hours = 0.0
            else:
                # Calculate overlap hours for each booking on this day
                overlap_df = day_bookings.with_columns(
                    [
                        pl.max_horizontal([pl.col("start_dt"), day_start]).alias("overlap_start"),
                        pl.min_horizontal([pl.col("end_dt"), day_end]).alias("overlap_end"),
                    ]
                ).with_columns(
                    [
                        ((pl.col("overlap_end") - pl.col("overlap_start")).dt.total_seconds() / 3600).alias(
                            "overlap_hours"
                        )
                    ]
                )

                # Sum up all overlap hours (handling potential overlapping bookings)
                total_overlap_hours = overlap_df.select("overlap_hours").sum().item()
                occupied_hours = min(total_overlap_hours, 24.0)  # Cap at 24 hours per day

            # Calculate occupancy rate for this day (percentage of day occupied)
            occupancy_rate = occupied_hours / 24.0
            daily_occupancy.append({"date": single_date, "daily_occupancy": occupancy_rate})

        # Convert to DataFrame
        daily_df = pl.DataFrame(daily_occupancy)

        # Calculate rolling average
        result_df = daily_df.with_columns(
            [pl.col("daily_occupancy").rolling_mean(window_size=window, center=False).alias("rolling_occupancy")]
        ).drop_nulls()

        return result_df.select(["date", "rolling_occupancy"])


def parse_bookings_json(json_data: dict) -> pl.DataFrame:
    """
    Parse the bookings JSON data into a Polars DataFrame with the defined schema.

    Args:
        json_data (dict): The JSON data as a dictionary.

    Returns:
        pl.DataFrame: A Polars DataFrame containing the bookings data.
    """
    root_df = pl.DataFrame([json_data], strict=False)
    bookings_df = root_df.select("items").explode("items")
    bookings_df = bookings_df.with_columns([pl.col("items").struct.field("*")]).drop("items")

    return bookings_df


if __name__ == "__main__":
    import json

    bookings = BookingsData.from_json(json.load(open("justpark-bookings-2025-09-10.json")))
    print("Bookings data loaded successfully!")
    print(f"Total bookings: {bookings.data.shape[0]}")
    print("\nFirst 3 bookings:")
    print(bookings.data.head(3))

    print("\n" + "=" * 60)
    print("DRIVER STATISTICS")
    print("=" * 60)

    stats = bookings.driver_stats()
    print(f"Total unique drivers: {stats.shape[0]}")
    print("\nTop 5 drivers by earnings:")
    top_drivers = (
        stats.select(["name", "num_bookings", "total_earnings"]).sort("total_earnings", descending=True).head(5)
    )
    print(top_drivers)

    print("\n" + "=" * 60)
    print("ROLLING OCCUPANCY")
    print("=" * 60)

    occupancy = bookings.rolling_occupancy(window=7)
    print(f"Rolling occupancy data points: {occupancy.shape[0]}")
    print("\nFirst 5 days:")
    print(occupancy.head(5))
    print("\nLast 5 days:")
    print(occupancy.tail(5))

    import polars as pl

    occupancy_stats = occupancy.select(
        [
            pl.col("rolling_occupancy").min().alias("min_occupancy"),
            pl.col("rolling_occupancy").max().alias("max_occupancy"),
            pl.col("rolling_occupancy").mean().alias("avg_occupancy"),
        ]
    )
    print("\nOccupancy statistics:")
    print(occupancy_stats)

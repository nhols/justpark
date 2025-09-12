from typing import Self

import polars as pl

from src.bookings.models import BookingResponse
from src.bookings.schemas import BOOKINGS, DRIVER, VEHICLE

MINS_IN_DAY = 24 * 60


class Bookings:
    def __init__(self, data: BookingResponse) -> None:
        self.data = data
        self.bookings = pl.DataFrame([b.to_record() for b in data.items], schema=BOOKINGS)
        self.drivers = pl.DataFrame([b.driver.data.model_dump() for b in data.items], schema=DRIVER).unique(
            subset=["id"]
        )
        self.vehicles = pl.DataFrame([b.vehicle.data.model_dump() for b in data.items], schema=VEHICLE).unique(
            subset=["id"]
        )

    @property
    def cancelled_bookings(self) -> pl.DataFrame:
        return self.bookings.filter(pl.col("status") == "cancelled")

    @property
    def active_bookings(self) -> pl.DataFrame:
        return self.bookings.filter(pl.col("status") != "cancelled")

    @classmethod
    def from_json(cls, json_data: dict) -> Self:
        data = BookingResponse.model_validate(json_data)
        return cls(data)

    def driver_stats(self) -> pl.DataFrame:
        cancelled_count = self.cancelled_bookings.group_by("driver_id").agg(pl.count("id").alias("num_cancelled"))

        active_with_duration = self.active_bookings.with_columns(
            [((pl.col("end_date") - pl.col("start_date")).dt.total_seconds() / 3600).alias("duration_hours")]
        )

        return (
            active_with_duration.group_by("driver_id")
            .agg(
                [
                    pl.count("id").alias("total_bookings"),
                    pl.sum("earnings_value").alias("total_earnings"),
                    pl.sum("paid_value").alias("total_paid"),
                    pl.min("start_date").alias("first_booking"),
                    pl.max("start_date").alias("last_booking"),
                    pl.max("duration_hours").alias("longest_duration_hours"),
                    pl.min("duration_hours").alias("shortest_duration_hours"),
                    pl.mean("duration_hours").alias("average_duration_hours"),
                ]
            )
            .join(cancelled_count, on="driver_id", how="full", coalesce=True)
            .join(self.drivers, left_on="driver_id", right_on="id", how="left")
            .with_columns(
                [
                    pl.col("num_cancelled").fill_null(0),
                    pl.col("total_bookings").fill_null(0),
                    pl.col("total_earnings").fill_null(0.0),
                    pl.col("total_paid").fill_null(0.0),
                    pl.col("longest_duration_hours").fill_null(0.0),
                    pl.col("shortest_duration_hours").fill_null(0.0),
                    pl.col("average_duration_hours").fill_null(0.0),
                ]
            )
            .select(
                [
                    "driver_id",
                    "name",
                    "total_bookings",
                    "num_cancelled",
                    "total_earnings",
                    "total_paid",
                    "longest_duration_hours",
                    "shortest_duration_hours",
                    "average_duration_hours",
                ]
            )
            .sort("total_earnings", descending=True)
        )

    def _occupied_mins_by_date(self, filter: pl.Expr | None = None) -> pl.DataFrame:
        if filter is not None:
            df = self.active_bookings.filter(filter)
        else:
            df = self.active_bookings
        df = df.select(
            pl.col("id"),
            pl.col("start_date"),
            pl.col("end_date"),
        )
        return (
            df.group_by("id")
            .agg(pl.date_range(pl.col("start_date").dt.date().min(), pl.col("end_date").dt.date().max()).alias("date"))
            .explode("date")
            .join(df, on="id")
            .with_columns(
                (pl.col("date") == pl.col("start_date").dt.date()).alias("on_start"),
                (pl.col("date") == pl.col("end_date").dt.date()).alias("on_end"),
            )
            .with_columns(
                (pl.col("on_start") & (pl.col("on_end"))).alias("same_day"),
                pl.lit(60, pl.Int8).alias("60"),
            )
            .with_columns(
                pl.when(pl.col("same_day"))
                .then((pl.col("end_date") - pl.col("start_date")).dt.total_minutes())
                .when(pl.col("on_start"))
                .then(MINS_IN_DAY - mins_into_day(pl.col("start_date")))
                .when(pl.col("on_end"))
                .then(mins_into_day(pl.col("end_date")))
                .otherwise(MINS_IN_DAY)
                .alias("occupied_minutes"),
            )
            .group_by("date")
            .agg(pl.sum("occupied_minutes").alias("occupied_minutes"))
        )

    def rolling_occupancy(self, window_days: int = 30, filter: pl.Expr | None = None) -> pl.DataFrame:
        df_occupied = self._occupied_mins_by_date(filter)

        min_date, max_date = df_occupied.select(
            pl.col("date").min().alias("min"),
            pl.col("date").max().alias("max"),
        ).row(0)

        return (
            pl.date_range(min_date, max_date, interval="1d", eager=True)
            .alias("date")
            .to_frame()
            .join(df_occupied, on="date", how="left")
            .with_columns((pl.col("occupied_minutes").fill_null(0) / MINS_IN_DAY).alias("occupancy"))
            .sort("date")
            .select(
                pl.col("date"),
                pl.col("occupancy").rolling_mean(window_size=window_days, center=False).alias(f"{window_days}d"),
            )
        )


def mins_into_day(expr: pl.Expr) -> pl.Expr:
    return expr.dt.hour().cast(pl.Int64).mul(60) + expr.dt.minute().cast(pl.Int64)

import datetime
from typing import Any

import polars as pl
import requests
import streamlit as st
from humanize import naturaltime

from src.bookings import Bookings
from src.ui.occupancy import daily_occupancy_plot


def get_driver_stats_column_config(df):
    config: dict[str, str | Any] = {
        "driver_id": "Driver ID",
        "name": "Driver Name",
    }

    # Define numeric columns with their display info
    numeric_columns = {
        "total_bookings": {
            "label": "Bookings",
            "help": "Total number of bookings made by the driver",
            "format": "%d",
            "total_earnings": {
                "label": "Earnings",
                "help": "Total earnings from the driver from all bookings",
                "format": "£%.2f",
            },
        },
        "total_earnings": {
            "label": "Earnings",
            "help": "Total amount earned from the driver from all bookings",
            "format": "£%.2f",
        },
        "total_paid": {
            "label": "Paid",
            "help": "Total amount paid by the driver for all bookings",
            "format": "£%.2f",
        },
        "longest_duration_hours": {
            "label": "Longest Stay (hours)",
            "help": "Duration of the longest booking in hours",
            "format": "%.1f",
        },
        "average_duration_hours": {
            "label": "Average Stay (hours)",
            "help": "Average duration of bookings in hours",
            "format": "%.1f",
        },
        "shortest_duration_hours": {
            "label": "Shortest Stay (hours)",
            "help": "Duration of the shortest booking in hours",
            "format": "%.1f",
        },
        "num_cancelled": {
            "label": "Cancelled",
            "help": "Number of bookings cancelled by the driver",
            "format": "%d",
        },
    }

    for col_name, col_info in numeric_columns.items():
        if col_name in df.columns:
            col_data = df[col_name].drop_nulls()
            if len(col_data) > 0:
                max_val = float(col_data.max())
                # Add some padding to max value for better visualization
                max_val = max_val * 1.1

                config[col_name] = st.column_config.ProgressColumn(
                    col_info["label"], help=col_info["help"], min_value=0, max_value=max_val, format=col_info["format"]
                )

    return config


def fmt_bg(v: str) -> str:
    return f":blue-background[{v}]"


def driver_stats(bookings: Bookings) -> int | None:
    stats = bookings.driver_stats()
    col_configs = get_driver_stats_column_config(stats)
    st.dataframe(
        stats.sort("total_earnings", descending=True),
        width="stretch",
        column_order=col_configs.keys(),
        column_config=col_configs,
    )


def format_info(k: str, v: Any) -> dict[str, Any]:
    key = f"{k.replace('_', ' ').title()}"
    if isinstance(v, datetime.datetime):
        v = naturaltime(datetime.datetime.now(tz=v.tzinfo) - v)
    return {"Info": key, "Value": v}


def driver_spotlight(bookings: Bookings):
    id_name = {id: name for id, name in bookings.drivers.select(pl.col("id"), pl.col("name")).iter_rows()}
    driver_id = st.selectbox("Select a driver", options=id_name, format_func=lambda id: id_name[id], index=None)
    if not driver_id:
        st.info("Select a driver to see their info")
        return
    driver_id_filter = pl.col("driver_id") == pl.lit(driver_id)
    info = bookings.drivers.filter(pl.col("id") == pl.lit(driver_id)).select(pl.exclude("id")).to_dicts()[0]
    df_b = bookings.bookings.filter(driver_id_filter).sort("start_date", descending=True)
    df_v = bookings.vehicles.join(df_b, left_on="id", right_on="vehicle_id", how="semi")

    agg_stats = (
        df_b.group_by("driver_id")
        .agg(
            [
                pl.col("start_date").min().alias("first_booking"),
                pl.col("start_date").max().alias("last_booking"),
                pl.col("id").count().alias("num_bookings"),
                (pl.col("status") == "cancelled").sum().alias("num_cancelled"),
                pl.col("earnings_value").sum().alias("total_earnings"),
                pl.col("paid_value").filter(pl.col("status") != "cancelled").sum().alias("total_paid_by_driver"),
            ]
        )
        .to_dicts()[0]
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Total earnings", f"£{agg_stats.pop('total_earnings'):.2f}", border=True)
    col2.metric("Total bookings", f"{agg_stats.pop('num_bookings')}", border=True)
    col3.metric("Total cancelled", f"{agg_stats.pop('num_cancelled')}", border=True)

    st.image(info.pop("profile_photo"), width=100)
    st.dataframe([format_info(key, value) for key, value in (info | agg_stats).items()], hide_index=True)

    df = bookings.rolling_occupancy(window_days=1, filter=driver_id_filter).rename({"1d": "daily_occupancy"})
    daily_occupancy_plot(df)

    st.subheader("Bookings")
    st.dataframe(df_b, width=True)
    st.subheader("Vehicles")
    st.dataframe(df_v, width=True)


def driver(bookings: Bookings):
    driver_stats(bookings)
    st.divider()
    driver_spotlight(bookings)

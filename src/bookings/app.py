import json
from typing import Any

import altair as alt
import polars as pl
import streamlit as st

from src.bookings.data import BookingsData

st.set_page_config(page_title="JustPark Bookings Analysis", layout="wide")
bookings = BookingsData.from_json(json.load(open("justpark-bookings-2025-09-10.json")))


def get_driver_stats_column_config(df):
    config: dict[str, str | Any] = {
        "driver_id": "Driver ID",
        "name": "Driver Name",
    }

    # Define numeric columns with their display info
    numeric_columns = {
        "num_bookings": {
            "label": "Number of Bookings",
            "help": "Total number of bookings made by the driver",
            "format": "%d",
        },
        "num_cancelled": {
            "label": "Number Cancelled",
            "help": "Number of bookings cancelled by the driver",
            "format": "%d",
        },
        "total_earnings": {
            "label": "Total Earnings (£)",
            "help": "Total earnings from all bookings",
            "format": "£%.2f",
        },
        "total_paid_by_driver": {
            "label": "Total Paid by Driver (£)",
            "help": "Total amount paid by the driver for all bookings",
            "format": "£%.2f",
        },
        "longest_stay": {
            "label": "Longest Stay (hours)",
            "help": "Duration of the longest booking in hours",
            "format": "%.1f",
        },
        "average_stay": {
            "label": "Average Stay (hours)",
            "help": "Average duration of bookings in hours",
            "format": "%.2f",
        },
        "shortest_stay": {
            "label": "Shortest Stay (hours)",
            "help": "Duration of the shortest booking in hours",
            "format": "%.2f",
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

    if "first_booking" in df.columns:
        config["first_booking"] = st.column_config.DatetimeColumn(
            "First Booking", help="Date and time of the first booking made by the driver", format="DD/MM/YYYY HH:mm"
        )

    if "last_booking" in df.columns:
        config["last_booking"] = st.column_config.DatetimeColumn(
            "Last Booking",
            help="Date and time of the most recent booking made by the driver",
            format="DD/MM/YYYY HH:mm",
        )

    return config


def get_driver_details_column_config():
    config: dict[str, str | Any] = {
        "profile_photo": st.column_config.ImageColumn("Profile Photo", help="Driver's profile photo"),
        "id": "Driver ID",
        "name": "Name",
        "first_name": "First Name",
        "last_name": "Last Name",
        "is_managed": st.column_config.CheckboxColumn(
            "Managed Account", help="Whether this is a managed driver account"
        ),
        "registration_date": st.column_config.DateColumn("Registration Date", help="Date when the driver registered"),
        "email": "Email Address",
        "email_verified": st.column_config.CheckboxColumn(
            "Email Verified", help="Whether the email address has been verified"
        ),
        "phone_number": "Phone Number",
        "phone_number_verified": st.column_config.TextColumn(
            "Phone Verified", help="Whether the phone number has been verified"
        ),
        "company_name": "Company Name",
    }
    return config


st.dataframe(bookings.data)


driver_details_df = bookings.driver_details()
driver_details_cc = get_driver_details_column_config()
st.dataframe(
    driver_details_df,
    use_container_width=True,
    column_order=driver_details_cc.keys(),
    column_config=driver_details_cc,
)


driver_stats_df = bookings.driver_stats()
driver_stats_cc = get_driver_stats_column_config(driver_stats_df)
st.dataframe(
    driver_stats_df,
    use_container_width=True,
    column_order=driver_stats_cc.keys(),
    column_config=driver_stats_cc,
)

window = st.segmented_control("Rolling Occupancy window (days)", [7, 14, 30, 90], default=7, selection_mode="multi")
window = window or [7]
df = pl.DataFrame(schema={"date": pl.Date})
col_names = []

for w in window:
    col_name = f"{w}d"
    col_names.append(col_name)
    df = df.join(
        bookings.rolling_occupancy(window=w).rename({"rolling_occupancy": col_name}),
        on="date",
        how="full",
        coalesce=True,
    )
st.line_chart(
    df,
    use_container_width=True,
    y=col_names,
    x="date",
    y_label="Rolling Occupancy",
    x_label="Date",
)


alt_chart = (
    alt.Chart(bookings.rolling_occupancy(window=1).to_pandas())
    .mark_line(interpolate="step-after")
    .encode(
        x=alt.X("date:T", axis=alt.Axis(title="Date")),
        y=alt.Y("rolling_occupancy", type="quantitative", axis=alt.Axis(title="Daily Occupancy")),
        tooltip=["date:T", "rolling_occupancy"],
    )
    .properties(width=600, height=400)
)
st.altair_chart(alt_chart, use_container_width=True)

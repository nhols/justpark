import datetime as dt
from typing import cast

import altair as alt
import polars as pl
import streamlit as st

from src.bookings import Bookings


def occupancy(bookings: Bookings):
    rolling_occupancy(bookings)
    daily_occupancy(bookings)


def rolling_occupancy(bookings: Bookings):
    st.subheader("Rolling")
    signal = st.segmented_control("Occupancy signal", ["By minute", "By day"], default="By minute")
    occupancy_signal = "days" if signal == "By day" else "minutes"
    window = cast(
        list[int],
        st.segmented_control("Rolling window (days)", [7, 14, 30, 90], default=[7, 30], selection_mode="multi"),
    )
    if not window:
        st.info("Select one or more window sizes to display rolling occupancy")
        return

    df = pl.DataFrame(schema={"date": pl.Date})
    col_names = []

    for w in window:
        col_name = f"{w}d"
        col_names.append(col_name)
        df = df.join(
            bookings.rolling_occupancy(window_days=w, signal=occupancy_signal),
            on="date",
            how="full",
            coalesce=True,
        )
    chart_df = df.unpivot(index="date", on=col_names, variable_name="window", value_name="occupancy")
    y_title = "Rolling Occupancy" if occupancy_signal == "minutes" else "Rolling Occupied Days"
    line_chart = (
        alt.Chart(chart_df)
        .mark_line(clip=True)
        .encode(
            x=alt.X("date:T", axis=alt.Axis(title="Date")),
            y=alt.Y("occupancy:Q", axis=alt.Axis(title=y_title, format="%"), scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("window:N", title="Window", legend=alt.Legend(orient="bottom")),
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("window:N", title="Window"),
                alt.Tooltip("occupancy:Q", title=y_title, format=".1%"),
            ],
        )
    )
    alt_chart = line_chart + today_rule()
    st.altair_chart(alt_chart, use_container_width=True)


def daily_occupancy(bookings: Bookings):
    st.subheader("Daily")
    df = bookings.rolling_occupancy(window_days=1).rename({"1d": "daily_occupancy"})
    daily_occupancy_plot(df)


def daily_occupancy_plot(df: pl.DataFrame):
    line_chart = (
        alt.Chart(df)
        .mark_line(interpolate="step-after", clip=True)
        .encode(
            x=alt.X("date:T", axis=alt.Axis(title="Date")),
            y=alt.Y(
                "daily_occupancy",
                type="quantitative",
                axis=alt.Axis(title="Daily Occupancy", format="%"),
                scale=alt.Scale(domain=[0, 1]),
            ),
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("daily_occupancy:Q", title="Daily Occupancy", format=".1%"),
            ],
        )
    )
    alt_chart = line_chart + today_rule()
    st.altair_chart(alt_chart, use_container_width=True)


def today_rule():
    return (
        alt.Chart(pl.DataFrame({"date": [dt.date.today()], "label": ["Today"]}))
        .mark_rule(color="orange", opacity=0.45, strokeWidth=1)
        .encode(
            x=alt.X("date:T"),
            tooltip=[
                alt.Tooltip("label:N", title=""),
                alt.Tooltip("date:T", title="Date"),
            ],
        )
    )


if __name__ == "__main__":
    import json

    st.set_page_config(page_title="JustPark Bookings Analysis", layout="wide")

    with open("justpark-bookings-2025-09-10.json", "r") as f:
        data = json.load(f)

    bookings = Bookings.from_json(data)
    occupancy(bookings)

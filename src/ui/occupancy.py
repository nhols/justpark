import altair as alt
import polars as pl
import streamlit as st

from src.bookings import Bookings


def occupancy(bookings: Bookings):
    rolling_occupancy(bookings)
    daily_occupancy(bookings)


def rolling_occupancy(bookings: Bookings):
    st.subheader("Rolling")
    window = st.segmented_control("Rolling window (days)", [7, 14, 30, 90], default=[7, 30], selection_mode="multi")
    if not window:
        st.info("Select one or more window sizes to display rolling occupancy")
        return

    df = pl.DataFrame(schema={"date": pl.Date})
    col_names = []

    for w in window:
        col_name = f"{w}d"
        col_names.append(col_name)
        df = df.join(
            bookings.rolling_occupancy(window_days=w),
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


def daily_occupancy(bookings: Bookings):
    st.subheader("Daily")
    df = bookings.rolling_occupancy(window_days=1).rename({"1d": "daily_occupancy"})
    daily_occupancy_plot(df)


def daily_occupancy_plot(df: pl.DataFrame):
    alt_chart = (
        alt.Chart(df)
        .mark_line(interpolate="step-after")
        .encode(
            x=alt.X("date:T", axis=alt.Axis(title="Date")),
            y=alt.Y("daily_occupancy", type="quantitative", axis=alt.Axis(title="Daily Occupancy")),
            tooltip=["date:T", "daily_occupancy"],
        )
    )
    st.altair_chart(alt_chart, use_container_width=True)


if __name__ == "__main__":
    import json

    st.set_page_config(page_title="JustPark Bookings Analysis", layout="wide")

    with open("justpark-bookings-2025-09-10.json", "r") as f:
        data = json.load(f)

    bookings = Bookings.from_json(data)
    occupancy(bookings)

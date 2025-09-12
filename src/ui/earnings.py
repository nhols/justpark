from datetime import date

import polars as pl
import streamlit as st

SCHEAMA = pl.Schema(
    {
        "date": pl.Date,
        "earnings": pl.Float64,
    }
)

PERIODS = {
    "Day": "1d",
    "Week": "1w",
    "Month": "1mo",
    "Quarter": "1q",
    "Year": "1y",
}


def this_tax_year_start() -> date:
    today = date.today()
    start_year = today.year if today >= date(today.year, 4, 6) else today.year - 1
    return date(start_year, 4, 6)


def earnings_metrics(df: pl.DataFrame) -> None:
    total = df.select(pl.col("earnings").sum()).item()
    this_tax_year = df.filter(pl.col("date") >= pl.lit(this_tax_year_start())).select(pl.col("earnings").sum()).item()
    num_bookings = df.select(pl.count()).item()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total earnings", f"£{total:.2f}", help="Total earnings from all bookings", border=True)
    col2.metric(
        "Earnings this tax year", f"£{this_tax_year:.2f}", help="Earnings from 6th April this year", border=True
    )
    col3.metric("Total bookings", f"{num_bookings}", help="Total number of bookings", border=True)


def earnings_by_period(df: pl.DataFrame) -> None:
    period = st.segmented_control("Frequency", list(PERIODS.keys()), default="Week")
    if not period:
        st.info("Select a frequency to display earnings")
        return

    df = (
        df.with_columns(pl.col("date").dt.truncate(PERIODS[period]).alias("date"))
        .group_by("date")
        .agg(pl.col("earnings").sum())
        .sort("date", descending=True)
    )
    st.bar_chart(df, x="date", y="earnings", use_container_width=True)
    st.dataframe(
        df,
        hide_index=True,
        column_config={
            "date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
            "earnings": st.column_config.ProgressColumn(
                "Earnings", format="£ %.2f", min_value=0, max_value=df.select(pl.col("earnings").max()).item()
            ),
        },
    )


def earnings(df: pl.DataFrame) -> None:
    if df.is_empty():
        st.info("No earnings data available")
        return

    earnings_metrics(df)
    st.divider()
    earnings_by_period(df)

import datetime

import altair as alt
import humanize
import plotly.express as px
import polars as pl
import streamlit as st

from src.bookings import Bookings


def booked_plot(df: pl.DataFrame):
    df_ = df.to_pandas()
    df_["y"] = 1
    fig = px.timeline(
        df_,
        x_start="start_date",
        x_end="end_date",
        y="y",
        title="Bookings Timeline",
        hover_data={"y": False},
        opacity=0.6,
    )
    fig.update_xaxes(rangeslider_visible=True)
    fig.update_yaxes(visible=False)
    fig.add_vline(
        x=datetime.datetime.now().isoformat(), line_color=st.get_option("theme.primaryColor"), line_dash="dot"
    )

    st.plotly_chart(fig, use_container_width=True)


def booked_plot_(df: pl.DataFrame):
    df = (
        df.unpivot(on=["start_date", "end_date"], variable_name="event", value_name="date")
        .with_columns(pl.when(pl.col("event") == "start_date").then(1).otherwise(0).alias("live"))
        .sort(["date", "live"], descending=[False, True])
    )

    alt_chart = (
        alt.Chart(df)
        .mark_line(interpolate="step-after", strokeWidth=4, cornerRadius=5)
        .encode(
            x=alt.X("date:T", axis=alt.Axis(title="Time")),
            y=alt.Y("live", type="quantitative", axis=alt.Axis(title="Booked")),
            tooltip=["date:T", "live"],
        )
    )
    st.altair_chart(alt_chart, use_container_width=True)


def live_view(bookings: Bookings):
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    next_week = today + datetime.timedelta(days=7)
    dates = st.date_input("Select date range", (yesterday, next_week), help="Filter bookings by date range")
    if not dates or len(dates) != 2:
        st.info("Select a date range in which to filter bookings")
        return

    date_from, date_to = dates
    filtered_bookings = bookings.active_bookings.filter(
        pl.col("start_date").dt.date().le(date_to) & pl.col("end_date").dt.date().ge(date_from)
    )
    if filtered_bookings.is_empty():
        st.info("No bookings found in the selected date range")
        return
    booked_plot(filtered_bookings)
    now = datetime.datetime.now(tz=filtered_bookings.select(pl.col("start_date")).row(0)[0].tzinfo)

    df = (
        (
            filtered_bookings.join(
                bookings.drivers.select(["id", "name", "phone_number", "email"]),
                left_on="driver_id",
                right_on="id",
                suffix="_driver",
            )
            .join(
                bookings.vehicles.select(["id", "make", "model", "registration", "colour"]),
                left_on="vehicle_id",
                right_on="id",
                suffix="_vehicle",
            )
            .select(
                [
                    "start_date",
                    "end_date",
                    "name",
                    "phone_number",
                    "email",
                    "make",
                    "model",
                    "registration",
                    "colour",
                    "earnings_value",
                    "paid_value",
                ]
            )
        )
        .with_columns(
            pl.col("start_date").map_elements(humanize.naturaltime).alias("Start"),
            (pl.col("end_date") - pl.col("start_date"))
            .map_elements(lambda x: humanize.precisedelta(x, minimum_unit="minutes"))
            .alias("Duration"),
            pl.when(pl.col("end_date") < now)
            .then(pl.lit("✅ Completed"))
            .when(pl.col("start_date") < now)
            .then(pl.lit("⏳ In Progress"))
            .otherwise(pl.lit("🔜 Upcoming"))
            .alias("Status"),
        )
        .sort("start_date")
    )
    dt_fmt = "ddd DD MMM, HH:mm"
    cfg = {
        "Status": st.column_config.TextColumn("Status"),
        "Start": st.column_config.TextColumn("Start"),
        "Duration": st.column_config.TextColumn("Duration"),
        "start_date": st.column_config.DatetimeColumn("Start date", format=dt_fmt),
        "end_date": st.column_config.DatetimeColumn("End date", format=dt_fmt),
        "name": st.column_config.TextColumn("Driver"),
        "phone_number": st.column_config.TextColumn("Phone"),
        "email": st.column_config.TextColumn("Email"),
        "make": st.column_config.TextColumn("Make"),
        "model": st.column_config.TextColumn("Model"),
        "registration": st.column_config.TextColumn("Reg"),
        "colour": st.column_config.TextColumn("Colour"),
        "earnings_value": st.column_config.ProgressColumn(
            "Earnings", format="£ %.2f", min_value=0, max_value=df.select(pl.col("earnings_value").max()).item()
        ),
        "paid_value": st.column_config.ProgressColumn(
            "Paid", format="£ %.2f", min_value=0, max_value=df.select(pl.col("paid_value").max()).item()
        ),
    }
    st.dataframe(
        df,
        column_config=cfg,
        column_order=cfg.keys(),
        hide_index=True,
        use_container_width=True,
    )

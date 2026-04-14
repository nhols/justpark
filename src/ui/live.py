import datetime

import altair as alt
import humanize
import polars as pl
import streamlit as st
from streamlit_calendar import calendar

from src.bookings import Bookings


def booked_plot(df: pl.DataFrame):
    event_colour = st.get_option("theme.primaryColor")

    events = df.select(
        [
            pl.col("id").cast(pl.String).alias("id"),
            pl.col("registration").fill_null("Unknown reg").alias("title"),
            pl.col("start_date").dt.strftime("%Y-%m-%dT%H:%M:%S").alias("start"),
            pl.col("end_date").dt.strftime("%Y-%m-%dT%H:%M:%S").alias("end"),
        ]
    ).to_dicts()

    options = {
        "initialView": "timeGridWeek",
        "firstDay": 1,
        "views": {
            "timeGridDay": {"slotDuration": "01:00:00"},
            "timeGridWeek": {"buttonText": "week", "slotDuration": "01:00:00"},
            "timelineWeek": {"buttonText": "timeline", "slotMinWidth": 140},
        },
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "timeGridDay,timeGridWeek,timelineWeek,dayGridMonth",
        },
        "slotMinTime": "00:00:00",
        "slotMaxTime": "24:00:00",
        "nowIndicator": True,
        "height": 740,
        "editable": False,
        "slotMinWidth": 120,
        "eventTimeFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False},
    }
    custom_css = f"""
    .fc-event {{
        border: 0;
        background-color: {event_colour};
    }}
    """
    return calendar(
        events=events,
        options=options,
        custom_css=custom_css,
        callbacks=["dateClick", "eventClick", "eventsSet"],
        key=f"bookings-calendar-{options['height']}",
    )


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
    live_bookings = (
        bookings.active_bookings.join(
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
        .sort("start_date")
    )
    if live_bookings.is_empty():
        st.info("No active bookings found")
        return

    calendar_state = booked_plot(live_bookings)
    selection_key = "live_calendar_selection"
    view_key = "live_calendar_view"

    if calendar_state:
        callback = calendar_state.get("callback")
        if callback == "eventClick":
            event = calendar_state["eventClick"]["event"]
            st.session_state[selection_key] = {"type": "event", "booking_id": int(event["id"])}
            st.session_state[view_key] = calendar_state["eventClick"]["view"]
        elif callback == "dateClick":
            clicked_at = datetime.datetime.fromisoformat(calendar_state["dateClick"]["date"])
            st.session_state[selection_key] = {"type": "date", "date": clicked_at.date().isoformat()}
            st.session_state[view_key] = calendar_state["dateClick"]["view"]
        elif callback == "eventsSet":
            st.session_state[selection_key] = None
            st.session_state[view_key] = calendar_state["eventsSet"].get("view")

    selected = st.session_state.get(selection_key)
    current_view = st.session_state.get(view_key)

    table_bookings = live_bookings
    table_label = "Showing bookings in the current calendar view"

    if selected and selected["type"] == "event":
        table_bookings = live_bookings.filter(pl.col("id") == selected["booking_id"])
        table_label = "Showing the clicked booking"
    elif selected and selected["type"] == "date":
        selected_date = datetime.date.fromisoformat(selected["date"])
        table_bookings = live_bookings.filter(
            pl.col("start_date").dt.date().le(selected_date) & pl.col("end_date").dt.date().ge(selected_date)
        )
        table_label = f"Showing bookings for {selected_date:%a %d %b %Y}"
    elif current_view:
        view_start = datetime.datetime.fromisoformat(current_view["activeStart"]).date()
        view_end = (datetime.datetime.fromisoformat(current_view["activeEnd"]) - datetime.timedelta(days=1)).date()
        table_bookings = live_bookings.filter(
            pl.col("start_date").dt.date().le(view_end) & pl.col("end_date").dt.date().ge(view_start)
        )

    if table_bookings.is_empty():
        st.info("No bookings match the current calendar selection")
        return

    st.caption(table_label)

    now = datetime.datetime.now(tz=table_bookings.select(pl.col("start_date")).row(0)[0].tzinfo)

    df = (
        table_bookings.select(
            [
                "id",
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
        "registration": st.column_config.TextColumn("Reg"),
        "Start": st.column_config.TextColumn("Start"),
        "Duration": st.column_config.TextColumn("Duration"),
        "start_date": st.column_config.DatetimeColumn("Start date", format=dt_fmt),
        "end_date": st.column_config.DatetimeColumn("End date", format=dt_fmt),
        "name": st.column_config.TextColumn("Driver"),
        "phone_number": st.column_config.TextColumn("Phone"),
        "email": st.column_config.TextColumn("Email"),
        "make": st.column_config.TextColumn("Make"),
        "model": st.column_config.TextColumn("Model"),
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

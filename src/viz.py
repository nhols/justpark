from math import e

import altair as alt
import pandas as pd
import streamlit as st

from src.data_utils import PeriodOption, drop_withdrawals


def total_earnings(df: pd.DataFrame) -> None:
    df_copy = df.copy()
    df_copy = drop_withdrawals(df_copy)
    st.metric(label="Total earnings", value=f"£{df_copy['total_amount'].sum():.2f}", border=True)


def total_bookings(df: pd.DataFrame) -> None:
    bookings = {desc.split("#")[-1] for desc in df["Description"].tolist() if "#" in desc}
    st.metric(label="Total bookings", value=len(bookings), border=True)


def earnings_this_tax_year(df: pd.DataFrame) -> None:
    df_copy = df.copy()
    df_copy = drop_withdrawals(df_copy)
    now = pd.Timestamp.now()
    tax_year_start = pd.Timestamp(year=now.year if now.month >= 4 and now.day >= 6 else now.year - 1, month=4, day=6)
    df_copy = df_copy[df_copy["Date"] >= tax_year_start]
    total = df_copy["total_amount"].sum()

    st.metric(
        label=f"Earnings this tax year ({tax_year_start.year}/{tax_year_start.year + 1})",
        value=f"£{total:.2f}",
        border=True,
    )


def earnings_by_period(df: pd.DataFrame, period: PeriodOption) -> None:
    temp_df = df.copy()
    temp_df = drop_withdrawals(temp_df)
    temp_df.set_index("Date", inplace=True)
    temp_df["earnings"] = temp_df["Sub Total"] + temp_df["Tax"]
    resampled = temp_df["earnings"].resample(period.value, label="right").sum().reset_index()
    resampled.rename(columns={"Date": "date_grouped"}, inplace=True)

    chart = (
        alt.Chart(resampled)
        .mark_bar(size=period.width)
        .encode(
            x=alt.X(
                "date_grouped:T",
                title=period.label.title(),
                axis=alt.Axis(format="%d %b %y"),  # Optional
            ),
            y=alt.Y("earnings:Q", title="Earnings"),
        )
        .properties(width="container")
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)
    st.dataframe(
        resampled.sort_values("date_grouped", ascending=False),
        hide_index=True,
        column_config={
            "date_grouped": st.column_config.DateColumn("Date", format=period.format_moment_js),
            "earnings": st.column_config.ProgressColumn(
                "Earnings", format="£ %.2f", min_value=0, max_value=resampled["earnings"].max()
            ),
        },
    )


def cumulative_balance(df: pd.DataFrame) -> None:
    df_copy = df.copy()
    df_copy.sort_values(by="Date", inplace=True)
    df_copy["cumulative_balance"] = df_copy["total_amount"].cumsum()

    chart = (
        alt.Chart(df_copy)
        .mark_line(interpolate="step-after")
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y("cumulative_balance:Q", title="Cumulative balance (£)", axis=alt.Axis(grid=True)),
        )
        .interactive()
    )

    st.altair_chart(chart, use_container_width=True)


def cumulative_earnings(df: pd.DataFrame) -> None:
    df_copy = df.copy()
    df_copy = drop_withdrawals(df_copy)
    df_copy.sort_values(by="Date", inplace=True)
    df_copy["cumulative_earnings"] = df_copy["total_amount"].cumsum()

    chart = (
        alt.Chart(df_copy)
        .mark_line(interpolate="step-after")
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y("cumulative_earnings:Q", title="Cumulative earnings (£)", axis=alt.Axis(grid=True)),
        )
        .interactive()
    )

    st.altair_chart(chart, use_container_width=True)

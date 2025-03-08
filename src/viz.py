import pandas as pd
import streamlit as st

from src.data_utils import PERIOD_OPTIONS, drop_withdrawals


def earnings_by_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    temp_df = df.copy()
    temp_df = drop_withdrawals(temp_df)
    temp_df.set_index("Date", inplace=True)
    temp_df["earnings"] = temp_df["Sub Total"] + temp_df["Tax"]
    resampled = temp_df["earnings"].resample(period, label="left").sum().reset_index()
    resampled.rename(columns={"Date": "date_grouped"}, inplace=True)
    st.bar_chart(
        resampled,
        x="date_grouped",
        y="earnings",
        x_label=PERIOD_OPTIONS[period].title(),
        y_label="Earnings",
    )


def cumulative_balance(df: pd.DataFrame) -> pd.DataFrame:
    df_copy = df.copy()
    df_copy.sort_values(by="Date", inplace=True)
    df_copy["cumulative_balance"] = df_copy["total_amount"].cumsum()
    st.line_chart(df_copy, x="Date", y="cumulative_balance")


def cumulative_earnings(df: pd.DataFrame) -> pd.DataFrame:
    df_copy = df.copy()
    df_copy = drop_withdrawals(df_copy)
    df_copy.sort_values(by="Date", inplace=True)
    df_copy["cumulative_earnings"] = df_copy["total_amount"].cumsum()
    st.line_chart(df_copy, x="Date", y="cumulative_earnings")

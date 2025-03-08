import pandas as pd
import streamlit as st

from data_utils import PERIOD_OPTIONS, clean_data
from src import viz

st.set_page_config(page_title="JustPark", page_icon=":parking:")


def data_dl_ul():
    st.link_button(
        "Download", "https://www.justpark.com/dashboard/billing/transactions/download", icon=":material/download:"
    )
    data = st.file_uploader("Upload", type="csv")
    return data


def app():
    with st.sidebar:
        data = data_dl_ul()

    if not data:
        st.info("Download your latest transactions from JustPark in the sidebar")
        st.stop()

    df = pd.read_csv(data)
    df = clean_data(df)
    start_date, end_date = st.slider(
        "Select a date range",
        min_value=df["Date"].min().date(),
        max_value=df["Date"].max().date(),
        value=(df["Date"].min().date(), df["Date"].max().date()),
    )
    df = df[df["Date"].dt.date.between(start_date, end_date)]

    st.title("Earnings by period")
    period = st.selectbox("Select period", PERIOD_OPTIONS, format_func=lambda x: PERIOD_OPTIONS[x])
    viz.earnings_by_period(df, period)

    st.title("Cumulative earnings")
    viz.cumulative_earnings(df)

    st.title("Cumulative balance")
    viz.cumulative_balance(df)

    st.title("Raw data")
    st.dataframe(df, hide_index=True)


app()

import io

import pandas as pd
import streamlit as st

from src import viz
from src.data_utils import PeriodOption, clean_data, check_earnings_milestone


def data_dl_ul():
    if "data" in st.session_state:
        data = st.session_state["data"]
        st.success(f"`{data.name}` uploaded", icon=":material/check:")
        if st.button(":material/delete:"):
            del st.session_state["data"]
            st.rerun()

    else:
        st.markdown(
            """
            ### Data Import
            1. Download your transactions from JustPark
            2. Upload the CSV file below
            """
        )
        st.divider()

        st.link_button(
            "Download from JustPark",
            "https://www.justpark.com/dashboard/billing/transactions/download",
            icon=":material/download:",
        )
        st.divider()

        data = st.file_uploader("Upload CSV file")
        if data:
            st.session_state["data"] = data
            st.rerun()


def metrics(df: pd.DataFrame):
    col1, col2, col3 = st.columns(3)
    with col1:
        viz.total_earnings(df)
    with col2:
        viz.total_bookings(df)
    with col3:
        viz.earnings_this_tax_year(df)


def main():
    with st.sidebar:
        data_dl_ul()

    if "data" not in st.session_state:
        st.info("Download your latest transactions from JustPark in the sidebar")
        st.stop()

    data = st.session_state["data"].getvalue()
    df = pd.read_csv(io.BytesIO(data))
    df = clean_data(df)
    
    # Check for earnings milestone and trigger confetti
    if check_earnings_milestone(df):
        st.balloons()
        
    start_date, end_date = st.slider(
        "Select a date range",
        min_value=df["Date"].min().date(),
        max_value=df["Date"].max().date(),
        value=(df["Date"].min().date(), df["Date"].max().date()),
    )
    df = df[df["Date"].dt.date.between(start_date, end_date)]

    st.divider()
    metrics(df)

    st.divider()
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Earnings by period",
            "Cumulative earnings",
            "Cumulative balance",
            "Raw data",
        ]
    )
    with tab1:
        st.title("Earnings by period")
        default = PeriodOption.WEEK
        period = st.segmented_control(
            "Frequency",
            options=[option for option in PeriodOption],
            format_func=lambda x: x.label.title(),
            default=default,
        )
        viz.earnings_by_period(df, period or default)
    with tab2:
        st.title("Cumulative earnings")
        viz.cumulative_earnings(df)
    with tab3:
        st.title("Cumulative balance")
        viz.cumulative_balance(df)
    with tab4:
        st.title("Raw data")
        st.dataframe(df, hide_index=True)

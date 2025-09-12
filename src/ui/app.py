import datetime
import json

import boto3
import polars as pl
import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError
from humanize import naturaltime

from src.bookings import Bookings
from src.ui.driver import driver
from src.ui.earnings import earnings
from src.ui.occupancy import occupancy
from src.ui.sql_widget import df_sql_widget


@st.cache_data(ttl="1d")
def load_s3_data():
    s3 = boto3.client(
        "s3",
        aws_access_key_id=st.secrets.aws_access_key_id,
        aws_secret_access_key=st.secrets.aws_secret_access_key,
    )
    try:
        obj = s3.get_object(Bucket=st.secrets.bucket, Key=st.secrets.key)
        st.session_state["data"] = json.load(obj["Body"])
    except (BotoCoreError, ClientError) as e:
        st.error(f"Error loading data from S3: {e}")
        return


def get_data():
    st.session_state.setdefault("data", None)
    load_s3_data()
    if not st.session_state["data"]:
        file = st.file_uploader("JustPark Bookings JSON", type=["json"])
        if file is None:
            st.info("Upload your JustPark bookings JSON file to get started")
            st.stop()
        st.session_state["data"] = json.load(file)
        st.rerun()


def app():
    get_data()
    bookings = Bookings.from_json(st.session_state["data"])

    with st.sidebar:
        st.caption(
            f"_Last updated {naturaltime(datetime.datetime.now(tz=bookings.data.fetchedAt.tzinfo) - bookings.data.fetchedAt)}_"
        )
        if st.button(":material/refresh:", help="Reload data"):
            st.session_state["data"] = None

    tab1, tab2, tab3, tab4 = st.tabs(["Earnings", "Occupancy", "Drivers", "Raw data"])
    with tab1:
        earnings(
            bookings.active_bookings.select(
                pl.col("start_date").alias("date"), pl.col("earnings_value").alias("earnings")
            )
        )
    with tab2:
        occupancy(bookings)
    with tab3:
        driver(bookings)
    with tab4:
        df_sql_widget(bookings)


def main():
    st.session_state.setdefault("authenticated", False)
    if not st.session_state["authenticated"]:
        password = st.text_input("Enter password", type="password")
        if password == st.secrets["password"]:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            if password:
                st.error("Incorrect password")
            return
    else:
        app()

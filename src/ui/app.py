import datetime
import hashlib

import boto3
import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError
from humanize import naturaltime
from pydantic import ValidationError

from src.bookings import Bookings
from src.ui.driver import driver
from src.ui.earnings import earnings
from src.ui.live import live_view
from src.ui.occupancy import occupancy
from src.ui.sql_widget import df_sql_widget

S3Error = (BotoCoreError, ClientError)
S3ValidationError = (BotoCoreError, ClientError, ValidationError)


@st.cache_resource
def s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=st.secrets.aws_access_key_id,
        aws_secret_access_key=st.secrets.aws_secret_access_key,
    )


def check_s3_changed():
    s3 = s3_client()
    try:
        obj = s3.head_object(Bucket=st.secrets.bucket, Key=st.secrets.key)
        if st.session_state["s3_etag"] != obj["ETag"]:
            st.toast("New data available, reload for latest", icon="🔄", duration="infinite")
    except S3Error as e:
        st.error(f"Error checking S3 object: {e}")


@st.cache_data(show_spinner="Refreshing bookings data...", show_time=True)
def load_s3_data() -> tuple[Bookings, str] | None:
    s3 = s3_client()
    try:
        obj = s3.get_object(Bucket=st.secrets.bucket, Key=st.secrets.key)
        bookings = Bookings.from_json(obj["Body"].read())
        return bookings, obj["ETag"]
    except S3ValidationError as e:
        st.error(f"Error loading data from S3: {e}")
        return


def put_s3_data(data: str | bytes | bytearray) -> None:
    s3 = s3_client()
    try:
        _ = Bookings.from_json(data)
        s3.put_object(Bucket=st.secrets.bucket, Key=st.secrets.key, Body=data)
        st.success("Data uploaded successfully")
        refresh_data()
    except S3ValidationError as e:
        st.error(f"Data validation error: {e}")
        return


def get_data():
    st.session_state.setdefault("data", None)
    st.session_state.setdefault("s3_etag", None)

    st.markdown("[![JustPark](https://www.justpark.com/favicon.ico)](https://justpark.com)")
    file = st.file_uploader("Upload new bookings", help="Upload your JustPark bookings JSON file", type=["json"])

    if file is not None:
        put_s3_data(file.getvalue())

    maybe_data = load_s3_data()
    if maybe_data:
        bookings, etag = maybe_data
        st.session_state["data"] = bookings
        st.session_state["s3_etag"] = etag
        check_s3_changed()
        return

    st.info("Upload your JustPark bookings JSON file to get started")


def refresh_data():
    st.session_state["data"] = None
    st.session_state["s3_etag"] = None
    load_s3_data.clear()


def app():
    with st.sidebar:
        get_data()
        bookings = st.session_state["data"]
        if bookings is None:
            st.stop()
        if st.button(":material/refresh:", help="Refresh data"):
            refresh_data()

    st.caption(
        f"_Data last updated {naturaltime(datetime.datetime.now(tz=bookings.data.fetchedAt.tzinfo) - bookings.data.fetchedAt)}_"
    )

    pages = (
        ("Live", live_view),
        ("Earnings", earnings),
        ("Occupancy", occupancy),
        ("Drivers", driver),
        ("Raw data", df_sql_widget),
    )

    tabs = st.tabs([title for title, _ in pages])
    for tab, (_, page) in zip(tabs, pages):
        with tab:
            page(bookings)


def main():
    st.session_state.setdefault("authenticated", False)
    if not st.session_state["authenticated"]:
        password = st.text_input("Enter password", type="password")
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        if hashed_password == st.secrets["password"]:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            if password:
                st.error("Incorrect password")
            return
    else:
        app()

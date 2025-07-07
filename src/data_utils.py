from enum import Enum

import pandas as pd


class PeriodOption(Enum):
    DAY = "D"
    WEEK = "W"
    MONTH = "ME"
    YEAR = "YE"

    @property
    def width(self):
        return {
            PeriodOption.DAY: 5,
            PeriodOption.WEEK: 15,
            PeriodOption.MONTH: 50,
            PeriodOption.YEAR: 200,
        }[self]

    @property
    def label(self):
        return {
            PeriodOption.DAY: "day",
            PeriodOption.WEEK: "week",
            PeriodOption.MONTH: "month",
            PeriodOption.YEAR: "year",
        }[self]

    @property
    def format_moment_js(self):
        """Format for moment.js https://momentjs.com/docs/#/displaying/format/"""
        return {
            PeriodOption.DAY: "DD MMM YY",
            PeriodOption.WEEK: "DD MMM YY",
            PeriodOption.MONTH: "MMM YY",
            PeriodOption.YEAR: "YYYY",
        }[self]


def drop_withdrawals(df: pd.DataFrame) -> pd.DataFrame:
    return df[~(df["Description"].str.contains("withdrawal", case=False))]


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df["Date"] = pd.to_datetime(df["Date"], format="%d/%b/%Y")
    df["Tax"] = df["Tax"].str.replace("Free", "0")
    df["Description"] = df["Description"].fillna("")
    amounts = ["Sub Total", "Tax", "Money in", "Money out"]
    for field in amounts:
        df[field] = df[field].str.replace("£", "").astype(float)
        df[field] = df[field].fillna(0)
    df["total_amount"] = df["Money in"] + df["Money out"]
    return df


def check_earnings_milestone(df: pd.DataFrame) -> bool:
    """Check if earnings in the last 7 days reach a multiple of 500"""
    df_copy = df.copy()
    df_copy = drop_withdrawals(df_copy)
    
    # Get the last 7 days
    now = pd.Timestamp.now()
    seven_days_ago = now - pd.Timedelta(days=7)
    recent_df = df_copy[df_copy["Date"] >= seven_days_ago]
    
    if recent_df.empty:
        return False
    
    # Calculate total earnings in last 7 days
    total_earnings = recent_df["total_amount"].sum()
    
    # Check if it's a multiple of 500 and greater than 0
    return total_earnings > 0 and total_earnings % 500 == 0

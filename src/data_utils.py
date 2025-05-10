import pandas as pd

PERIOD_OPTIONS = {
    "D": "day",
    "W": "week",
    "ME": "month",
    "Y": "year",
}


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

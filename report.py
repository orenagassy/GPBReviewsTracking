from datetime import date
import pandas as pd

_STAR_MAP = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}


def build_weekly_report(
    reviews: list[dict], start_date: date, end_date: date
) -> pd.DataFrame:
    """
    Aggregate reviews into weekly buckets.

    Returns a DataFrame with columns:
        week_start    - Monday of each ISO week (datetime)
        review_count  - number of reviews that week
        avg_rating    - mean star rating (NaN for weeks with no reviews)
    """
    if not reviews:
        return _empty_frame(start_date, end_date)

    df = pd.DataFrame(reviews)

    if "createTime" not in df.columns or "starRating" not in df.columns:
        return _empty_frame(start_date, end_date)

    df["createTime"] = pd.to_datetime(df["createTime"], utc=True)
    df["rating"] = df["starRating"].map(_STAR_MAP)

    # Drop reviews with unrecognised star ratings (e.g. STAR_RATING_UNSPECIFIED)
    df = df.dropna(subset=["rating"])

    start_ts = pd.Timestamp(start_date, tz="UTC")
    end_ts = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=1)
    df = df[(df["createTime"] >= start_ts) & (df["createTime"] < end_ts)]

    if df.empty:
        return _empty_frame(start_date, end_date)

    df["week_start"] = df["createTime"].dt.to_period("W").dt.start_time.dt.tz_localize(None)

    weekly = (
        df.groupby("week_start")
        .agg(review_count=("rating", "count"), avg_rating=("rating", "mean"))
        .reset_index()
    )

    # Build a complete week spine so missing weeks appear as zeros
    spine = pd.DataFrame(
        {"week_start": pd.date_range(start=start_date, end=end_date, freq="W-MON")}
    )
    result = spine.merge(weekly, on="week_start", how="left")
    result["review_count"] = result["review_count"].fillna(0).astype(int)
    # avg_rating stays NaN for empty weeks — intentional

    return result


def _empty_frame(start_date: date, end_date: date) -> pd.DataFrame:
    spine = pd.date_range(start=start_date, end=end_date, freq="W-MON")
    return pd.DataFrame(
        {"week_start": spine, "review_count": 0, "avg_rating": float("nan")}
    )

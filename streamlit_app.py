"""Streamlit dashboard for visualising Tokyo ward crime data."""

from __future__ import annotations

import io
from difflib import SequenceMatcher
from typing import List, Optional

import pandas as pd
import streamlit as st

TOKYO_CENTER = {"lat": 35.6762, "lon": 139.6503}


def read_tabular_file(uploaded_file: io.BytesIO) -> pd.DataFrame:
    """Load a CSV or Excel file into a DataFrame."""

    name = uploaded_file.name.lower()
    uploaded_file.seek(0)

    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)

    raise ValueError("CSV もしくは Excel ファイルをアップロードしてください。")


def prepare_map_dataframe(
    df: pd.DataFrame,
    ward_col: str,
    lat_col: Optional[str],
    lon_col: Optional[str],
) -> pd.DataFrame:
    """Create a dataframe compatible with st.map."""

    if not lat_col or not lon_col:
        return pd.DataFrame([TOKYO_CENTER])

    map_df = df[[ward_col]].copy()
    map_df["lat"] = pd.to_numeric(df[lat_col], errors="coerce")
    map_df["lon"] = pd.to_numeric(df[lon_col], errors="coerce")
    map_df = map_df.dropna(subset=["lat", "lon"])

    if map_df.empty:
        return pd.DataFrame([TOKYO_CENTER])

    return map_df


def ward_summary_table(df: pd.DataFrame, ward_col: str, crime_col: Optional[str]) -> pd.DataFrame:
    """Aggregate ward level counts for the left-bottom panel."""

    counts = df.groupby(ward_col).size().reset_index(name="件数")

    if crime_col and crime_col in df.columns:
        crimes = (
            df.groupby([ward_col, crime_col]).size().reset_index(name="件数")
        )
        top_crime = (
            crimes.sort_values([ward_col, "件数"], ascending=[True, False])
            .groupby(ward_col)
            .head(1)
            .rename(columns={crime_col: "最多犯罪種別", "件数": "最多件数"})
        )
        counts = counts.merge(top_crime, how="left", on=ward_col)

    return counts.rename(columns={ward_col: "区"})


def find_related_cases(
    df: pd.DataFrame,
    ward_col: str,
    summary_col: Optional[str],
    selected_ward: str,
    selected_summary: Optional[str],
    crime_col: Optional[str] = None,
    selected_crime: Optional[str] = None,
    top_n: int = 5,
) -> pd.DataFrame:
    """Find textually similar cases within the same ward (and crime type)."""

    if not summary_col or summary_col not in df.columns or not selected_summary:
        return pd.DataFrame()

    ward_rows = df[df[ward_col] == selected_ward]

    if crime_col and selected_crime and crime_col in df.columns:
        ward_rows = ward_rows[ward_rows[crime_col] == selected_crime]

    ward_rows = ward_rows.dropna(subset=[summary_col])

    if ward_rows.empty:
        return pd.DataFrame()

    def similarity(text: str) -> float:
        return SequenceMatcher(None, selected_summary, text).ratio()

    ranked = ward_rows.assign(_score=ward_rows[summary_col].map(similarity))
    ranked = ranked[ranked[summary_col] != selected_summary]
    ranked = ranked[ranked["_score"] >= 0.3]

    if ranked.empty:
        return pd.DataFrame()

    ranked = ranked.sort_values("_score", ascending=False).head(top_n)
    return ranked.drop(columns="_score")


def main() -> None:
    st.set_page_config(page_title="東京都犯罪情報ダッシュボード", layout="wide")
    st.title("東京都犯罪情報ダッシュボード")
    st.caption("CSV / Excel ファイルをアップロードして区ごとの情報を可視化します。")

    uploaded = st.file_uploader("犯罪データファイルを選択", type=["csv", "xlsx", "xls"])
    if uploaded is None:
        st.info("まずは CSV もしくは Excel ファイルをアップロードしてください。")
        return

    try:
        df = read_tabular_file(uploaded)
    except Exception as exc:  # pragma: no cover - surfaced to the UI
        st.error(f"ファイルの読み込み中にエラーが発生しました: {exc}")
        return

    if df.empty:
        st.warning("データが空です。別のファイルをお試しください。")
        return

    columns = list(df.columns)

    st.sidebar.header("列設定")
    ward_col = st.sidebar.selectbox("区を表す列", options=columns)
    crime_col = st.sidebar.selectbox(
        "犯罪種別の列", options=["(なし)"] + columns, index=0
    )
    crime_col = None if crime_col == "(なし)" else crime_col

    summary_col = st.sidebar.selectbox(
        "概要を表す列", options=["(なし)"] + columns, index=0
    )
    summary_col = None if summary_col == "(なし)" else summary_col

    lat_col = st.sidebar.selectbox("緯度列", options=["(なし)"] + columns, index=0)
    lat_col = None if lat_col == "(なし)" else lat_col

    lon_col = st.sidebar.selectbox("経度列", options=["(なし)"] + columns, index=0)
    lon_col = None if lon_col == "(なし)" else lon_col

    wards = df[ward_col].dropna().unique().tolist()
    wards.sort()
    selected_ward = st.sidebar.selectbox("表示する区", options=wards)

    crime_options: List[str] = []
    selected_crime: Optional[str] = None
    if crime_col:
        crime_options = ["すべて"] + (
            df[df[ward_col] == selected_ward][crime_col].dropna().unique().tolist()
        )
        selected_crime = st.sidebar.selectbox("犯罪種別で絞り込み", options=crime_options)
        if selected_crime == "すべて":
            selected_crime = None

    filtered = df[df[ward_col] == selected_ward]
    if selected_crime:
        filtered = filtered[filtered[crime_col] == selected_crime]

    summary_options: List[str] = []
    selected_summary: Optional[str] = None
    if summary_col:
        summary_options = (
            filtered[summary_col].dropna().astype(str).unique().tolist()
        )
        summary_options.sort()
        if summary_options:
            selected_summary = st.sidebar.selectbox(
                "概要を選択", options=summary_options
            )

    top_left, top_right = st.columns((2, 1))

    with top_left:
        st.subheader("左上: 東京都全域マップ")
        map_df = prepare_map_dataframe(df, ward_col, lat_col, lon_col)
        st.map(map_df)

    with top_right:
        st.subheader("右上: 概要")
        st.markdown(f"**選択中の区:** {selected_ward}")
        if crime_col:
            st.markdown(
                f"**犯罪種別:** {selected_crime if selected_crime else 'すべて'}"
            )
        if summary_col and selected_summary:
            st.markdown("**選択した概要:**")
            st.info(selected_summary)
        elif summary_col:
            st.warning("概要を選択すると詳細が表示されます。")
        else:
            st.info("サイドバーで概要列を選択すると右上に詳細が表示されます。")

    bottom_left, bottom_right = st.columns(2)

    with bottom_left:
        st.subheader("左下: 区一覧")
        st.dataframe(ward_summary_table(df, ward_col, crime_col), use_container_width=True)

    with bottom_right:
        st.subheader("右下: 関連事例")
        related = find_related_cases(
            df=df,
            ward_col=ward_col,
            summary_col=summary_col,
            selected_ward=selected_ward,
            selected_summary=selected_summary,
            crime_col=crime_col,
            selected_crime=selected_crime,
            top_n=5,
        )
        if related.empty:
            st.info("関連事例を表示するには概要列からレコードを選択してください。")
        else:
            display_cols = [ward_col]
            if crime_col:
                display_cols.append(crime_col)
            if summary_col:
                display_cols.append(summary_col)
            st.dataframe(related[display_cols], use_container_width=True)


if __name__ == "__main__":  # pragma: no cover - Streamlit entry point
    main()

import io
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, List, Optional, Tuple

try:  # pragma: no cover - import is validated in tests via stubs
    import pandas as pd  # type: ignore
    from pandas.errors import ParserError  # type: ignore
except ImportError:  # pragma: no cover - runtime guard for optional dependency
    pd = None  # type: ignore

    class ParserError(Exception):
        """Fallback parser error used when pandas is unavailable."""

        pass

try:  # pragma: no cover - import exercised when running the UI
    import streamlit as st  # type: ignore
except ImportError:  # pragma: no cover - allows importing the module in tests
    st = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover - typing aide
    import pandas as _pd

TOKYO_CENTER = {"lat": 35.6762, "lon": 139.6503}


def ensure_pandas_available() -> None:
    """Ensure pandas is installed before performing dataframe operations."""

    if pd is None:  # pragma: no cover - defensive runtime guard
        raise ImportError(
            "pandas がインストールされていません。`pip install -r requirements.txt` を実行して依存関係を整えてください。"
        )


def load_tabular_file(uploaded_file: io.BytesIO) -> Tuple["_pd.DataFrame", List[str]]:
    """Return a dataframe from a CSV or Excel file along with load warnings."""

    ensure_pandas_available()
    filename = uploaded_file.name.lower()
    warnings: List[str] = []

    if filename.endswith(".csv"):
        attempts = [
            ({}, False),
            ({"engine": "python"}, True),
            ({"engine": "python", "on_bad_lines": "skip"}, True),
        ]

        last_exc: Optional[Exception] = None
        for kwargs, record_warning in attempts:
            uploaded_file.seek(0)
            try:
                df = pd.read_csv(uploaded_file, **kwargs)
            except ParserError as exc:
                last_exc = exc
                continue
            except Exception as exc:  # pragma: no cover - defensive
                last_exc = exc
                continue

            if record_warning and kwargs.get("on_bad_lines") == "skip":
                warnings.append(
                    "一部の行で列数が一致しなかったため除外しました。データを確認してください。"
                )
            elif record_warning:
                warnings.append(
                    "標準の読み込みでエラーが発生したため、柔軟な解析モードで読み込みました。"
                )

            return df, warnings

        if last_exc:
            raise last_exc

    elif filename.endswith((".xlsx", ".xls")):
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file), warnings
    else:
        raise ValueError("Unsupported file type. Please upload a CSV or Excel file.")

    raise ValueError("CSVファイルの読み込みに失敗しました。ファイルの内容を確認してください。")


def summarize_records(
    df: "_pd.DataFrame",
    ward_col: str,
    crime_col: Optional[str] = None,
    summary_col: Optional[str] = None,
) -> "_pd.DataFrame":
    ensure_pandas_available()
    columns = [ward_col]
    rename_map = {ward_col: "区"}

    if crime_col:
        columns.append(crime_col)
        rename_map[crime_col] = "犯罪種別"

    if summary_col:
        columns.append(summary_col)
        rename_map[summary_col] = "概要"

    return df[columns].rename(columns=rename_map)


def compute_related_cases(
    df: "_pd.DataFrame",
    ward_col: str,
    summary_col: Optional[str],
    selected_ward: str,
    selected_summary: Optional[str],
    crime_col: Optional[str] = None,
    selected_crime: Optional[str] = None,
    top_n: int = 5,
) -> "_pd.DataFrame":
    ensure_pandas_available()

    if not summary_col or summary_col not in df.columns or not selected_summary:
        return pd.DataFrame()

    candidates = df[df[ward_col] == selected_ward]
    if crime_col and selected_crime:
        candidates = candidates[candidates[crime_col] == selected_crime]

    candidates = candidates.dropna(subset=[summary_col])
    if candidates.empty:
        return pd.DataFrame()

    def similarity(summary: str) -> float:
        return SequenceMatcher(None, selected_summary, summary).ratio()

    scored = candidates.assign(_score=candidates[summary_col].apply(similarity))
    scored = scored[scored[summary_col] != selected_summary]
    scored = scored[scored["_score"] >= 0.3]
    if scored.empty:
        return pd.DataFrame()

    scored = scored.sort_values("_score", ascending=False).head(top_n)
    return scored.drop(columns="_score")


def display_map(
    df: "_pd.DataFrame",
    lat_col: Optional[str],
    lon_col: Optional[str],
    ward_col: str,
    selected_ward: str,
):
    ensure_pandas_available()
    st.subheader("東京都全域マップ")
    if lat_col and lon_col and lat_col in df.columns and lon_col in df.columns:
        map_df = df[[lat_col, lon_col, ward_col]].rename(
            columns={lat_col: "lat", lon_col: "lon", ward_col: "区"}
        )
        st.map(map_df)
    else:
        st.info(
            "位置情報の列が選択されていないため、東京都心部を仮表示しています。"
        )
        st.map(pd.DataFrame([TOKYO_CENTER]))


def main() -> None:
    """Render the Streamlit dashboard."""

    if st is None:  # pragma: no cover - guards CLI usage without streamlit
        raise RuntimeError(
            "Streamlit がインストールされていません。`pip install -r requirements.txt` を実行してください。"
        )

    ensure_pandas_available()

    st.set_page_config(page_title="東京都犯罪ダッシュボード", layout="wide")
    st.title("東京都犯罪情報ダッシュボード")

    st.markdown(
        """
        添付するCSVまたはExcelファイルをアップロードすると、区別に犯罪情報を可視化できます。
        ファイルを変更したい場合は再度アップロードしてください。
        """
    )

    uploaded = st.file_uploader(
        "犯罪データファイル (CSV / Excel)", type=["csv", "xlsx", "xls"]
    )

    if not uploaded:
        st.stop()

    load_warnings: List[str] = []
    try:
        data, load_warnings = load_tabular_file(uploaded)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    except Exception as exc:  # pragma: no cover - defensive
        st.error(f"ファイルの読み込みに失敗しました: {exc}")
        st.stop()

    for warning in load_warnings:
        st.warning(warning)

    if data.empty:
        st.warning("データが空です。内容を確認してください。")
        st.stop()

    columns = list(data.columns)

    ward_col = st.selectbox("区名の列を選択", columns)
    crime_col = st.selectbox("犯罪種別の列を選択 (任意)", [None] + columns)
    summary_col = st.selectbox("概要の列を選択 (任意)", [None] + columns)
    related_col = st.selectbox("関連事例の列を選択 (任意)", [None] + columns)
    lat_col = st.selectbox("緯度の列を選択 (任意)", [None] + columns)
    lon_col = st.selectbox("経度の列を選択 (任意)", [None] + columns)

    wards = sorted(data[ward_col].dropna().unique())
    selected_ward = st.selectbox("表示する区を選択", wards)

    crime_options = ["すべて"]
    if crime_col:
        crime_options += sorted(data[crime_col].dropna().unique())
    selected_crime = st.selectbox("犯罪種別を絞り込み", crime_options)
    selected_crime_value = (
        selected_crime if (crime_col and selected_crime != "すべて") else None
    )

    filtered_df = data[data[ward_col] == selected_ward]
    if crime_col and selected_crime_value:
        filtered_df = filtered_df[filtered_df[crime_col] == selected_crime_value]

    # Layout containers
    upper_left, upper_right = st.columns((2, 1))
    lower_left, lower_right = st.columns((1, 1))

    selected_summary_value: Optional[str] = None

    with upper_left:
        display_map(data, lat_col, lon_col, ward_col, selected_ward)

    with lower_left:
        st.subheader("区ごとの一覧")
        ward_summary = (
            data.groupby(ward_col)
            .size()
            .reset_index(name="件数")
            .sort_values("件数", ascending=False)
        )
        ward_summary_display = ward_summary.rename(columns={ward_col: "区"})
        st.dataframe(ward_summary_display, use_container_width=True)

        if not ward_summary.empty:
            top_wards_df = ward_summary.head(3)
            metric_cols = st.columns(len(top_wards_df))
            for metric_col, (_, ward_row) in zip(
                metric_cols, top_wards_df.iterrows()
            ):
                metric_col.metric(str(ward_row[ward_col]), f"{ward_row['件数']}件")

    with upper_right:
        st.subheader("概要")
        if summary_col:
            summaries = (
                filtered_df.dropna(subset=[summary_col])
                if not filtered_df.empty
                else pd.DataFrame()
            )
            if summaries.empty:
                st.info("該当する概要がありません。条件を変更してください。")
                selected_summary_value = None
            else:
                summary_choices = (
                    summaries[summary_col].dropna().unique().tolist()
                )
                selected_summary_value = st.selectbox(
                    "表示する概要を選択",
                    summary_choices,
                    format_func=lambda value: str(value),
                )
                st.markdown(f"**選択した概要**\n\n{selected_summary_value}")

                detail_columns = [ward_col]
                if crime_col:
                    detail_columns.append(crime_col)
                detail_columns.append(summary_col)
                detail_df = summarize_records(
                    summaries[summaries[summary_col] == selected_summary_value],
                    ward_col,
                    crime_col,
                    summary_col,
                )
                st.dataframe(detail_df, use_container_width=True)
        else:
            summary_df = summarize_records(filtered_df, ward_col, crime_col)
            if summary_df.empty:
                st.info("該当するデータがありません。条件を変更してください。")
                selected_summary_value = None
            else:
                st.dataframe(summary_df, use_container_width=True)
                selected_summary_value = None

    with lower_right:
        st.subheader("関連事例")
        related_cases = compute_related_cases(
            data,
            ward_col,
            summary_col,
            selected_ward,
            selected_summary_value if summary_col else None,
            crime_col,
            selected_crime_value,
        )

        if related_cases.empty and related_col and related_col in data.columns:
            fallback_df = summarize_records(
                filtered_df, ward_col, summary_col=related_col
            )
            fallback_df = fallback_df.rename(columns={"概要": "関連事例"})
            if fallback_df.empty:
                st.info("関連事例を表示できません。条件や列の選択を確認してください。")
            else:
                st.dataframe(fallback_df, use_container_width=True)
        elif related_cases.empty:
            st.info("関連事例を表示できません。条件や列の選択を確認してください。")
        else:
            display_columns = [ward_col]
            rename_map = {ward_col: "区"}

            if crime_col:
                display_columns.append(crime_col)
                rename_map[crime_col] = "犯罪種別"

            if summary_col:
                display_columns.append(summary_col)
                rename_map[summary_col] = "概要"

            if related_col and related_col in related_cases.columns:
                display_columns.append(related_col)
                rename_map[related_col] = "関連事例"

            display_df = related_cases[display_columns].rename(columns=rename_map)
            st.dataframe(display_df, use_container_width=True)

    st.caption("データの列を選択して、希望のビューを作成してください。")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()

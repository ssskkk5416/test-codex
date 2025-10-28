import pytest

pd = pytest.importorskip("pandas")

from streamlit_app import find_related_cases

def test_find_related_cases_returns_similar_rows():
    data = pd.DataFrame(
        {
            "区": ["新宿区", "新宿区", "渋谷区", "新宿区"],
            "概要": [
                "深夜に発生したひったくり事件",
                "昼間に起きた窃盗事件",
                "渋谷駅前での置き引き",
                "深夜のひったくり未遂",
            ],
            "犯罪種別": ["ひったくり", "窃盗", "置き引き", "ひったくり"],
        }
    )

    similar = find_related_cases(
        df=data,
        ward_col="区",
        summary_col="概要",
        selected_ward="新宿区",
        selected_summary="深夜に発生したひったくり事件",
        crime_col="犯罪種別",
        selected_crime="ひったくり",
        top_n=3,
    )

    assert not similar.empty
    assert (similar["区"] == "新宿区").all()
    assert "深夜のひったくり未遂" in similar["概要"].values

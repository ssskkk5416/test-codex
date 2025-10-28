"""Tests for the data loading logic in ``streamlit_app``.

The production module relies on pandas which is unavailable in the execution
environment.  These tests provide lightweight stubs to emulate the pandas API
surface that ``load_tabular_file`` interacts with so we can exercise the retry
behaviour without the heavy dependency.
"""

from __future__ import annotations

import importlib
import io
import pathlib
import sys
import types
from typing import Any, Callable, Dict, Iterable, List, Tuple

import pytest

_SENTINEL = object()

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _make_pandas_stub(
    csv_behaviours: Iterable[Any] | None = None,
    excel_behaviour: Any = _SENTINEL,
) -> Tuple[
    types.ModuleType,
    types.ModuleType,
    List[Dict[str, Any]],
    type,
    List[Any],
]:
    """Return stub ``pandas`` and ``pandas.errors`` modules.

    ``csv_behaviours`` is an iterable that yields either a value (returned to the
    caller) or an ``Exception`` instance that should be raised.  ``excel_behaviour``
    mirrors this behaviour for ``read_excel``.
    """

    behaviours = list(csv_behaviours or [])
    call_log: List[Dict[str, Any]] = []

    parser_error = type("ParserError", (Exception,), {})

    errors_module = types.ModuleType("pandas.errors")
    errors_module.ParserError = parser_error  # type: ignore[attr-defined]

    pandas_module = types.ModuleType("pandas")
    pandas_module.errors = errors_module  # type: ignore[attr-defined]

    def read_csv(file_obj: io.BytesIO, **kwargs: Any) -> Any:
        call_log.append(kwargs)
        if behaviours:
            next_value = behaviours.pop(0)
            if isinstance(next_value, Exception):
                raise next_value
            return next_value
        return {"kind": "csv", "kwargs": kwargs}

    def read_excel(file_obj: io.BytesIO, **kwargs: Any) -> Any:
        if isinstance(excel_behaviour, Exception):
            raise excel_behaviour
        if excel_behaviour is _SENTINEL:
            return {"kind": "excel", "kwargs": kwargs}
        return excel_behaviour

    pandas_module.read_csv = read_csv  # type: ignore[attr-defined]
    pandas_module.read_excel = read_excel  # type: ignore[attr-defined]

    return pandas_module, errors_module, call_log, parser_error, behaviours


def _reload_with_stub(
    csv_behaviour_factory: Callable[[type], Iterable[Any]] | None = None,
    excel_behaviour: Any = _SENTINEL,
):
    """Reload ``streamlit_app`` with a pandas stub in place."""

    for module_name in ["streamlit_app", "pandas", "pandas.errors"]:
        sys.modules.pop(module_name, None)

    pandas_module, errors_module, calls, parser_error, behaviours = _make_pandas_stub(
        None, excel_behaviour
    )
    if csv_behaviour_factory:
        behaviours.extend(csv_behaviour_factory(parser_error))
    sys.modules["pandas"] = pandas_module
    sys.modules["pandas.errors"] = errors_module

    import streamlit_app

    importlib.reload(streamlit_app)
    return streamlit_app, calls, parser_error


def test_load_csv_successful_path() -> None:
    streamlit_app, calls, _ = _reload_with_stub(lambda _: [{"data": "ok"}])

    payload = io.BytesIO(b"ward,crime\n")
    payload.name = "records.csv"  # type: ignore[attr-defined]

    frame, warnings = streamlit_app.load_tabular_file(payload)
    assert frame == {"data": "ok"}
    assert warnings == []
    assert calls == [{}]


def test_load_csv_recovers_with_python_engine() -> None:
    streamlit_app, calls, parser_error = _reload_with_stub(
        lambda err: [err("boom"), {"data": "python"}]
    )

    payload = io.BytesIO(b"broken")
    payload.name = "records.csv"  # type: ignore[attr-defined]

    frame, warnings = streamlit_app.load_tabular_file(payload)
    assert frame == {"data": "python"}
    assert "柔軟な解析モード" in warnings[0]
    assert calls == [{}, {"engine": "python"}]


def test_load_csv_skips_bad_lines_with_warning() -> None:
    streamlit_app, calls, parser_error = _reload_with_stub(
        lambda err: [err("first"), err("second"), {"data": "skip"}]
    )

    payload = io.BytesIO(b"bad")
    payload.name = "records.csv"  # type: ignore[attr-defined]

    frame, warnings = streamlit_app.load_tabular_file(payload)
    assert frame == {"data": "skip"}
    assert any("除外しました" in message for message in warnings)
    assert calls == [
        {},
        {"engine": "python"},
        {"engine": "python", "on_bad_lines": "skip"},
    ]


def test_load_csv_raises_last_error_when_all_attempts_fail() -> None:
    streamlit_app, _, parser_error = _reload_with_stub(
        lambda err: [err("first"), err("second"), err("third")]
    )

    payload = io.BytesIO(b"bad")
    payload.name = "records.csv"  # type: ignore[attr-defined]

    with pytest.raises(parser_error):
        streamlit_app.load_tabular_file(payload)


def test_load_excel_pass_through() -> None:
    sentinel = {"data": "excel"}
    streamlit_app, calls, _ = _reload_with_stub(lambda _: [], sentinel)

    payload = io.BytesIO(b"excel")
    payload.name = "records.xlsx"  # type: ignore[attr-defined]

    frame, warnings = streamlit_app.load_tabular_file(payload)
    assert frame == sentinel
    assert warnings == []
    assert calls == []


def test_load_rejects_unsupported_extension() -> None:
    streamlit_app, _, _ = _reload_with_stub(lambda _: [])

    payload = io.BytesIO(b"data")
    payload.name = "records.txt"  # type: ignore[attr-defined]

    with pytest.raises(ValueError):
        streamlit_app.load_tabular_file(payload)


def test_load_requires_pandas() -> None:
    for module_name in ["streamlit_app", "pandas", "pandas.errors"]:
        sys.modules.pop(module_name, None)

    import streamlit_app

    importlib.reload(streamlit_app)

    payload = io.BytesIO(b"data")
    payload.name = "records.csv"  # type: ignore[attr-defined]

    with pytest.raises(ImportError):
        streamlit_app.load_tabular_file(payload)

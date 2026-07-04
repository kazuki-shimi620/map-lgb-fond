from __future__ import annotations

import json

import pytest

from collect import mlit


def test_collect_requires_api_key(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv(mlit.REINFOLIB_API_KEY_ENV, raising=False)

    with pytest.raises(mlit.ReinfolibApiError, match=mlit.REINFOLIB_API_KEY_ENV):
        mlit.collect_mlit_data(region="tokyo", year=2024, output_dir=tmp_path)


def test_collect_writes_valid_response(monkeypatch, tmp_path) -> None:
    response = {"status": "OK", "data": [{"Type": "中古マンション等"}]}
    monkeypatch.setattr(mlit, "fetch_reinfolib_api", lambda *args, **kwargs: response)

    output = mlit.collect_mlit_data(
        region="tokyo",
        year=2024,
        output_dir=tmp_path,
        api_key="test-key",
    )

    assert output.name == "tokyo_2024_xit001.json"
    assert json.loads(output.read_text(encoding="utf-8")) == response


def test_collect_rejects_invalid_response(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        mlit,
        "fetch_reinfolib_api",
        lambda *args, **kwargs: {"status": "ERROR", "data": []},
    )

    with pytest.raises(mlit.ReinfolibApiError, match="status: ERROR"):
        mlit.collect_mlit_data(
            region="tokyo",
            year=2024,
            output_dir=tmp_path,
            api_key="test-key",
        )

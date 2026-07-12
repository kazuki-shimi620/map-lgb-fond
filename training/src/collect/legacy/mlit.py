from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from collect.reinfolib import REINFOLIB_API_KEY_ENV, REINFOLIB_BASE_URL

PREFECTURE_CODES = {
    "tokyo": "13",
    "saitama": "11",
    "chiba": "12",
    "kanagawa": "14",
}


class ReinfolibApiError(RuntimeError):
    pass


def convert_shift_jis_to_utf8(source: str | Path, destination: str | Path) -> Path:
    source_path = Path(source)
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    text = source_path.read_text(encoding="shift_jis")
    destination_path.write_text(text, encoding="utf-8")
    return destination_path


def collect_mlit_data(
    *,
    region: str,
    year: int,
    output_dir: str | Path,
    quarter: int | None = None,
    city: str | None = None,
    station: str | None = None,
    api_key: str | None = None,
    price_classification: str = "01",
) -> Path:
    subscription_key = api_key or os.getenv(REINFOLIB_API_KEY_ENV)
    if not subscription_key:
        raise ReinfolibApiError(
            f"{REINFOLIB_API_KEY_ENV} is not set. "
            "Set it in training/.env or the process environment."
        )

    area = PREFECTURE_CODES.get(region)
    if not area:
        raise ValueError(f"Unsupported region for MLIT API: {region}")
    if year < 2005:
        raise ValueError("MLIT transaction price data is available from 2005")
    if quarter is not None and quarter not in {1, 2, 3, 4}:
        raise ValueError("quarter must be between 1 and 4")

    params = {
        "year": str(year),
        "area": area,
        "priceClassification": price_classification,
        "language": "ja",
    }
    if quarter is not None:
        params["quarter"] = str(quarter)
    if city:
        params["city"] = city
    if station:
        params["station"] = station

    data = fetch_reinfolib_api("XIT001", params=params, subscription_key=subscription_key)
    validate_reinfolib_response(data)
    output_path = _build_output_path(output_dir, region, year, quarter)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def fetch_reinfolib_api(
    api_id: str,
    *,
    params: dict[str, str],
    subscription_key: str,
    timeout: int = 60,
) -> object:
    url = f"{REINFOLIB_BASE_URL}/{api_id}?{urlencode(params)}"
    request = Request(url)
    request.add_header("Ocp-Apim-Subscription-Key", subscription_key)
    request.add_header("Accept-Encoding", "gzip")

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
            encoding = (response.headers.get("Content-Encoding") or "").lower()
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:300]
        message = f"Reinfolib API returned HTTP {error.code} for {api_id}"
        if detail:
            message = f"{message}: {detail}"
        raise ReinfolibApiError(message) from error
    except URLError as error:
        raise ReinfolibApiError(f"Could not connect to Reinfolib API: {error.reason}") from error

    if "gzip" in encoding:
        payload = gzip.decompress(payload)
    if not payload:
        raise ReinfolibApiError(f"Reinfolib API returned an empty response for {api_id}")

    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReinfolibApiError(f"Reinfolib API returned invalid JSON for {api_id}") from error


def validate_reinfolib_response(data: object) -> None:
    if not isinstance(data, dict):
        raise ReinfolibApiError("Reinfolib API response must be a JSON object")
    if data.get("status") != "OK":
        raise ReinfolibApiError(f"Reinfolib API returned status: {data.get('status', 'unknown')}")
    if not isinstance(data.get("data"), list):
        raise ReinfolibApiError("Reinfolib API response does not contain a data list")


def _build_output_path(output_dir: str | Path, region: str, year: int, quarter: int | None) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    suffix = f"_q{quarter}" if quarter is not None else ""
    return directory / f"{region}_{year}{suffix}_xit001.json"

from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

CHECKLIST_START = "<!-- reinfolib-csv-checklist:start -->"
CHECKLIST_END = "<!-- reinfolib-csv-checklist:end -->"
CHECKLIST_FROM_YEAR = 2005
CHECKLIST_TO_YEAR = 2025
CSV_COLUMNS = [
    "種類",
    "価格情報区分",
    "市区町村コード",
    "都道府県名",
    "市区町村名",
    "地区名",
    "最寄駅：名称",
    "最寄駅：距離（分）",
    "取引価格（総額）",
    "間取り",
    "面積（㎡）",
    "建築年",
    "建物の構造",
    "用途",
    "今後の利用目的",
    "都市計画",
    "建ぺい率（％）",
    "容積率（％）",
    "取引時期",
    "改装",
    "取引の事情等",
]
REQUIRED_CSV_COLUMNS = {"種類", "取引時期", "最寄駅：名称", "最寄駅：距離（分）"}
HIGH_VOLUME_PREFECTURES = {
    "saitama",
    "chiba",
    "tokyo",
    "kanagawa",
    "aichi",
    "kyoto",
    "osaka",
    "hyogo",
    "fukuoka",
}


@dataclass(frozen=True)
class Prefecture:
    code: str
    slug: str
    name: str
    csv_prefix: str


PREFECTURES = [
    Prefecture("01", "hokkaido", "北海道", "Hokkaido"),
    Prefecture("02", "aomori", "青森県", "Aomori"),
    Prefecture("03", "iwate", "岩手県", "Iwate"),
    Prefecture("04", "miyagi", "宮城県", "Miyagi"),
    Prefecture("05", "akita", "秋田県", "Akita"),
    Prefecture("06", "yamagata", "山形県", "Yamagata"),
    Prefecture("07", "fukushima", "福島県", "Fukushima"),
    Prefecture("08", "ibaraki", "茨城県", "Ibaraki"),
    Prefecture("09", "tochigi", "栃木県", "Tochigi"),
    Prefecture("10", "gunma", "群馬県", "Gunma"),
    Prefecture("11", "saitama", "埼玉県", "Saitama"),
    Prefecture("12", "chiba", "千葉県", "Chiba"),
    Prefecture("13", "tokyo", "東京都", "Tokyo"),
    Prefecture("14", "kanagawa", "神奈川県", "Kanagawa"),
    Prefecture("15", "niigata", "新潟県", "Niigata"),
    Prefecture("16", "toyama", "富山県", "Toyama"),
    Prefecture("17", "ishikawa", "石川県", "Ishikawa"),
    Prefecture("18", "fukui", "福井県", "Fukui"),
    Prefecture("19", "yamanashi", "山梨県", "Yamanashi"),
    Prefecture("20", "nagano", "長野県", "Nagano"),
    Prefecture("21", "gifu", "岐阜県", "Gifu"),
    Prefecture("22", "shizuoka", "静岡県", "Shizuoka"),
    Prefecture("23", "aichi", "愛知県", "Aichi"),
    Prefecture("24", "mie", "三重県", "Mie"),
    Prefecture("25", "shiga", "滋賀県", "Shiga"),
    Prefecture("26", "kyoto", "京都府", "Kyoto"),
    Prefecture("27", "osaka", "大阪府", "Osaka"),
    Prefecture("28", "hyogo", "兵庫県", "Hyogo"),
    Prefecture("29", "nara", "奈良県", "Nara"),
    Prefecture("30", "wakayama", "和歌山県", "Wakayama"),
    Prefecture("31", "tottori", "鳥取県", "Tottori"),
    Prefecture("32", "shimane", "島根県", "Shimane"),
    Prefecture("33", "okayama", "岡山県", "Okayama"),
    Prefecture("34", "hiroshima", "広島県", "Hiroshima"),
    Prefecture("35", "yamaguchi", "山口県", "Yamaguchi"),
    Prefecture("36", "tokushima", "徳島県", "Tokushima"),
    Prefecture("37", "kagawa", "香川県", "Kagawa"),
    Prefecture("38", "ehime", "愛媛県", "Ehime"),
    Prefecture("39", "kochi", "高知県", "Kochi"),
    Prefecture("40", "fukuoka", "福岡県", "Fukuoka"),
    Prefecture("41", "saga", "佐賀県", "Saga"),
    Prefecture("42", "nagasaki", "長崎県", "Nagasaki"),
    Prefecture("43", "kumamoto", "熊本県", "Kumamoto"),
    Prefecture("44", "oita", "大分県", "Oita"),
    Prefecture("45", "miyazaki", "宮崎県", "Miyazaki"),
    Prefecture("46", "kagoshima", "鹿児島県", "Kagoshima"),
    Prefecture("47", "okinawa", "沖縄県", "Okinawa"),
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download Reinfolib CSV ZIPs through the official UI."
    )
    parser.add_argument("--prefectures", nargs="+", default=["all"])
    parser.add_argument("--from-year", type=int, default=2005)
    parser.add_argument("--to-year", type=int, default=2025)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--todo-file", type=Path, default=Path("../TODO.md"))
    parser.add_argument("--delay-seconds", type=float, default=15.0)
    parser.add_argument(
        "--chunk-years",
        type=int,
        default=0,
        help="Years per browser download. Use 0 for automatic selection.",
    )
    parser.add_argument("--download-timeout-ms", type=int, default=120_000)
    parser.add_argument("--chrome-path")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--keep-aggregate", action="store_true")
    parser.add_argument("--checklist-only", action="store_true")
    args = parser.parse_args()

    validate_year_range(args.from_year, args.to_year)
    selected = resolve_prefectures(args.prefectures)
    output_dir = args.output_dir.resolve()
    todo_file = args.todo_file.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.checklist_only:
        sync_checklist(todo_file, output_dir, CHECKLIST_FROM_YEAR, CHECKLIST_TO_YEAR)
        return 0

    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for browser-based CSV downloads")
    downloader = Path(__file__).resolve().parents[2] / "browser" / "download.mjs"
    if not (downloader.parent / "node_modules" / "playwright-core").exists():
        raise RuntimeError("Playwright is not installed. Run 'make setup-csv-download' first.")

    failures: list[str] = []
    download_count = 0
    for prefecture in selected:
        missing_years = [
            year
            for year in range(args.from_year, args.to_year + 1)
            if args.force or not is_valid_year_zip(year_zip_path(output_dir, prefecture, year))
        ]
        if not missing_years:
            print(f"skip {prefecture.name}: all requested years already exist")
            continue

        chunk_size = args.chunk_years or (
            1 if prefecture.slug in HIGH_VOLUME_PREFECTURES else len(missing_years)
        )
        for first_year, last_year in build_year_chunks(missing_years, chunk_size):
            if download_count > 0 and args.delay_seconds > 0:
                time.sleep(args.delay_seconds)
            download_count += 1
            aggregate_dir = output_dir / ".downloads"
            aggregate_dir.mkdir(parents=True, exist_ok=True)
            aggregate_path = aggregate_dir / f"{prefecture.slug}_{first_year}_{last_year}.zip"

            try:
                has_data = download_prefecture(
                    node=node,
                    downloader=downloader,
                    prefecture=prefecture,
                    from_year=first_year,
                    to_year=last_year,
                    output_path=aggregate_path,
                    timeout_ms=args.download_timeout_ms,
                    chrome_path=args.chrome_path,
                )
                if has_data:
                    counts = split_year_zips(
                        aggregate_path=aggregate_path,
                        output_dir=output_dir,
                        prefecture=prefecture,
                        from_year=first_year,
                        to_year=last_year,
                        force=args.force,
                    )
                else:
                    counts = create_empty_year_zips(
                        output_dir=output_dir,
                        prefecture=prefecture,
                        from_year=first_year,
                        to_year=last_year,
                        force=args.force,
                    )
                print(
                    f"completed {prefecture.name} {first_year}-{last_year}: "
                    f"{sum(counts.values())} records"
                )
                if not args.keep_aggregate:
                    aggregate_path.unlink(missing_ok=True)
            except (
                OSError,
                RuntimeError,
                subprocess.CalledProcessError,
                zipfile.BadZipFile,
            ) as error:
                message = f"{prefecture.name} {first_year}-{last_year}: {error}"
                failures.append(message)
                print(f"failed {message}")
                if not args.continue_on_error:
                    raise

    if failures:
        print("download failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


def validate_year_range(from_year: int, to_year: int) -> None:
    if from_year < 2005 or to_year < from_year:
        raise ValueError("year range must start at 2005 or later and be in ascending order")


def build_year_chunks(years: list[int], chunk_size: int) -> list[tuple[int, int]]:
    if chunk_size < 1:
        raise ValueError("chunk-years must be at least 1")
    if not years:
        return []

    chunks: list[tuple[int, int]] = []
    start = years[0]
    previous = years[0]
    for year in years[1:]:
        if year != previous + 1 or year - start + 1 > chunk_size:
            chunks.append((start, previous))
            start = year
        previous = year
    chunks.append((start, previous))
    return chunks


def resolve_prefectures(values: list[str]) -> list[Prefecture]:
    if values == ["all"]:
        return PREFECTURES
    lookup = {
        value: prefecture
        for prefecture in PREFECTURES
        for value in (prefecture.code, prefecture.slug)
    }
    unknown = [value for value in values if value not in lookup]
    if unknown:
        raise ValueError(f"unknown prefectures: {', '.join(unknown)}")
    return list(dict.fromkeys(lookup[value] for value in values))


def download_prefecture(
    *,
    node: str,
    downloader: Path,
    prefecture: Prefecture,
    from_year: int,
    to_year: int,
    output_path: Path,
    timeout_ms: int,
    chrome_path: str | None,
) -> bool:
    command = [
        node,
        str(downloader),
        "--prefecture-code",
        prefecture.code,
        "--from-season",
        f"{from_year}{3 if from_year == 2005 else 1}",
        "--to-season",
        f"{to_year}4",
        "--output",
        str(output_path),
        "--timeout-ms",
        str(timeout_ms),
    ]
    if chrome_path:
        command.extend(["--chrome-path", chrome_path])
    print(f"download {prefecture.name}: {from_year}-{to_year}")
    no_data_marker = Path(f"{output_path}.no-data")
    output_path.unlink(missing_ok=True)
    no_data_marker.unlink(missing_ok=True)
    subprocess.run(command, check=True)
    if no_data_marker.exists():
        no_data_marker.unlink()
        return False
    if not zipfile.is_zipfile(output_path):
        raise zipfile.BadZipFile(f"downloaded file is not a ZIP: {output_path}")
    return True


def create_empty_year_zips(
    *,
    output_dir: Path,
    prefecture: Prefecture,
    from_year: int,
    to_year: int,
    force: bool,
) -> dict[int, int]:
    import io

    buffer = io.StringIO(newline="")
    csv.writer(buffer).writerow(CSV_COLUMNS)
    payload = buffer.getvalue().encode("cp932")
    counts = {}
    for year in range(from_year, to_year + 1):
        destination = year_zip_path(output_dir, prefecture, year)
        counts[year] = 0
        if destination.exists() and not force and is_valid_year_zip(destination):
            continue
        temporary_zip = destination.with_suffix(".zip.tmp")
        with zipfile.ZipFile(
            temporary_zip,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as output_zip:
            output_zip.writestr(internal_csv_name(prefecture, year), payload)
        temporary_zip.replace(destination)
    return counts


def split_year_zips(
    *,
    aggregate_path: Path,
    output_dir: Path,
    prefecture: Prefecture,
    from_year: int,
    to_year: int,
    force: bool,
) -> dict[int, int]:
    years = list(range(from_year, to_year + 1))
    counts = dict.fromkeys(years, 0)
    with zipfile.ZipFile(aggregate_path) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"expected one CSV in {aggregate_path}, found {len(csv_names)}")
        with tempfile.TemporaryDirectory(dir=output_dir) as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            handles = {}
            writers = {}
            try:
                with archive.open(csv_names[0]) as source_binary:
                    import io

                    source = io.TextIOWrapper(source_binary, encoding="cp932", newline="")
                    reader = csv.DictReader(source)
                    if not reader.fieldnames or not REQUIRED_CSV_COLUMNS.issubset(
                        reader.fieldnames
                    ):
                        raise ValueError("downloaded CSV is missing station or transaction columns")
                    for year in years:
                        csv_path = temp_dir / internal_csv_name(prefecture, year)
                        handle = csv_path.open("w", encoding="cp932", newline="")
                        handles[year] = handle
                        writer = csv.DictWriter(handle, fieldnames=reader.fieldnames)
                        writer.writeheader()
                        writers[year] = writer

                    for row in reader:
                        match = re.search(r"(\d{4})", row.get("取引時期", ""))
                        if not match:
                            continue
                        year = int(match.group(1))
                        if year in writers:
                            writers[year].writerow(row)
                            counts[year] += 1
            finally:
                for handle in handles.values():
                    handle.close()

            for year in years:
                destination = year_zip_path(output_dir, prefecture, year)
                if destination.exists() and not force and is_valid_year_zip(destination):
                    continue
                temporary_zip = destination.with_suffix(".zip.tmp")
                with zipfile.ZipFile(
                    temporary_zip,
                    "w",
                    compression=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                ) as output_zip:
                    csv_path = temp_dir / internal_csv_name(prefecture, year)
                    output_zip.write(csv_path, arcname=csv_path.name)
                temporary_zip.replace(destination)
                if not is_valid_year_zip(destination):
                    raise zipfile.BadZipFile(f"invalid year ZIP created: {destination}")
    return counts


def internal_csv_name(prefecture: Prefecture, year: int) -> str:
    first_quarter = 3 if year == 2005 else 1
    return f"{prefecture.csv_prefix}_{year}{first_quarter}_{year}4.csv"


def year_zip_path(output_dir: Path, prefecture: Prefecture, year: int) -> Path:
    return output_dir / f"mlit_{prefecture.slug}_{year}.zip"


def is_valid_year_zip(path: Path) -> bool:
    if not path.exists() or not zipfile.is_zipfile(path):
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                return False
            csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(csv_names) != 1:
                return False
            with archive.open(csv_names[0]) as source:
                header = source.readline().decode("cp932")
            return REQUIRED_CSV_COLUMNS.issubset(next(csv.reader([header])))
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile):
        return False


def sync_checklist(todo_file: Path, output_dir: Path, from_year: int, to_year: int) -> None:
    years = range(from_year, to_year + 1)
    statuses = [
        (prefecture, year, is_valid_year_zip(year_zip_path(output_dir, prefecture, year)))
        for prefecture in PREFECTURES
        for year in years
    ]
    completed = sum(done for _, _, done in statuses)
    lines = [
        CHECKLIST_START,
        "## 国交省CSVダウンロード状況",
        "",
        f"完了: {completed} / {len(statuses)}",
        "",
    ]
    current_code = None
    for prefecture, year, done in statuses:
        if current_code != prefecture.code:
            if current_code is not None:
                lines.append("")
            lines.append(f"### {prefecture.name} ({prefecture.slug})")
            current_code = prefecture.code
        lines.append(f"- [{'x' if done else ' '}] {year}")
    lines.extend(["", CHECKLIST_END])
    block = "\n".join(lines)

    original = todo_file.read_text(encoding="utf-8") if todo_file.exists() else "# TODO\n"
    if CHECKLIST_START in original and CHECKLIST_END in original:
        before, remainder = original.split(CHECKLIST_START, 1)
        _, after = remainder.split(CHECKLIST_END, 1)
        updated = f"{before.rstrip()}\n\n{block}{after}"
    else:
        updated = f"{original.rstrip()}\n\n{block}\n"
    todo_file.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

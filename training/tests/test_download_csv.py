from __future__ import annotations

import csv
import io
import zipfile

from collect.download_csv import (
    CHECKLIST_END,
    CHECKLIST_START,
    PREFECTURES,
    build_year_chunks,
    create_empty_year_zips,
    is_valid_year_zip,
    resolve_prefectures,
    split_year_zips,
    sync_checklist,
    year_zip_path,
)


def test_split_year_zips_and_sync_checklist(tmp_path) -> None:
    tokyo = resolve_prefectures(["tokyo"])[0]
    aggregate = tmp_path / "aggregate.zip"
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=[
            "種類",
            "取引時期",
            "最寄駅：名称",
            "最寄駅：距離（分）",
            "取引価格（総額）",
        ],
    )
    writer.writeheader()
    writer.writerow(
        {
            "種類": "中古マンション等",
            "取引時期": "2024年第4四半期",
            "最寄駅：名称": "東京",
            "最寄駅：距離（分）": "8",
            "取引価格（総額）": "50000000",
        }
    )
    writer.writerow(
        {
            "種類": "中古マンション等",
            "取引時期": "2025年第1四半期",
            "最寄駅：名称": "東京",
            "最寄駅：距離（分）": "10",
            "取引価格（総額）": "52000000",
        }
    )
    with zipfile.ZipFile(aggregate, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Tokyo_20241_20254.csv", csv_buffer.getvalue().encode("cp932"))

    counts = split_year_zips(
        aggregate_path=aggregate,
        output_dir=tmp_path,
        prefecture=tokyo,
        from_year=2024,
        to_year=2025,
        force=False,
    )

    assert counts == {2024: 1, 2025: 1}
    assert is_valid_year_zip(year_zip_path(tmp_path, tokyo, 2024))
    assert is_valid_year_zip(year_zip_path(tmp_path, tokyo, 2025))

    todo = tmp_path / "TODO.md"
    todo.write_text("# TODO\n\n既存タスク\n", encoding="utf-8")
    sync_checklist(todo, tmp_path, 2024, 2025)
    content = todo.read_text(encoding="utf-8")
    assert "既存タスク" in content
    assert CHECKLIST_START in content
    assert CHECKLIST_END in content
    assert "完了: 2 / 94" in content
    assert "### 東京都 (tokyo)\n- [x] 2024\n- [x] 2025" in content


def test_resolve_all_prefectures() -> None:
    assert resolve_prefectures(["all"]) == PREFECTURES
    assert resolve_prefectures(["13", "kanagawa"])[0].slug == "tokyo"


def test_build_year_chunks_handles_gaps() -> None:
    assert build_year_chunks([2005, 2006, 2007, 2010, 2011, 2012], 2) == [
        (2005, 2006),
        (2007, 2007),
        (2010, 2011),
        (2012, 2012),
    ]


def test_create_empty_year_zip(tmp_path) -> None:
    chiba = resolve_prefectures(["chiba"])[0]
    counts = create_empty_year_zips(
        output_dir=tmp_path,
        prefecture=chiba,
        from_year=2005,
        to_year=2005,
        force=False,
    )

    output = year_zip_path(tmp_path, chiba, 2005)
    assert counts == {2005: 0}
    assert is_valid_year_zip(output)

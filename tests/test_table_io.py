from __future__ import annotations

import time
import tracemalloc
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from virtual_array import table_io
from virtual_array.server import create_app
from virtual_array.table_io import (
    MAX_CSV_LINE_CHARS,
    MAX_TABLE_COLUMNS,
    MAX_TABLE_ROWS,
    MAX_XLSX_UNCOMPRESSED_BYTES,
    read_csv_rows,
    read_spreadsheet_rows,
)

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    "</Types>"
)
_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
    "</Relationships>"
)
_WORKBOOK = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
)
_WORKBOOK_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
    "</Relationships>"
)


def write_xlsx(path: Path, rows: int, cells_per_row: int = 2) -> Path:
    """A valid workbook whose sheet XML is streamed, so huge sheets stay cheap to build."""
    row_xml = ("<row>" + "<c><v>1</v></c>" * cells_per_row + "</row>").encode()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("xl/workbook.xml", _WORKBOOK)
        archive.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        with archive.open("xl/worksheets/sheet1.xml", "w", force_zip64=True) as sheet:
            sheet.write(b'<?xml version="1.0" encoding="UTF-8"?>'
                        b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>')
            batch = row_xml * 1000
            for _ in range(rows // 1000):
                sheet.write(batch)
            sheet.write(row_xml * (rows % 1000))
            sheet.write(b"</sheetData></worksheet>")
    return path


def test_small_workbook_still_reads(tmp_path) -> None:
    rows = read_spreadsheet_rows(write_xlsx(tmp_path / "ok.xlsx", 10))
    assert rows == [["1", "1"]] * 10


@pytest.fixture()
def small_row_cap(monkeypatch) -> int:
    """Shrink the row cap so the "stops early" behaviour is cheap to test."""
    monkeypatch.setattr(table_io, "MAX_TABLE_ROWS", 5_000)
    return 5_000


def test_compact_xlsx_bomb_stops_early_with_bounded_memory(tmp_path, small_row_cap) -> None:
    # Far more rows than allowed in a tiny file: parsing must stop at the cap.
    path = write_xlsx(tmp_path / "bomb.xlsx", small_row_cap * 40)
    assert path.stat().st_size < 1024 * 1024

    tracemalloc.start()
    start = time.perf_counter()
    try:
        with pytest.raises(ValueError, match="行"):
            read_spreadsheet_rows(path)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 32 * 1024 * 1024
    assert time.perf_counter() - start < 10


def test_xlsx_rejected_by_decompressed_size_before_parsing(tmp_path) -> None:
    rows = MAX_XLSX_UNCOMPRESSED_BYTES // len("<row><c><v>1</v></c><c><v>1</v></c></row>") + 10
    path = write_xlsx(tmp_path / "big.xlsx", rows)
    start = time.perf_counter()
    with pytest.raises(ValueError, match="MB"):
        read_spreadsheet_rows(path)
    assert time.perf_counter() - start < 1


def test_wide_xlsx_row_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="列"):
        read_spreadsheet_rows(write_xlsx(tmp_path / "wide.xlsx", 2, cells_per_row=MAX_TABLE_COLUMNS + 50))


def test_csv_row_count_line_length_and_width_are_bounded(tmp_path) -> None:
    many = tmp_path / "many.csv"
    many.write_text("1,0\n" * (MAX_TABLE_ROWS + 1), encoding="utf-8")
    with pytest.raises(ValueError, match="行"):
        read_csv_rows(many, ",")

    long_line = tmp_path / "long.csv"
    long_line.write_text("1," * (MAX_CSV_LINE_CHARS // 2 + 10) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="KB"):
        read_csv_rows(long_line, ",")

    wide = tmp_path / "wide.csv"
    wide.write_text(",".join(["1"] * (MAX_TABLE_COLUMNS + 1)) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="列"):
        read_csv_rows(wide, ",")

    ok = tmp_path / "ok.csv"
    ok.write_text("theta,gain\n0,1\n", encoding="utf-8")
    assert read_csv_rows(ok, ",") == [["theta", "gain"], ["0", "1"]]


def test_xlsx_bomb_upload_is_a_fast_client_error(tmp_path, small_row_cap) -> None:
    client = TestClient(create_app(data_dir=tmp_path / "data", static_dir=tmp_path / "web"))
    content = write_xlsx(tmp_path / "bomb.xlsx", small_row_cap * 40).read_bytes()
    asset = client.post("/api/assets", files={"file": ("bomb.xlsx", content, "application/octet-stream")}).json()["id"]

    response = client.post("/api/element-pattern/preview", json={"asset": asset})
    assert response.status_code == 422
    assert "行" in response.json()["detail"]

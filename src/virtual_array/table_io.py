from __future__ import annotations

import csv
import posixpath
import re
import zipfile
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"

# Uploaded tables are untrusted and parsed into Python objects (~10x their text
# size), so their shape is bounded, not just their file size. Real patterns and
# dictionaries are thousands of angle rows by at most a few hundred channels; the
# largest realistic table, a 2D dictionary on a 0.5° grid (361 x 121), has ~44k rows.
MAX_TABLE_ROWS = 50_000
MAX_TABLE_COLUMNS = 2048
MAX_CSV_LINE_CHARS = 1024 * 1024
# An XLSX is a zip: bound what it may expand to before any XML is parsed.
MAX_XLSX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
# Text cells (headers, channel names); numeric tables need only a handful.
MAX_SHARED_STRINGS = 200_000


def bounded_rows(rows: Iterable[Sequence[Any]], name: str) -> Iterator[Sequence[Any]]:
    """Yield rows, stopping with ``ValueError`` once the table is implausibly large."""
    for count, row in enumerate(rows, start=1):
        if count > MAX_TABLE_ROWS:
            raise ValueError(f"表格超过 {MAX_TABLE_ROWS:,} 行，不像方向图或字典数据：{name}")
        if len(row) > MAX_TABLE_COLUMNS:
            raise ValueError(f"表格超过 {MAX_TABLE_COLUMNS} 列：{name}")
        yield row


def read_csv_rows(path: str | Path, delimiter: str) -> list[list[str]]:
    """CSV/TSV rows with bounded line length, row count and column count."""
    table_path = Path(path)

    def lines(handle: Iterable[str]) -> Iterator[str]:
        for line in handle:
            # Checked before csv splits it, so one huge line cannot become millions of fields.
            if len(line) > MAX_CSV_LINE_CHARS:
                raise ValueError(f"表格中有超过 {MAX_CSV_LINE_CHARS // 1024} KB 的单行：{table_path.name}")
            yield line

    with table_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [list(row) for row in bounded_rows(csv.reader(lines(handle), delimiter=delimiter), table_path.name)]


def read_text_sample(path: str | Path, size: int = 4096) -> str:
    """The first ``size`` characters, without reading the whole file."""
    with Path(path).open("r", encoding="utf-8-sig", errors="ignore") as handle:
        return handle.read(size)


def read_spreadsheet_rows(path: str | Path) -> list[list[str]]:
    """Rows of the active worksheet as stripped strings.

    Damaged or oversized workbooks raise ``ValueError`` (reported to the user as
    a bad file) instead of leaking zipfile/XML exceptions as server errors.
    """
    workbook_path = Path(path)
    try:
        with zipfile.ZipFile(workbook_path) as archive:
            expanded = sum(info.file_size for info in archive.infolist())
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError(f"无法读取 XLSX/XLSM 文件（文件已损坏或不是 Excel 工作簿）：{workbook_path.name}") from exc
    if expanded > MAX_XLSX_UNCOMPRESSED_BYTES:
        raise ValueError(
            f"XLSX/XLSM 文件解压后超过 {MAX_XLSX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB，请另存为 CSV：{workbook_path.name}"
        )
    return read_xlsx_rows(workbook_path)


def read_xlsx_rows(path: str | Path) -> list[list[str]]:
    """Stream the active worksheet of an XLSX/XLSM workbook.

    Supports shared strings, inline strings, cached formula values, booleans and
    numbers. The sheet XML is parsed incrementally and reading stops as soon as
    the table exceeds its bounds. (openpyxl is not used here: for a sheet without
    a <dimension> element it scans the whole sheet before yielding a single row.)
    """
    workbook_path = Path(path)
    try:
        with zipfile.ZipFile(workbook_path) as archive:
            shared_strings = _read_shared_strings(archive, workbook_path.name)
            sheet_path = _active_sheet_path(archive)
            with archive.open(sheet_path) as sheet:
                return [list(row) for row in bounded_rows(_iter_sheet_rows(sheet, shared_strings, workbook_path.name), workbook_path.name)]
    except ValueError:
        raise
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError, OSError, EOFError) as exc:
        raise ValueError(f"无法读取 XLSX/XLSM 文件（文件已损坏或结构不完整）：{workbook_path.name}") from exc


def _iter_sheet_rows(sheet: Any, shared_strings: list[str], name: str) -> Iterator[list[str]]:
    row_tag = f"{{{NS_MAIN}}}row"
    cell_tag = f"{{{NS_MAIN}}}c"
    for _event, element in ElementTree.iterparse(sheet, events=("end",)):
        if element.tag != row_tag:
            continue
        values: list[str] = []
        next_column = 0
        for cell in element.iter(cell_tag):
            column_index = _cell_column_index(cell.get("r"))
            if column_index is None:
                column_index = next_column
            if column_index >= MAX_TABLE_COLUMNS:
                raise ValueError(f"表格超过 {MAX_TABLE_COLUMNS} 列：{name}")
            while len(values) < column_index:
                values.append("")
            values.append(_cell_text(cell, shared_strings).strip())
            next_column = column_index + 1
        element.clear()  # free the parsed row before reading the next one
        while values and values[-1] == "":
            values.pop()
        # Empty rows are yielded too so they count against the row limit; callers
        # drop blank rows themselves.
        yield values


def _read_shared_strings(archive: zipfile.ZipFile, name: str) -> list[str]:
    try:
        source = archive.open("xl/sharedStrings.xml")
    except KeyError:
        return []
    item_tag = f"{{{NS_MAIN}}}si"
    text_tag = f"{{{NS_MAIN}}}t"
    strings: list[str] = []
    with source:
        try:
            for _event, element in ElementTree.iterparse(source, events=("end",)):
                if element.tag != item_tag:
                    continue
                strings.append("".join(text.text or "" for text in element.iter(text_tag)))
                element.clear()
                if len(strings) > MAX_SHARED_STRINGS:
                    raise ValueError(f"XLSX 共享字符串超过 {MAX_SHARED_STRINGS:,} 条：{name}")
        except ElementTree.ParseError as exc:
            raise ValueError("XLSX sharedStrings.xml 解析失败。") from exc
    return strings


def _active_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    sheets = workbook_root.findall(f".//{{{NS_MAIN}}}sheets/{{{NS_MAIN}}}sheet")
    if not sheets:
        return "xl/worksheets/sheet1.xml"

    active_index = 0
    workbook_view = workbook_root.find(f".//{{{NS_MAIN}}}bookViews/{{{NS_MAIN}}}workbookView")
    if workbook_view is not None:
        try:
            active_index = int(workbook_view.get("activeTab", "0"))
        except ValueError:
            active_index = 0
    active_index = max(0, min(active_index, len(sheets) - 1))
    relationship_id = sheets[active_index].get(f"{{{NS_REL}}}id")
    if not relationship_id:
        return "xl/worksheets/sheet1.xml"

    rel_root = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for rel in rel_root.findall(f"{{{NS_PACKAGE_REL}}}Relationship"):
        if rel.get("Id") != relationship_id:
            continue
        target = rel.get("Target", "")
        if target.startswith("/"):
            return target.lstrip("/")
        return posixpath.normpath(posixpath.join("xl", target))
    return "xl/worksheets/sheet1.xml"


def _cell_text(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(
            text.text or "" for text in cell.findall(f".//{{{NS_MAIN}}}is//{{{NS_MAIN}}}t")
        )

    value = cell.find(f"{{{NS_MAIN}}}v")
    raw = "" if value is None or value.text is None else value.text
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return ""
    if cell_type == "b":
        return "TRUE" if raw == "1" else "FALSE"
    return raw


def _cell_column_index(reference: str | None) -> int | None:
    if not reference:
        return None
    match = re.match(r"([A-Za-z]+)", reference)
    if match is None:
        return None
    index = 0
    for letter in match.group(1).upper():
        index = index * 26 + (ord(letter) - ord("A") + 1)
    return index - 1

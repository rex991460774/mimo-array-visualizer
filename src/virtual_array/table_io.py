from __future__ import annotations

import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def read_xlsx_rows(path: str | Path) -> list[list[str]]:
    """Read the active worksheet from a simple XLSX/XLSM workbook.

    This is a small dependency-free fallback for table-shaped files. It supports
    shared strings, inline strings, cached formula values, booleans, and numbers.
    """
    workbook_path = Path(path)
    try:
        with zipfile.ZipFile(workbook_path) as archive:
            shared_strings = _read_shared_strings(archive)
            sheet_path = _active_sheet_path(archive)
            root = ElementTree.fromstring(archive.read(sheet_path))
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise ValueError(f"无法读取 XLSX/XLSM 文件：{workbook_path.name}") from exc

    rows: list[list[str]] = []
    for row in root.findall(f".//{{{NS_MAIN}}}sheetData/{{{NS_MAIN}}}row"):
        values: list[str] = []
        next_column = 0
        for cell in row.findall(f"{{{NS_MAIN}}}c"):
            column_index = _cell_column_index(cell.get("r"))
            if column_index is None:
                column_index = next_column
            while len(values) < column_index:
                values.append("")
            values.append(_cell_text(cell, shared_strings).strip())
            next_column = column_index + 1
        while values and values[-1] == "":
            values.pop()
        if values and any(value for value in values):
            rows.append(values)
    return rows


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    except ElementTree.ParseError as exc:
        raise ValueError("XLSX sharedStrings.xml 解析失败。") from exc

    strings: list[str] = []
    for item in root.findall(f"{{{NS_MAIN}}}si"):
        strings.append("".join(text.text or "" for text in item.findall(f".//{{{NS_MAIN}}}t")))
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

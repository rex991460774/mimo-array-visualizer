from __future__ import annotations

import numpy as np
import pytest
from openpyxl import Workbook

from virtual_array.analysis import dbf_azimuth_spectrum_bank
from virtual_array.dbf_dictionary import (
    DBF_DICT_CUSTOM,
    DbfDictionaryConfig,
    load_dbf_dictionary_table,
)
from virtual_array.geometry import AntennaArray


def test_loads_virtual_channel_phase_dictionary_csv(tmp_path) -> None:
    path = tmp_path / "virtual-dict.csv"
    path.write_text(
        "Angle,V1,V2\n"
        "-30,0,-90\n"
        "0,0,0\n"
        "30,0,90\n",
        encoding="utf-8",
    )
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 1], rx_y=[0, 0])

    table = load_dbf_dictionary_table(path, array)
    config = DbfDictionaryConfig(mode=DBF_DICT_CUSTOM, custom_table=table)
    matrix = config.scan_matrix(array, np.array([30.0]), axis="azimuth")

    assert matrix.shape == (1, 2)
    assert matrix[0, 0] == pytest.approx(1.0 + 0.0j)
    assert matrix[0, 1] == pytest.approx(np.exp(-1j * np.radians(90.0)))


def test_loads_physical_tx_rx_dictionary_xlsx_and_combines_virtual_channels(tmp_path) -> None:
    path = tmp_path / "physical-dict.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Angle", "Tx1", "Rx1", "Rx2"])
    sheet.append([0, 10, 20, 30])
    workbook.save(path)
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 1], rx_y=[0, 0])

    table = load_dbf_dictionary_table(path, array)
    config = DbfDictionaryConfig(mode=DBF_DICT_CUSTOM, custom_table=table)
    matrix = config.scan_matrix(array, np.array([0.0]), axis="azimuth")

    expected = np.conjugate(
        np.exp(1j * np.radians(np.array([30.0, 40.0], dtype=float)))
    )
    assert matrix.shape == (1, 2)
    assert matrix[0] == pytest.approx(expected)


def test_tx_rx_headers_win_when_physical_and_virtual_column_counts_match(tmp_path) -> None:
    path = tmp_path / "physical-2t2r.csv"
    path.write_text(
        "Angle,Tx1,Tx2,Rx1,Rx2\n"
        "0,0,10,20,30\n",
        encoding="utf-8",
    )
    array = AntennaArray.from_xy(
        tx_x=[0, 1],
        tx_y=[0, 0],
        rx_x=[0, 1],
        rx_y=[0, 0],
    )

    table = load_dbf_dictionary_table(path, array)
    config = DbfDictionaryConfig(mode=DBF_DICT_CUSTOM, custom_table=table)
    matrix = config.scan_matrix(array, np.array([0.0]), axis="azimuth")

    expected_phases = np.array([20.0, 30.0, 30.0, 40.0])
    assert table.channel_mode == "physical"
    assert matrix[0] == pytest.approx(np.conjugate(np.exp(1j * np.radians(expected_phases))))


def test_hfss_phase_style_metadata_columns_are_not_channels(tmp_path) -> None:
    path = tmp_path / "hfss-phase.csv"
    path.write_text(
        '"Freq [GHz]","Phi [deg]","Theta [deg]","cang_deg(rETheta) [deg]",'
        '"cang_deg(rETheta)_1 [deg]","cang_deg(rETheta)_2 [deg]",'
        '"cang_deg(rETheta)_3 [deg]"\n'
        "24.125,90,0,0,10,20,30\n",
        encoding="utf-8",
    )
    array = AntennaArray.from_xy(
        tx_x=[0, 1],
        tx_y=[0, 0],
        rx_x=[0, 1],
        rx_y=[0, 0],
    )

    table = load_dbf_dictionary_table(path, array)
    config = DbfDictionaryConfig(mode=DBF_DICT_CUSTOM, custom_table=table)
    matrix = config.scan_matrix(array, np.array([0.0]), axis="azimuth")

    expected_phases = np.array([20.0, 30.0, 30.0, 40.0])
    assert table.channel_mode == "physical"
    assert table.column_names == (
        "cang_deg(rETheta) [deg]",
        "cang_deg(rETheta)_1 [deg]",
        "cang_deg(rETheta)_2 [deg]",
        "cang_deg(rETheta)_3 [deg]",
    )
    assert matrix[0] == pytest.approx(np.conjugate(np.exp(1j * np.radians(expected_phases))))


def test_ambiguous_2t2r_virtual_headers_still_load_as_virtual(tmp_path) -> None:
    path = tmp_path / "virtual-2t2r.csv"
    path.write_text(
        "Angle,V1,V2,V3,V4\n"
        "0,0,10,20,30\n",
        encoding="utf-8",
    )
    array = AntennaArray.from_xy(
        tx_x=[0, 1],
        tx_y=[0, 0],
        rx_x=[0, 1],
        rx_y=[0, 0],
    )

    table = load_dbf_dictionary_table(path, array)
    config = DbfDictionaryConfig(mode=DBF_DICT_CUSTOM, custom_table=table)
    matrix = config.scan_matrix(array, np.array([0.0]), axis="azimuth")

    assert table.channel_mode == "virtual"
    assert matrix[0] == pytest.approx(
        np.conjugate(np.exp(1j * np.radians(np.array([0.0, 10.0, 20.0, 30.0]))))
    )


def test_custom_dictionary_uses_separate_azimuth_and_elevation_files(tmp_path) -> None:
    az_path = tmp_path / "az-dict.csv"
    az_path.write_text(
        "Angle,V1,V2\n"
        "0,0,0\n"
        "30,0,90\n",
        encoding="utf-8",
    )
    el_path = tmp_path / "el-dict.csv"
    el_path.write_text(
        "Angle,V1,V2\n"
        "0,0,0\n"
        "30,0,45\n",
        encoding="utf-8",
    )
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 1], rx_y=[0, 0])
    az_table = load_dbf_dictionary_table(az_path, array)
    el_table = load_dbf_dictionary_table(el_path, array)
    config = DbfDictionaryConfig(
        mode=DBF_DICT_CUSTOM,
        custom_azimuth_table=az_table,
        custom_elevation_table=el_table,
    )

    az_matrix = config.scan_matrix(array, np.array([30.0]), axis="azimuth")
    el_matrix = config.scan_matrix(array, np.array([30.0]), axis="elevation")

    assert az_matrix[0, 1] == pytest.approx(np.exp(-1j * np.radians(90.0)))
    assert el_matrix[0, 1] == pytest.approx(np.exp(-1j * np.radians(45.0)))


def test_custom_2d_dictionary_combines_separate_axis_files(tmp_path) -> None:
    az_path = tmp_path / "az-dict.csv"
    az_path.write_text(
        "Angle,V1,V2\n"
        "0,0,0\n"
        "30,0,90\n",
        encoding="utf-8",
    )
    el_path = tmp_path / "el-dict.csv"
    el_path.write_text(
        "Angle,V1,V2\n"
        "0,0,0\n"
        "20,0,45\n",
        encoding="utf-8",
    )
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 1], rx_y=[0, 0])
    config = DbfDictionaryConfig(
        mode=DBF_DICT_CUSTOM,
        custom_azimuth_table=load_dbf_dictionary_table(az_path, array),
        custom_elevation_table=load_dbf_dictionary_table(el_path, array),
    )

    matrix = config.scan_matrix_2d(
        array,
        np.array([30.0]),
        np.array([20.0]),
    )

    assert matrix[0, 1] == pytest.approx(np.exp(-1j * np.radians(135.0)))


def test_custom_dictionary_integrates_with_dbf_spectrum_bank(tmp_path) -> None:
    path = tmp_path / "ideal-custom.csv"
    path.write_text(
        "Angle,V1,V2\n"
        "-90,0,-180\n"
        "0,0,0\n"
        "90,0,180\n",
        encoding="utf-8",
    )
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 1], rx_y=[0, 0])
    table = load_dbf_dictionary_table(path, array)
    config = DbfDictionaryConfig(mode=DBF_DICT_CUSTOM, custom_table=table)

    true_angles, scan_angles, spectra_db = dbf_azimuth_spectrum_bank(
        array,
        true_angles_deg=np.array([30.0]),
        scan_angles_deg=np.array([-30.0, 0.0, 30.0]),
        dbf_dictionary=config,
    )

    peak_index = int(np.argmax(spectra_db[0]))
    assert true_angles[0] == pytest.approx(30.0)
    assert scan_angles[peak_index] == pytest.approx(30.0)

from __future__ import annotations

import numpy as np
import pytest
from openpyxl import Workbook

from virtual_array.analysis import dbf_azimuth_spectrum_bank
from virtual_array.dbf_dictionary import (
    DBF_DICT_CHANNEL_PATTERN,
    DBF_DICT_CUSTOM,
    DbfDictionaryConfig,
    load_dbf_dictionary_table,
)
from virtual_array.element_pattern import (
    PATTERN_KIND_PHASE,
    PATTERN_PLANE_HORIZONTAL,
    ChannelPatternSet,
    PatternSeries,
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

    assert matrix.shape == (1, 2)
    assert matrix[0] == pytest.approx(
        np.conjugate(np.exp(1j * np.radians(np.array([30.0, 40.0]))))
    )


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

    assert table.channel_mode == "physical"
    assert matrix[0] == pytest.approx(
        np.conjugate(np.exp(1j * np.radians(np.array([20.0, 30.0, 30.0, 40.0]))))
    )


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

    assert table.channel_mode == "physical"
    assert table.column_names == (
        "cang_deg(rETheta) [deg]",
        "cang_deg(rETheta)_1 [deg]",
        "cang_deg(rETheta)_2 [deg]",
        "cang_deg(rETheta)_3 [deg]",
    )
    assert matrix[0] == pytest.approx(
        np.conjugate(np.exp(1j * np.radians(np.array([20.0, 30.0, 30.0, 40.0]))))
    )


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


def test_custom_dictionary_phase_columns_are_zero_degree_calibrated(tmp_path) -> None:
    path = tmp_path / "offset-phase.csv"
    path.write_text(
        "Angle,V1,V2\n"
        "-30,10,110\n"
        "0,20,120\n"
        "30,30,130\n",
        encoding="utf-8",
    )
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 1], rx_y=[0, 0])

    table = load_dbf_dictionary_table(path, array)
    config = DbfDictionaryConfig(
        mode=DBF_DICT_CUSTOM,
        custom_table=table,
        custom_zero_phase_calibrated=True,
    )
    matrix = config.scan_matrix(array, np.array([30.0]), axis="azimuth")

    assert matrix[0] == pytest.approx(
        np.conjugate(np.exp(1j * np.radians(np.array([10.0, 10.0]))))
    )


def test_custom_dictionary_complex_values_keep_amplitude_after_zero_calibration(
    tmp_path,
) -> None:
    path = tmp_path / "complex-offset.csv"
    path.write_text(
        "Angle,V1,V2\n"
        "0,2∠30,3∠-10\n"
        "30,4∠60,5∠20\n",
        encoding="utf-8",
    )
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 1], rx_y=[0, 0])

    table = load_dbf_dictionary_table(path, array)
    config = DbfDictionaryConfig(
        mode=DBF_DICT_CUSTOM,
        custom_table=table,
        custom_zero_phase_calibrated=True,
    )
    matrix = config.scan_matrix(array, np.array([30.0]), axis="azimuth")

    expected_response = np.array([4.0, 5.0]) * np.exp(1j * np.radians(30.0))
    assert matrix[0] == pytest.approx(np.conjugate(expected_response))


def test_custom_dictionary_can_reverse_imported_phase(tmp_path) -> None:
    path = tmp_path / "reverse-phase.csv"
    path.write_text(
        "Angle,V1,V2\n"
        "0,0,90\n",
        encoding="utf-8",
    )
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 1], rx_y=[0, 0])

    table = load_dbf_dictionary_table(path, array)
    config = DbfDictionaryConfig(
        mode=DBF_DICT_CUSTOM,
        custom_table=table,
        custom_phase_reversed=True,
    )
    matrix = config.scan_matrix(array, np.array([0.0]), axis="azimuth")

    assert matrix[0, 0] == pytest.approx(1.0 + 0.0j)
    assert matrix[0, 1] == pytest.approx(np.exp(1j * np.radians(90.0)))


def test_channel_pattern_dictionary_uses_zero_degree_phase_reference() -> None:
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 1], rx_y=[0, 0])
    phase_series = PatternSeries(
        name="rx2-phase",
        source_path="phase.csv",
        angle_column="Theta",
        value_column="phase",
        value_kind=PATTERN_KIND_PHASE,
        angles_deg=np.array([0.0, 30.0]),
        values=np.array([45.0, 135.0]),
    )
    channel_patterns = ChannelPatternSet()
    channel_patterns.set_series(
        "Rx2",
        PATTERN_KIND_PHASE,
        PATTERN_PLANE_HORIZONTAL,
        phase_series,
    )

    config = DbfDictionaryConfig(mode=DBF_DICT_CHANNEL_PATTERN)
    matrix = config.scan_matrix(
        array,
        np.array([30.0]),
        axis="azimuth",
        channel_patterns=channel_patterns,
    )

    assert matrix[0] == pytest.approx(
        np.conjugate(np.exp(1j * np.radians(np.array([0.0, 90.0]))))
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


def test_custom_dictionary_missing_axis_falls_back_to_ideal(tmp_path) -> None:
    az_path = tmp_path / "az-dict.csv"
    az_path.write_text(
        "Angle,V1,V2\n"
        "0,0,0\n"
        "30,0,90\n",
        encoding="utf-8",
    )
    array = AntennaArray.from_xy(tx_x=[0], tx_y=[0], rx_x=[0, 0], rx_y=[0, 1])
    config = DbfDictionaryConfig(
        mode=DBF_DICT_CUSTOM,
        custom_azimuth_table=load_dbf_dictionary_table(az_path, array),
    )
    ideal_config = DbfDictionaryConfig()

    elevation_matrix = config.scan_matrix(array, np.array([30.0]), axis="elevation")
    ideal_elevation_matrix = ideal_config.scan_matrix(
        array,
        np.array([30.0]),
        axis="elevation",
    )
    matrix_2d = config.scan_matrix_2d(
        array,
        np.array([30.0]),
        np.array([30.0]),
    )

    assert np.allclose(elevation_matrix, ideal_elevation_matrix)
    assert matrix_2d[0, 1] == pytest.approx(np.exp(-1j * np.radians(180.0)))


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

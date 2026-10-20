from __future__ import annotations

import base64
import io
import json
import time
import zipfile
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from virtual_array.analysis import (
    Dbf2dScanner,
    EvaluationSettings,
    dbf_2d_spectrum,
    evaluate_dbf_axis,
)
from virtual_array.element_pattern import (
    PATTERN_KIND_PHASE,
    PATTERN_PLANE_HORIZONTAL,
    ChannelPatternSet,
    PatternSeries,
)
from virtual_array.examples.case4_5tx7rx_sel import build_array
from virtual_array.geometry import AntennaArray
from virtual_array.project import default_project
from virtual_array.server import create_app

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
PATTERN_CSV = EXAMPLES / "A8H_8horn_Realized Gain EH plane.csv"


@pytest.fixture()
def client(tmp_path) -> TestClient:
    return TestClient(create_app(data_dir=tmp_path / "data", static_dir=tmp_path / "web"))


@pytest.fixture()
def project() -> dict:
    return default_project().model_dump(mode="json")


def small_project() -> dict:
    project = default_project().model_dump(mode="json")
    project["layout"] = {
        "tx": [{"x": 0, "y": 0}, {"x": 2, "y": 0}],
        "rx": [{"x": 0, "y": -2}, {"x": 0.5, "y": -2}, {"x": 1, "y": -1.5}],
    }
    return project


def decode(payload: dict) -> np.ndarray:
    data = base64.b64decode(payload["data"])
    return np.frombuffer(data, dtype=payload["dtype"]).reshape(payload["shape"])


def upload(client: TestClient, name: str, content: bytes) -> str:
    response = client.post("/api/assets", files={"file": (name, content, "text/csv")})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def wait_for_job(client: TestClient, job: dict, timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(f"/api/jobs/{job['id']}").json()
        if status["status"] in {"succeeded", "failed", "cancelled"}:
            return status
        time.sleep(0.2)
    raise AssertionError("export job timed out")


# ── Core: reusable 2D scanner ────────────────────────────────────────


def test_dbf_2d_scanner_reuse_matches_fresh_spectrum_with_channel_phase() -> None:
    array = AntennaArray.from_xy(tx_x=[0, 3], tx_y=[0, 0], rx_x=[0, 1, 2], rx_y=[0, 2, 0])
    angles = np.array([-60.0, 0.0, 60.0])
    patterns = ChannelPatternSet()
    for index, name in enumerate(["Tx1", "Rx2"]):
        patterns.set_series(
            name,
            PATTERN_KIND_PHASE,
            PATTERN_PLANE_HORIZONTAL,
            PatternSeries(
                name="phase.csv",
                source_path="phase.csv",
                angle_column="Theta",
                value_column=f"ch{index}",
                value_kind=PATTERN_KIND_PHASE,
                angles_deg=angles,
                values=angles * (index + 1),
            ),
        )
    scanner = Dbf2dScanner(array, channel_patterns=patterns)

    for true_az, true_el in [(0.0, 0.0), (20.0, -10.0), (-45.0, 30.0)]:
        _az, _el, expected = dbf_2d_spectrum(
            array, true_az, true_el, channel_patterns=patterns
        )
        assert np.array_equal(scanner.spectrum_db(true_az, true_el), expected)


# ── API ──────────────────────────────────────────────────────────────


def test_health_and_config(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"
    config = client.get("/api/config").json()
    assert config["limits"]["max_tx"] == 16
    assert config["default_project"]["version"] == 2


def test_root_explains_missing_web_client(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "npm run build" in response.text


def test_static_client_is_served_with_spa_fallback(tmp_path) -> None:
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (web / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    client = TestClient(create_app(data_dir=tmp_path / "data", static_dir=web))

    assert client.get("/").text == "<html>app</html>"
    assert client.get("/projects/123").text == "<html>app</html>"
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/api/nope").status_code == 404


def test_evaluate_reports_metrics_capability_and_virtual_points(client, project) -> None:
    response = client.post("/api/evaluate", json={"project": project})

    assert response.status_code == 200
    result = response.json()
    assert result["summary"]["virtual_count"] == 64
    assert result["summary"]["x_aperture_lambda"] == pytest.approx(37.5)
    assert result["capability"] == {"azimuth": True, "elevation": True, "two_d": True}
    assert len(result["virtual_points"]) == result["summary"]["unique_count"]
    assert result["angle"]["azimuth"]["no_fold_width"] > 0
    assert result["pattern_status"] == {"amplitude": "ideal", "phase": "ideal"}
    assert result["wavelength_mm"] == pytest.approx(299.792458 / 77.0)


def test_evaluate_marks_missing_elevation_aperture(client) -> None:
    project = default_project().model_dump(mode="json")
    project["layout"] = {"tx": [{"x": 0, "y": 0}], "rx": [{"x": 0, "y": 0}, {"x": 1, "y": 0}]}

    result = client.post("/api/evaluate", json={"project": project}).json()

    assert result["capability"] == {"azimuth": True, "elevation": False, "two_d": False}
    assert result["angle"]["elevation"] is None


def test_evaluate_rejects_invalid_project(client, project) -> None:
    project["frequency_ghz"] = -1

    response = client.post("/api/evaluate", json={"project": project})

    assert response.status_code == 422
    assert "frequency_ghz" in response.json()["detail"]


def test_dbf_bank_matches_core_computation(client, project) -> None:
    result = client.post("/api/dbf/bank", json={"project": project, "axis": "azimuth"}).json()

    expected = evaluate_dbf_axis(build_array(), "azimuth", EvaluationSettings())
    spectra = decode(result["spectra_db"])
    # Default FOV ±75° (true angles) with a 10° search guard (scan ±85°).
    assert spectra.shape == (151, 171)
    assert np.allclose(spectra, expected.spectra_db, atol=1e-4)
    assert len(result["frames"]["errors"]) == 151
    assert result["frames"]["quality"][75] == "normal"


def test_dbf_2d_returns_frames(client, project) -> None:
    response = client.post(
        "/api/dbf/2d",
        json={"project": project, "frames": [{"azimuth": 10, "elevation": 0}]},
    )

    assert response.status_code == 200
    frame = response.json()["frames"][0]
    # Scan grid: azimuth ±85°, elevation ±25° (FOV plus search guard).
    assert decode(frame["spectrum_db"]).shape == (51, 171)
    assert frame["peak_azimuth"] == pytest.approx(10.0)


def test_auto_layout_endpoint(client) -> None:
    layout = client.post("/api/layout/auto", json={"tx_count": 2, "rx_count": 4}).json()
    assert len(layout["tx"]) == 2 and len(layout["rx"]) == 4
    assert client.post("/api/layout/auto", json={"tx_count": 17, "rx_count": 4}).status_code == 422


def test_element_pattern_upload_preview_and_evaluate(client, project) -> None:
    asset = upload(client, PATTERN_CSV.name, PATTERN_CSV.read_bytes())

    preview = client.post("/api/element-pattern/preview", json={"asset": asset}).json()
    swapped = client.post(
        "/api/element-pattern/preview", json={"asset": asset, "swap_axes": True}
    ).json()

    assert preview["name"] == PATTERN_CSV.name
    assert preview["elevation_column"] is not None
    assert swapped["horizontal_column"] == preview["elevation_column"]
    project["element_pattern"] = {"asset": asset}
    result = client.post("/api/evaluate", json={"project": project}).json()
    assert result["pattern_status"]["amplitude"] == "imported"


def test_asset_upload_rejects_unsupported_files(client) -> None:
    response = client.post("/api/assets", files={"file": ("a.exe", b"x", "application/octet-stream")})
    assert response.status_code == 422
    assert client.get("/api/assets/" + "0" * 64).status_code == 404


def test_channel_pattern_summary_resolves_to_physical_channels(client) -> None:
    project = small_project()
    content = (
        b'"Theta [deg]","cang_deg(a) [deg]","cang_deg(b) [deg]","cang_deg(c) [deg]",'
        b'"cang_deg(d) [deg]","cang_deg(e) [deg]"\n'
        b"-30,1,2,3,4,5\n0,2,3,4,5,6\n30,3,4,5,6,7\n"
    )
    asset = upload(client, "phase-summary.csv", content)

    bindings = client.post(
        "/api/channel-patterns/resolve",
        json={
            "project": project,
            "asset": asset,
            "kind": "phase",
            "plane": "horizontal",
            "target": "physical",
        },
    ).json()

    assert [binding["channel"] for binding in bindings] == ["Tx1", "Tx2", "Rx1", "Rx2", "Rx3"]
    assert [binding["column_index"] for binding in bindings] == [0, 1, 2, 3, 4]
    project["channel_patterns"] = bindings
    result = client.post("/api/evaluate", json={"project": project}).json()
    assert result["pattern_status"] == {"amplitude": "ideal", "phase": "imported"}


def test_channel_pattern_single_channel_and_count_mismatch(client) -> None:
    project = small_project()
    asset = upload(client, "one.csv", b"Theta,gain\n-10,-3\n0,0\n10,-3\n")

    single = client.post(
        "/api/channel-patterns/resolve",
        json={
            "project": project,
            "asset": asset,
            "kind": "amplitude",
            "plane": "elevation",
            "channel": "Rx2",
        },
    ).json()
    mismatch = client.post(
        "/api/channel-patterns/resolve",
        json={"project": project, "asset": asset, "kind": "amplitude", "plane": "horizontal"},
    )

    assert single == [
        {
            "channel": "Rx2",
            "kind": "amplitude",
            "plane": "elevation",
            "asset": asset,
            "column_index": 0,
            "column": "gain",
        }
    ]
    assert mismatch.status_code == 422
    project["channel_patterns"] = single
    status = client.post("/api/evaluate", json={"project": project}).json()["pattern_status"]
    assert status["amplitude"] == "mixed"


def test_custom_dictionary_preview_and_mismatch_error(client) -> None:
    project = small_project()
    header = "Angle," + ",".join(f"V{index}" for index in range(1, 7))
    rows = [f"{angle}," + ",".join("0" for _ in range(6)) for angle in (-90, 0, 90)]
    asset = upload(client, "dict.csv", ("\n".join([header, *rows]) + "\n").encode())
    project["dbf_dictionary"] = {"mode": "custom", "azimuth_asset": asset}

    preview = client.post(
        "/api/dictionary/preview", json={"project": project, "axis": "azimuth"}
    ).json()
    project["layout"]["rx"].pop()
    mismatch = client.post("/api/dbf/bank", json={"project": project, "axis": "azimuth"})

    assert preview["channel_count"] == 6
    assert preview["tables"]["azimuth"]["channel_mode"] == "virtual"
    assert decode(preview["phase_deg"]).shape == (171, 6)
    assert mismatch.status_code == 422
    assert "virtual channel" in mismatch.json()["detail"]


def test_missing_asset_reference_is_reported(client, project) -> None:
    project["element_pattern"] = {"asset": "a" * 64}

    response = client.post("/api/evaluate", json={"project": project})

    assert response.status_code == 422
    assert "missing" in response.json()["detail"]


def test_import_document_accepts_desktop_layout(client) -> None:
    document = (EXAMPLES / "ti.json").read_text(encoding="utf-8")
    import json

    response = client.post("/api/import/document", json={"document": json.loads(document)})

    assert response.status_code == 200
    assert len(response.json()["project"]["layout"]["tx"]) == 8
    bad = client.post("/api/import/document", json={"document": {"version": 9}})
    assert bad.status_code == 422


def test_export_layout_contains_desktop_evaluation_block(client, project) -> None:
    document = client.post("/api/export/layout", json={"project": project}).json()

    assert document["version"] == 1
    assert document["evaluation"]["frequency_ghz"] == 77
    assert document["evaluation"]["virtual_utilization"]["virtual_channels"] == 64


def test_project_library_crud(client, project) -> None:
    created = client.post("/api/projects", json={"project": project}).json()
    project["name"] = "renamed"
    updated = client.put(f"/api/projects/{created['id']}", json={"project": project}).json()
    listing = client.get("/api/projects").json()

    assert updated["project"]["name"] == "renamed"
    assert listing[0]["id"] == created["id"]
    assert listing[0]["tx_count"] == 8
    assert client.delete(f"/api/projects/{created['id']}").status_code == 204
    assert client.get(f"/api/projects/{created['id']}").status_code == 404
    assert client.get("/api/projects/not-an-id").status_code == 404


def test_bundle_round_trip_restores_assets(tmp_path, project) -> None:
    source = TestClient(create_app(data_dir=tmp_path / "a", static_dir=tmp_path / "web"))
    target = TestClient(create_app(data_dir=tmp_path / "b", static_dir=tmp_path / "web"))
    asset = upload(source, PATTERN_CSV.name, PATTERN_CSV.read_bytes())
    project["element_pattern"] = {"asset": asset, "swap_axes": True}

    bundle = source.post("/api/export/bundle", json={"project": project})
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        names = archive.namelist()
    restored = target.post(
        "/api/import/bundle",
        files={"file": ("p.mimo.zip", bundle.content, "application/zip")},
    ).json()

    assert "project.json" in names
    assert restored["missing_assets"] == []
    assert restored["project"]["element_pattern"] == {"asset": asset, "swap_axes": True}
    assert target.post("/api/evaluate", json={"project": restored["project"]}).status_code == 200


def test_angle_error_image_job_produces_png(client) -> None:
    job = client.post("/api/angle-error-image", json={"project": small_project()}).json()

    status = wait_for_job(client, job)
    download = client.get(f"/api/jobs/{job['id']}/download")

    assert status["status"] == "succeeded", status
    assert download.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_report_job_produces_zip_with_pdf_and_data(client) -> None:
    job = client.post(
        "/api/reports",
        json={"project": small_project(), "options": {"title": "测试报告"}},
    ).json()

    status = wait_for_job(client, job)
    download = client.get(f"/api/jobs/{job['id']}/download")

    assert status["status"] == "succeeded", status
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        names = archive.namelist()
    assert "测试报告.pdf" in names
    assert any(name.endswith(".csv") for name in names)


def test_report_rejects_invalid_options(client) -> None:
    response = client.post(
        "/api/reports",
        json={
            "project": small_project(),
            "options": {"include_spectrum_db": False, "include_spectrum_magnitude": False},
        },
    )

    assert response.status_code == 422
    assert client.get("/api/jobs/" + "f" * 32).status_code == 404


# ── Radar-band evaluation ────────────────────────────────────────────


def test_config_exposes_band_presets(client) -> None:
    presets = client.get("/api/config").json()["band_presets"]
    assert presets["60G"] == {"start_ghz": 57.0, "stop_ghz": 64.0, "design_ghz": 60.0}
    assert set(presets) == {"60G", "77G", "92G"}


def test_config_coordinate_limit_matches_project_validation(client, project) -> None:
    limit = client.get("/api/config").json()["limits"]["coordinate_lambda"]
    assert limit == 500

    project["layout"]["tx"][0]["x"] = limit
    assert client.post("/api/evaluate", json={"project": project}).status_code == 200
    project["layout"]["tx"][0]["x"] = limit + 1
    assert client.post("/api/evaluate", json={"project": project}).status_code == 422


def test_evaluate_reports_measured_resolution_fov_and_requirements(client, project) -> None:
    project["requirements"] = {"azimuth_resolution_deg": 1.5, "max_psl_db": -10}

    result = client.post("/api/evaluate", json={"project": project}).json()

    assert result["fov"] == {"azimuth": [-75, 75], "elevation": [-15, 15]}
    assert result["resolution"]["azimuth"]["measured"] == pytest.approx(1.72, abs=0.01)
    assert result["resolution"]["azimuth"]["estimate"] == pytest.approx(1.354, abs=0.01)
    # case4 elevation virtual spacing is λ, but the ±15° FOV is unambiguous.
    assert result["angle"]["elevation"]["no_fold_left"] == -15
    statuses = {(c["key"], c["axis"]): c["status"] for c in result["requirements"]}
    assert statuses[("resolution", "azimuth")] == "fail"
    assert statuses[("unambiguous_fov", "azimuth")] == "pass"
    assert statuses[("unambiguous_fov", "elevation")] == "pass"
    assert statuses[("psl", None)] == "fail"
    assert "resolution_optimistic" in result["notes"]


def test_dbf_bank_is_bounded_by_fov_with_search_guard(client, project) -> None:
    project["fov"] = {"azimuth": [-60, 60], "elevation": [-20, 20]}

    result = client.post("/api/dbf/bank", json={"project": project, "axis": "azimuth"}).json()

    assert result["true_angles"][0] == -60 and result["true_angles"][-1] == 60
    assert result["scan_angles"][0] == -70 and result["scan_angles"][-1] == 70
    assert decode(result["spectra_db"]).shape == (121, 141)
    assert max(abs(e) for e in result["frames"]["errors"]) < 0.01


def test_layout_checks_flag_overlapping_antennas(client) -> None:
    project = small_project()
    project["layout"]["rx"][1] = {"x": 0.25, "y": -2}
    project["layout"]["tx"][1] = {"x": 0, "y": 0}

    checks = client.post("/api/evaluate", json={"project": project}).json()["layout_checks"]

    assert checks[0]["code"] == "coincident"
    assert {checks[0]["a"], checks[0]["b"]} == {"Tx1", "Tx2"}
    assert any(c["code"] == "too_close" and c["distance_lambda"] == 0.25 for c in checks)


def test_band_sweep_scales_electrical_spacing_with_frequency(client) -> None:
    project = default_project().model_dump(mode="json")
    project["frequency_ghz"] = 60.0
    project["band"] = {"preset": "60G", "start_ghz": 57.0, "stop_ghz": 64.0}
    project["fov"] = {"azimuth": [-90, 90], "elevation": [-15, 15]}
    # λ/2 ULA at 60 GHz: unambiguous over ±90° only up to the design frequency.
    project["layout"] = {
        "tx": [{"x": 0, "y": 0}, {"x": 2, "y": 0}],
        "rx": [{"x": 0, "y": 0}, {"x": 0.5, "y": 0}, {"x": 1, "y": 0}, {"x": 1.5, "y": 0}],
    }

    sweep = client.post("/api/band", json={"project": project}).json()

    assert [p["frequency_ghz"] for p in sweep["points"]] == [57.0, 60.0, 64.0]
    assert [p["role"] for p in sweep["points"]] == ["start", "design", "stop"]
    resolution = [p["resolution"]["azimuth"]["value"] for p in sweep["points"]]
    assert resolution[0] > resolution[1] > resolution[2]
    width_at_stop = sweep["points"][2]["angle"]["azimuth"]["no_fold_width"]
    width_at_design = sweep["points"][1]["angle"]["azimuth"]["no_fold_width"]
    assert width_at_stop < width_at_design


def test_compare_summarises_several_projects(client, project) -> None:
    other = small_project()
    other["name"] = "small"

    result = client.post("/api/compare", json={"projects": [project, other]}).json()

    assert [item["name"] for item in result] == [project["name"], "small"]
    assert result[0]["tx_count"] == 8 and result[1]["tx_count"] == 2
    assert result[0]["error"] is None
    assert client.post("/api/compare", json={"projects": []}).status_code == 422


def test_legacy_document_infers_band_from_frequency(client) -> None:
    project = default_project().model_dump(mode="json")
    project.pop("band")
    project["frequency_ghz"] = 60.5

    imported = client.post("/api/import/document", json={"document": project}).json()

    assert imported["project"]["band"]["preset"] == "60G"


def test_report_includes_fov_and_requirement_rows(client) -> None:
    project = small_project()
    project["requirements"] = {"azimuth_resolution_deg": 30}
    job = client.post(
        "/api/reports",
        json={"project": project, "options": {"title": "fov report", "include_raw_data": True}},
    ).json()

    status = wait_for_job(client, job)
    download = client.get(f"/api/jobs/{job['id']}/download")

    assert status["status"] == "succeeded", status
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        manifest_name = next(n for n in archive.namelist() if n.endswith("report_manifest.json"))
        import json

        manifest = json.loads(archive.read(manifest_name))
    assert manifest["array_factor_fov"]["azimuth_deg"] == [-75.0, 75.0]
    assert manifest["dbf_scan"]["search_guard_deg"] == 10.0
    assert manifest["requirement_checks"][0]["key"] == "resolution"


def test_share_link_round_trip_is_content_addressed(client, project) -> None:
    created = client.post("/api/shares", json={"project": project})
    assert created.status_code == 200, created.text
    share = created.json()
    assert len(share["id"]) == 12 and share["id"].isalnum()
    assert share["path"] == f"/s/{share['id']}"

    # Same configuration → same link; a different layout → a different link.
    assert client.post("/api/shares", json={"project": project}).json()["id"] == share["id"]
    assert client.post("/api/shares", json={"project": small_project()}).json()["id"] != share["id"]

    opened = client.get(f"/api/shares/{share['id']}")
    assert opened.status_code == 200
    body = opened.json()
    assert body["project"]["layout"] == project["layout"]
    assert body["project"]["band"] == project["band"]
    assert body["missing_assets"] == []


def test_share_link_reports_missing_assets_and_rejects_bad_ids(client, project) -> None:
    project["element_pattern"] = {"asset": "0" * 64, "swap_axes": False}
    share_id = client.post("/api/shares", json={"project": project}).json()["id"]
    assert client.get(f"/api/shares/{share_id}").json()["missing_assets"] == ["0" * 64]

    assert client.get("/api/shares/AAAAAAAAAAAA").status_code == 404
    assert client.get("/api/shares/..%2F..%2Fetc").status_code == 404
    assert client.get("/api/shares/short").status_code == 404


def test_share_path_serves_the_web_client(tmp_path) -> None:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html>app</html>", encoding="utf-8")
    client = TestClient(create_app(data_dir=tmp_path / "data", static_dir=web))
    response = client.get("/s/AbCdEf123456")
    assert response.status_code == 200
    assert "app" in response.text


@pytest.mark.parametrize(
    "content",
    [b"PK\x03\x04garbage" * 10, b"not a zip at all", b""],
    ids=["truncated-zip", "plain-text", "empty-zip-member"],
)
def test_damaged_xlsx_is_a_client_error_everywhere(client, project, content) -> None:
    if not content:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("readme.txt", "no workbook here")
        content = buffer.getvalue()
    asset = upload(client, "x.xlsx", content)

    preview = client.post("/api/element-pattern/preview", json={"asset": asset})
    resolve = client.post(
        "/api/channel-patterns/resolve",
        json={"project": project, "asset": asset, "kind": "phase", "plane": "horizontal"},
    )
    project["dbf_dictionary"] = {**project["dbf_dictionary"], "mode": "custom", "azimuth_asset": asset}
    dictionary = client.post("/api/dictionary/preview", json={"project": project, "axis": "azimuth"})
    evaluate = client.post("/api/evaluate", json={"project": project})

    for response in (preview, resolve, dictionary, evaluate):
        assert 400 <= response.status_code < 500, (response.request.url, response.status_code, response.text)
        assert "XLSX" in response.json()["detail"]


def test_concurrent_saves_conflict_instead_of_overwriting(client, project) -> None:
    created = client.post("/api/projects", json={"project": project}).json()
    assert created["revision"] == 1
    project_id = created["id"]

    # Two people open revision 1 and both edit it.
    alice = {**project, "name": "Alice edit"}
    bob = {**project, "name": "Bob edit"}

    saved = client.put(f"/api/projects/{project_id}", json={"project": alice, "base_revision": 1})
    assert saved.status_code == 200
    assert saved.json()["revision"] == 2

    conflict = client.put(f"/api/projects/{project_id}", json={"project": bob, "base_revision": 1})
    assert conflict.status_code == 409
    assert "revision 2" in conflict.json()["detail"]
    stored = client.get(f"/api/projects/{project_id}").json()
    assert stored["project"]["name"] == "Alice edit"
    assert stored["revision"] == 2

    # Saving on top of the latest revision works; omitting it overwrites on purpose.
    assert client.put(f"/api/projects/{project_id}", json={"project": bob, "base_revision": 2}).json()["revision"] == 3
    forced = client.put(f"/api/projects/{project_id}", json={"project": alice})
    assert forced.status_code == 200 and forced.json()["revision"] == 4
    listed = {item["id"]: item for item in client.get("/api/projects").json()}
    assert listed[project_id]["revision"] == 4


def test_records_without_revision_count_as_revision_one(tmp_path, project) -> None:
    import json as _json

    client = TestClient(create_app(data_dir=tmp_path / "data", static_dir=tmp_path / "web"))
    project_id = client.post("/api/projects", json={"project": project}).json()["id"]
    path = tmp_path / "data" / "projects" / f"{project_id}.json"
    record = _json.loads(path.read_text(encoding="utf-8"))
    del record["revision"]  # written by a version before revisions existed
    path.write_text(_json.dumps(record), encoding="utf-8")

    assert client.get(f"/api/projects/{project_id}").json()["revision"] == 1
    assert client.put(f"/api/projects/{project_id}", json={"project": project, "base_revision": 1}).json()["revision"] == 2


def test_deleted_project_is_not_resurrected_by_concurrent_saves(client, project) -> None:
    import threading

    resurrected = 0
    for _ in range(40):
        project_id = client.post("/api/projects", json={"project": project}).json()["id"]
        barrier = threading.Barrier(5)

        def save(project_id: str = project_id, barrier: threading.Barrier = barrier) -> None:
            barrier.wait()
            for _ in range(4):
                client.put(f"/api/projects/{project_id}", json={"project": project})

        def delete(project_id: str = project_id, barrier: threading.Barrier = barrier) -> None:
            barrier.wait()
            assert client.delete(f"/api/projects/{project_id}").status_code == 204

        threads = [threading.Thread(target=save) for _ in range(4)] + [threading.Thread(target=delete)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if client.get(f"/api/projects/{project_id}").status_code != 404:
            resurrected += 1
    assert resurrected == 0


def ideal_dictionary_csv(start: float, stop: float, step: float = 0.5) -> bytes:
    """Ideal-geometry azimuth dictionary for the default project's virtual channels."""
    from virtual_array.project import project_array

    array = project_array(default_project())
    angles = np.arange(start, stop + step / 2, step)
    names, phases = [], []
    for ti, tx in enumerate(array.tx):
        for ri, rx in enumerate(array.rx):
            names.append(f"Tx{ti + 1}Rx{ri + 1}")
            phases.append(180.0 * (tx.x + rx.x) * np.sin(np.radians(angles)))
    lines = ["Angle," + ",".join(names)]
    lines += [f"{angle:g}," + ",".join(f"{phase[i]:.6f}" for phase in phases) for i, angle in enumerate(angles)]
    return ("\n".join(lines) + "\n").encode()


@pytest.mark.parametrize(
    ("span", "note"),
    [((-90, 90), None), ((-75, 75), "dictionary_guard_gap"), ((-60, 60), "dictionary_fov_gap")],
)
def test_custom_dictionary_edges_are_not_extrapolated(client, project, span, note) -> None:
    asset = upload(client, "dict.csv", ideal_dictionary_csv(*span))
    project["dbf_dictionary"] = {**project["dbf_dictionary"], "mode": "custom", "azimuth_asset": asset}

    result = client.post("/api/evaluate", json={"project": project}).json()
    azimuth = result["angle"]["azimuth"]
    coverage = result["dictionary_coverage"]["azimuth"]
    assert coverage["table"] == [span[0], span[1]]
    assert coverage["fov"] == [-75, 75]
    notes = {code for code in result["notes"] if code.startswith("dictionary_")}
    assert notes == ({note} if note else set())

    if span[0] <= -75:
        # A table that exactly spans the FOV used to report -85° for a true -75°
        # (edge rows repeated across the guard band); both edges must now be exact.
        assert azimuth["focus_max_abs_error"] < 0.01
        assert (azimuth["no_fold_left"], azimuth["no_fold_right"]) == (-75, 75)
        assert azimuth["negative_cut_reason"] == azimuth["positive_cut_reason"] == "data_boundary"

    preview = client.post("/api/dictionary/preview", json={"project": project, "axis": "azimuth"}).json()
    assert preview["coverage"]["table"] == [span[0], span[1]]
    assert preview["quality"]["zero_norm_rows"] == 0


def test_storage_failures_are_reported_and_leave_no_partial_files(tmp_path, project, monkeypatch) -> None:
    import errno
    from pathlib import Path as _Path

    client = TestClient(create_app(data_dir=tmp_path / "data", static_dir=tmp_path / "web"))
    real_write = _Path.write_bytes

    def disk_full(self, data):  # noqa: ANN001
        real_write(self, data[: len(data) // 2])  # a partial temp file, as on a full disk
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(_Path, "write_bytes", disk_full)
    upload_response = client.post("/api/assets", files={"file": ("p.csv", b"theta,gain\n0,1\n", "text/csv")})
    save_response = client.post("/api/projects", json={"project": project})
    monkeypatch.undo()

    for response in (upload_response, save_response):
        assert response.status_code == 507
        assert "data directory" in response.json()["detail"]
    leftovers = [path for path in (tmp_path / "data").rglob("*") if path.is_file() and path.suffix in {".tmp", ".csv"}]
    assert leftovers == []
    assert not any((tmp_path / "data" / "assets").iterdir())


def test_cli_refuses_an_unusable_data_dir(tmp_path, capsys) -> None:
    from virtual_array.server.cli import main

    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as exit_info:
        main(["--data-dir", str(blocker / "data")])
    assert exit_info.value.code == 2
    assert "Cannot use data directory" in capsys.readouterr().err


def test_request_bodies_are_size_limited(client, project) -> None:
    from virtual_array.server.limits import MAX_JSON_BODY_BYTES

    padding = "x" * (MAX_JSON_BODY_BYTES + 1)
    oversized = client.post(
        "/api/evaluate", content=json.dumps({"project": project, "pad": padding}), headers={"Content-Type": "application/json"}
    )
    assert oversized.status_code == 413
    assert "MB" in oversized.json()["detail"]

    # Chunked bodies without Content-Length are counted while being read.
    def chunks():
        yield b'{"project": '
        for _ in range(MAX_JSON_BODY_BYTES // (1024 * 1024) + 2):
            yield b" " * (1024 * 1024)
        yield json.dumps(project).encode() + b"}"

    chunked = client.post("/api/evaluate", content=chunks(), headers={"Content-Type": "application/json"})
    assert chunked.status_code == 413

    # Uploads keep their own, larger limit (an 18 MB CSV is fine).
    big_csv = b"theta,gain\n" + b"0,1\n" * (18 * 1024 * 1024 // 4)
    assert client.post("/api/assets", files={"file": ("big.csv", big_csv, "text/csv")}).status_code == 200
    assert client.post("/api/evaluate", json={"project": project}).status_code == 200

from __future__ import annotations

import io
import json
import tracemalloc
import zipfile

import pytest
from fastapi.testclient import TestClient

from virtual_array.assets import MAX_ASSET_BYTES
from virtual_array.project import default_project
from virtual_array.server import create_app
from virtual_array.server.bundles import MAX_BUNDLE_MEMBERS, BundleError, read_bundle

ASSET_ID = "a" * 64


def project_json() -> bytes:
    return json.dumps(default_project().model_dump(mode="json")).encode("utf-8")


def make_bundle(members: dict[str, bytes], zeros: dict[str, int] | None = None) -> bytes:
    """Build a zip in memory; ``zeros`` members are streamed so huge ones stay cheap."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
        for name, size in (zeros or {}).items():
            chunk = b"0" * (1024 * 1024)
            with archive.open(name, "w", force_zip64=True) as handle:
                for _ in range(size // len(chunk)):
                    handle.write(chunk)
    return buffer.getvalue()


@pytest.fixture()
def client(tmp_path) -> TestClient:
    return TestClient(create_app(data_dir=tmp_path / "data", static_dir=tmp_path / "web"))


def post_bundle(client: TestClient, content: bytes):
    return client.post("/api/import/bundle", files={"file": ("p.mimo.zip", content, "application/zip")})


def test_zip_bomb_is_rejected_without_decompressing(client, tmp_path) -> None:
    bomb = make_bundle({"project.json": project_json()}, zeros={f"assets/{ASSET_ID}/bomb.csv": 2 * MAX_ASSET_BYTES})
    assert len(bomb) < 1024 * 1024  # ~64 MiB of zeros compresses to well under 1 MiB

    tracemalloc.start()
    try:
        with pytest.raises(BundleError, match="too large"):
            read_bundle(bomb)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 8 * 1024 * 1024

    response = post_bundle(client, bomb)
    assert response.status_code == 422
    assert not any((tmp_path / "data" / "assets").glob("*/*.csv"))


def test_member_with_understated_size_cannot_overread() -> None:
    content = make_bundle({"project.json": project_json(), f"assets/{ASSET_ID}/x.csv": b"1,2\n" * 5000})
    archive = zipfile.ZipFile(io.BytesIO(content))
    info = archive.getinfo(f"assets/{ASSET_ID}/x.csv")
    info.file_size = 10  # a lying header: real data is far larger
    from virtual_array.server.bundles import _Budget, _read_member

    with pytest.raises(BundleError):
        _read_member(archive, info, 100, _Budget(1000), "x.csv")


def test_bundle_member_and_total_limits(client) -> None:
    many = make_bundle({"project.json": project_json(), **{f"extra/{i}.txt": b"x" for i in range(MAX_BUNDLE_MEMBERS)}})
    assert post_bundle(client, many).status_code == 422

    assert post_bundle(client, make_bundle({"project.json": b"{not json"})).status_code == 422
    assert post_bundle(client, make_bundle({"other.json": b"{}"})).status_code == 422
    assert post_bundle(client, b"PK\x03\x04garbage").status_code == 422


def test_bad_member_leaves_no_partial_assets(client, tmp_path) -> None:
    content = make_bundle({
        "project.json": project_json(),
        f"assets/{ASSET_ID}/ok.csv": b"theta,gain\n0,1\n",
        f"assets/{'b' * 64}/tool.exe": b"MZ",
    })
    response = post_bundle(client, content)
    assert response.status_code == 422
    assert "tool.exe" in response.json()["detail"]
    assert not any((tmp_path / "data" / "assets").glob("*/*.csv"))


def test_non_content_ids_are_not_used_for_text_remapping(client) -> None:
    # "1" would otherwise be replaced throughout project.json, corrupting it.
    content = make_bundle({"project.json": project_json(), "assets/1/x.csv": b"theta,gain\n0,1\n"})
    response = post_bundle(client, content)
    assert response.status_code == 200
    assert response.json()["project"]["frequency_ghz"] == default_project().frequency_ghz

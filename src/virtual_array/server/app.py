from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from ..analysis import DBF_SCAN_FOV, DBF_SCAN_GRID_SIZE, DBF_SCAN_STEP_DEG
from ..assets import MAX_ASSET_BYTES, AssetNotFoundError, AssetStore, sanitize_filename
from ..engine import Engine, ProjectComputationError
from ..logging_config import configure_logging
from ..project import (
    GRID_STEP_LAMBDA,
    MAX_RX_COUNT,
    MAX_TX_COUNT,
    ChannelPatternBinding,
    Layout,
    Project,
    auto_layout,
    default_project,
    project_from_document,
)
from ..version import APP_VERSION
from .jobs import JobManager, JobNotFoundError, zip_directory
from .store import ProjectNotFoundError, ProjectStore

LOGGER = logging.getLogger(__name__)
DATA_DIR_ENV = "MIMO_DATA_DIR"
WEB_DIST_ENV = "MIMO_WEB_DIST"
MAX_2D_FRAMES_PER_REQUEST = 24
MAX_BUNDLE_BYTES = 128 * 1024 * 1024


def default_data_dir() -> Path:
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path.cwd() / "data"


def default_static_dir() -> Path:
    override = os.environ.get(WEB_DIST_ENV)
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent / "static"


# ── Request models ───────────────────────────────────────────────────


class ProjectRequest(BaseModel):
    project: Project


class AutoLayoutRequest(BaseModel):
    tx_count: int = Field(ge=1, le=MAX_TX_COUNT)
    rx_count: int = Field(ge=1, le=MAX_RX_COUNT)


class BankRequest(ProjectRequest):
    axis: Literal["azimuth", "elevation"]


class TrueAngle(BaseModel):
    azimuth: float = Field(ge=DBF_SCAN_FOV[0], le=DBF_SCAN_FOV[1])
    elevation: float = Field(ge=DBF_SCAN_FOV[0], le=DBF_SCAN_FOV[1])


class Dbf2dRequest(ProjectRequest):
    frames: list[TrueAngle] = Field(min_length=1, max_length=MAX_2D_FRAMES_PER_REQUEST)


class ElementPatternPreviewRequest(BaseModel):
    asset: str
    swap_axes: bool = False


class ChannelPatternResolveRequest(ProjectRequest):
    asset: str
    kind: Literal["amplitude", "phase"]
    plane: Literal["horizontal", "elevation"]
    target: Literal["physical", "virtual"] = "physical"
    channel: str | None = None


class DictionaryPreviewRequest(ProjectRequest):
    axis: Literal["azimuth", "elevation"] = "azimuth"


class ImportDocumentRequest(BaseModel):
    document: Any


class AngleRangeModel(BaseModel):
    start: float = Field(ge=DBF_SCAN_FOV[0], le=DBF_SCAN_FOV[1])
    stop: float = Field(ge=DBF_SCAN_FOV[0], le=DBF_SCAN_FOV[1])


class ReportOptionsModel(BaseModel):
    title: str = Field(default="当前配置测角性能报告", min_length=1, max_length=100)
    azimuth_focus: AngleRangeModel = AngleRangeModel(start=-70, stop=70)
    elevation_focus: AngleRangeModel = AngleRangeModel(start=-15, stop=15)
    azimuth_hold: AngleRangeModel = AngleRangeModel(start=-70, stop=70)
    elevation_hold: AngleRangeModel = AngleRangeModel(start=-15, stop=15)
    azimuth_hold_stride_frames: int = 1
    elevation_hold_stride_frames: int = 1
    error_limit_deg: float = 1.0
    spectrum_floor_db: float = -40.0
    include_raw_data: bool = True
    include_spectrum_db: bool = True
    include_spectrum_magnitude: bool = False
    language: Literal["zh", "en", "ja"] = "zh"


class ReportRequest(ProjectRequest):
    options: ReportOptionsModel = ReportOptionsModel()


class AngleErrorImageRequest(ProjectRequest):
    error_limit_deg: float = 1.0
    language: Literal["zh", "en", "ja"] = "zh"


class SaveProjectRequest(ProjectRequest):
    pass


# ── Application ──────────────────────────────────────────────────────


def create_app(data_dir: str | Path | None = None, static_dir: str | Path | None = None) -> FastAPI:
    root = Path(data_dir) if data_dir is not None else default_data_dir()
    root.mkdir(parents=True, exist_ok=True)
    assets = AssetStore(root / "assets")
    engine = Engine(assets)
    projects = ProjectStore(root / "projects")
    jobs = JobManager(root / "jobs")
    web_root = Path(static_dir) if static_dir is not None else default_static_dir()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):  # noqa: ANN202
        yield
        jobs.shutdown()

    app = FastAPI(
        title="MIMO Array Visualizer",
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.engine = engine
    app.state.assets = assets
    app.state.projects = projects
    app.state.jobs = jobs
    app.state.data_dir = root

    @app.exception_handler(ProjectComputationError)
    async def computation_error(_request: Request, exc: ProjectComputationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(AssetNotFoundError)
    async def asset_missing(_request: Request, exc: AssetNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"Asset not found: {exc}"})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        messages = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
            messages.append(f"{location}: {error.get('msg')}" if location else str(error.get("msg")))
        return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})

    def bad_request(exc: Exception) -> HTTPException:
        return HTTPException(status_code=422, detail=str(exc))

    # ── Meta ─────────────────────────────────────────────────────────

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": APP_VERSION}

    @app.get("/api/config")
    def config() -> dict[str, Any]:
        return {
            "version": APP_VERSION,
            "default_project": default_project().model_dump(mode="json"),
            "limits": {
                "max_tx": MAX_TX_COUNT,
                "max_rx": MAX_RX_COUNT,
                "grid_step_lambda": GRID_STEP_LAMBDA,
                "max_asset_bytes": MAX_ASSET_BYTES,
                "max_2d_frames_per_request": MAX_2D_FRAMES_PER_REQUEST,
            },
            "dbf": {
                "scan_fov": list(DBF_SCAN_FOV),
                "scan_step_deg": DBF_SCAN_STEP_DEG,
                "scan_grid_size": DBF_SCAN_GRID_SIZE,
            },
        }

    @app.post("/api/layout/auto")
    def layout_auto(request: AutoLayoutRequest) -> Layout:
        return auto_layout(request.tx_count, request.rx_count)

    # ── Analysis ─────────────────────────────────────────────────────

    @app.post("/api/evaluate")
    def evaluate(request: ProjectRequest) -> dict[str, Any]:
        return engine.evaluate(request.project)

    @app.post("/api/dbf/bank")
    def dbf_bank(request: BankRequest) -> dict[str, Any]:
        return engine.dbf_bank(request.project, request.axis)

    @app.post("/api/dbf/2d")
    def dbf_2d(request: Dbf2dRequest) -> dict[str, Any]:
        frames = [(frame.azimuth, frame.elevation) for frame in request.frames]
        return engine.dbf_2d(request.project, frames)

    # ── Imported data ────────────────────────────────────────────────

    @app.post("/api/assets")
    async def upload_asset(file: UploadFile = File(...)) -> dict[str, Any]:
        content = await file.read(MAX_ASSET_BYTES + 1)
        try:
            info = assets.add(file.filename or "upload.csv", content)
        except ValueError as exc:
            raise bad_request(exc) from exc
        return asdict(info)

    @app.get("/api/assets/{asset_id}")
    def asset_info(asset_id: str) -> dict[str, Any]:
        return asdict(assets.info(asset_id))

    @app.post("/api/element-pattern/preview")
    def element_pattern_preview(request: ElementPatternPreviewRequest) -> dict[str, Any]:
        try:
            return engine.element_pattern_preview(request.asset, request.swap_axes)
        except ValueError as exc:
            raise bad_request(exc) from exc

    @app.post("/api/channel-patterns/resolve")
    def channel_patterns_resolve(request: ChannelPatternResolveRequest) -> list[ChannelPatternBinding]:
        try:
            return engine.resolve_channel_patterns(
                request.project,
                request.asset,
                request.kind,
                request.plane,
                request.target,
                channel=request.channel,
            )
        except ValueError as exc:
            raise bad_request(exc) from exc

    @app.post("/api/dictionary/preview")
    def dictionary_preview(request: DictionaryPreviewRequest) -> dict[str, Any]:
        return engine.dictionary_preview(request.project, request.axis)

    # ── Import / export ──────────────────────────────────────────────

    @app.post("/api/import/document")
    def import_document(request: ImportDocumentRequest) -> dict[str, Any]:
        try:
            project = project_from_document(request.document)
        except (ValueError, ValidationError) as exc:
            raise bad_request(exc) from exc
        missing = sorted(asset for asset in project.asset_ids() if not assets.exists(asset))
        return {"project": project.model_dump(mode="json"), "missing_assets": missing}

    @app.post("/api/export/layout")
    def export_layout(request: ProjectRequest) -> dict[str, Any]:
        return engine.layout_document(request.project)

    @app.post("/api/export/bundle")
    def export_bundle(request: ProjectRequest) -> Response:
        project = request.project
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "project.json",
                json.dumps(project.model_dump(mode="json"), ensure_ascii=False, indent=2),
            )
            for asset_id in sorted(project.asset_ids()):
                info = assets.info(asset_id)
                archive.write(assets.path(asset_id), arcname=f"assets/{asset_id}/{info.filename}")
        filename = sanitize_filename(f"{project.name}.mimo.zip")
        return Response(
            content=buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": _content_disposition(filename)},
        )

    @app.post("/api/import/bundle")
    async def import_bundle(file: UploadFile = File(...)) -> dict[str, Any]:
        content = await file.read(MAX_BUNDLE_BYTES + 1)
        if len(content) > MAX_BUNDLE_BYTES:
            raise HTTPException(status_code=413, detail="Project bundle is too large.")
        try:
            archive = zipfile.ZipFile(io.BytesIO(content))
        except zipfile.BadZipFile as exc:
            raise bad_request(ValueError("Not a valid project bundle (.zip).")) from exc
        with archive:
            try:
                document = json.loads(archive.read("project.json").decode("utf-8"))
            except KeyError as exc:
                raise bad_request(ValueError("Bundle has no project.json.")) from exc
            remap: dict[str, str] = {}
            for name in archive.namelist():
                parts = name.split("/")
                if len(parts) != 3 or parts[0] != "assets" or not parts[2]:
                    continue
                data = archive.read(name)
                if len(data) > MAX_ASSET_BYTES:
                    raise bad_request(ValueError(f"Bundled file {parts[2]} is too large."))
                info = assets.add(parts[2], data)
                remap[parts[1]] = info.id
        text = json.dumps(document)
        for old_id, new_id in remap.items():
            text = text.replace(old_id, new_id)
        try:
            project = project_from_document(json.loads(text))
        except (ValueError, ValidationError) as exc:
            raise bad_request(exc) from exc
        missing = sorted(asset for asset in project.asset_ids() if not assets.exists(asset))
        return {"project": project.model_dump(mode="json"), "missing_assets": missing}

    # ── Project library ──────────────────────────────────────────────

    @app.get("/api/projects")
    def list_projects() -> list[dict[str, Any]]:
        return projects.list()

    @app.post("/api/projects")
    def create_project(request: SaveProjectRequest) -> dict[str, Any]:
        return projects.create(request.project)

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, Any]:
        try:
            return projects.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found.") from exc

    @app.put("/api/projects/{project_id}")
    def update_project(project_id: str, request: SaveProjectRequest) -> dict[str, Any]:
        try:
            return projects.update(project_id, request.project)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found.") from exc

    @app.delete("/api/projects/{project_id}", status_code=204)
    def delete_project(project_id: str) -> Response:
        try:
            projects.delete(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found.") from exc
        return Response(status_code=204)

    # ── Exports (background jobs) ────────────────────────────────────

    @app.post("/api/reports")
    def create_report(request: ReportRequest) -> dict[str, Any]:
        from ..performance_report import (
            AngleRange,
            PerformanceReportOptions,
            generate_performance_report,
        )

        snapshot = engine.report_snapshot(request.project)
        settings = request.options
        filename = sanitize_filename(f"{settings.title}.pdf")
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        try:
            # Validate eagerly so option errors return 422 instead of a failed job.
            template = PerformanceReportOptions(
                output_path=Path(filename),
                title=settings.title,
                azimuth_focus=AngleRange(settings.azimuth_focus.start, settings.azimuth_focus.stop),
                elevation_focus=AngleRange(
                    settings.elevation_focus.start, settings.elevation_focus.stop
                ),
                azimuth_hold=AngleRange(settings.azimuth_hold.start, settings.azimuth_hold.stop),
                elevation_hold=AngleRange(
                    settings.elevation_hold.start, settings.elevation_hold.stop
                ),
                error_limit_deg=settings.error_limit_deg,
                spectrum_floor_db=settings.spectrum_floor_db,
                include_raw_data=settings.include_raw_data,
                language=settings.language,
                include_spectrum_db=settings.include_spectrum_db,
                include_spectrum_magnitude=settings.include_spectrum_magnitude,
                azimuth_hold_stride_frames=settings.azimuth_hold_stride_frames,
                elevation_hold_stride_frames=settings.elevation_hold_stride_frames,
            )
        except ValueError as exc:
            raise bad_request(exc) from exc

        def body(directory: Path, progress) -> Path:  # noqa: ANN001
            from dataclasses import replace

            options = replace(template, output_path=directory / filename)
            artifacts = generate_performance_report(snapshot, options, progress)
            if not options.include_raw_data:
                return artifacts.pdf_path
            target = directory / f"{Path(filename).stem}.zip"
            return zip_directory(list(artifacts.files), directory, target)

        return jobs.submit("report", body).payload()

    @app.post("/api/angle-error-image")
    def create_angle_error_image(request: AngleErrorImageRequest) -> dict[str, Any]:
        from ..performance_report import AngleErrorImageOptions, generate_angle_error_image

        snapshot = engine.report_snapshot(request.project)
        filename = sanitize_filename(f"{request.project.name}-angle-error.png")
        try:
            template = AngleErrorImageOptions(
                output_path=Path(filename),
                error_limit_deg=request.error_limit_deg,
                language=request.language,
            )
        except ValueError as exc:
            raise bad_request(exc) from exc

        def body(directory: Path, progress) -> Path:  # noqa: ANN001
            from dataclasses import replace

            options = replace(template, output_path=directory / filename)
            return generate_angle_error_image(snapshot, options, progress).png_path

        return jobs.submit("angle_image", body).payload()

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str) -> dict[str, Any]:
        try:
            return jobs.get(job_id).payload()
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Job not found.") from exc

    @app.post("/api/jobs/{job_id}/cancel")
    def job_cancel(job_id: str) -> dict[str, Any]:
        try:
            return jobs.cancel(job_id).payload()
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Job not found.") from exc

    @app.get("/api/jobs/{job_id}/download")
    def job_download(job_id: str) -> FileResponse:
        try:
            job = jobs.get(job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Job not found.") from exc
        if job.status != "succeeded" or job.download_path is None:
            raise HTTPException(status_code=409, detail="The export is not ready.")
        return FileResponse(job.download_path, filename=job.download_name)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    def api_not_found(path: str) -> None:
        raise HTTPException(status_code=404, detail=f"Unknown API endpoint: /api/{path}")

    _mount_web_client(app, web_root)
    return app


def _mount_web_client(app: FastAPI, web_root: Path) -> None:
    index = web_root / "index.html"
    if not index.is_file():
        LOGGER.warning("Web client not found at %s; serving API only.", web_root)

        @app.get("/", include_in_schema=False)
        def missing_client() -> HTMLResponse:
            return HTMLResponse(
                "<h1>MIMO Array Visualizer API</h1>"
                "<p>The web client has not been built. Run <code>npm run build</code> "
                "in <code>web/</code>, or open <a href='/api/docs'>/api/docs</a>.</p>"
            )

        return

    assets_dir = web_root / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="web-assets")

    @app.get("/{path:path}", include_in_schema=False)
    def web_client(path: str) -> FileResponse:
        candidate = (web_root / path).resolve()
        if path and candidate.is_file() and web_root.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


def _content_disposition(filename: str) -> str:
    from urllib.parse import quote

    ascii_name = filename.encode("ascii", "ignore").decode() or "project.mimo.zip"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def configure_server_logging(data_dir: Path) -> Path:
    return configure_logging(data_dir / "logs")

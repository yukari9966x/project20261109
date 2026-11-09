"""로컬 웹서버(FastAPI): REST API + 정적 웹 UI(webapp/).

- 기본 바인딩 127.0.0.1, 업로드 한도 30 MB, 작업별 임시 디렉터리(1시간 뒤 삭제)
- 문서 내용은 로그에 남기지 않는다(작업 ID·크기·소요 시간만)
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ksfix import __version__
from ksfix.io import InputError
from ksfix.io.safety import MB

log = logging.getLogger("ksfix.web")
JOB_RE = re.compile(r"^[0-9a-f]{32}$")
# 웹 UI(정적 파일)는 인라인 스크립트·스타일·외부 자원을 쓰지 않는다
UI_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)
FILES = {
    "tracked": ("result.ksfix-tracked.docx", "변경추적본(.docx)", ".ksfix-tracked.docx"),
    "clean": ("result.ksfix-clean.docx", "반영본(.docx)", ".ksfix-clean.docx"),
    "report_html": ("report.html", "리포트(HTML)", ".ksfix-report.html"),
    "report_json": ("report.json", "리포트(JSON)", ".ksfix-report.json"),
    "audit": ("audit.jsonl", "감사 로그(JSONL)", ".ksfix-audit.jsonl"),
}
MEDIA = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json",
    ".jsonl": "application/x-ndjson",
}


@dataclass
class Settings:
    max_upload_mb: int = field(
        default_factory=lambda: int(os.environ.get("KSFIX_MAX_UPLOAD_MB", "30"))
    )
    workdir: Path = field(
        default_factory=lambda: (
            Path(os.environ.get("KSFIX_WORKDIR") or tempfile.gettempdir()) / "ksfix-jobs"
        )
    )
    ttl_seconds: int = field(default_factory=lambda: int(os.environ.get("KSFIX_JOB_TTL", "3600")))
    static_dir: Path | None = None


def find_static_dir() -> Path | None:
    import ksfix

    here = Path(ksfix.__file__).resolve().parent
    for cand in (here / "webapp", here.parent.parent / "webapp"):
        if (cand / "index.html").is_file():
            return cand
    return None


def _cleanup(root: Path, ttl: int) -> None:
    if not root.is_dir():
        return
    now = time.time()
    for job in root.iterdir():
        try:
            if job.is_dir() and now - job.stat().st_mtime > ttl:
                shutil.rmtree(job, ignore_errors=True)
        except OSError:
            pass


def _safe_stem(name: str) -> str:
    stem = Path(name or "document").stem
    stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", stem).strip(" .") or "document"
    return stem[:80]


def _options(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        opts = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"옵션 JSON 형식이 잘못되었습니다: {exc}") from exc
    if not isinstance(opts, dict):
        raise HTTPException(400, "옵션은 JSON 객체여야 합니다.")
    return opts


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.workdir.mkdir(parents=True, exist_ok=True)
    static = settings.static_dir or find_static_dir()
    app = FastAPI(title="KS-Fix", version=__version__, docs_url="/api/docs", redoc_url=None)
    app.state.settings = settings

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        if not request.url.path.startswith("/api/"):
            resp.headers.setdefault("Content-Security-Policy", UI_CSP)
        return resp

    @app.get("/api/v1/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/v1/rules")
    def rules() -> dict[str, Any]:
        from ksfix.rules.registry import implemented_ids, load_catalog

        cat = load_catalog()
        impl = implemented_ids()
        return {
            "pack": cat.pack,
            "version": cat.version,
            "title": cat.title,
            "rules": [{**r, "implemented": r["id"] in impl} for r in cat.rules],
        }

    @app.get("/api/v1/llm/profiles")
    def llm_profiles() -> dict[str, Any]:
        try:
            from ksfix.llm.config import list_profiles

            profiles = list_profiles()
        except ImportError:
            profiles = [{"name": "none", "provider": "none", "model": None, "external": False}]
        return {"profiles": profiles}

    @app.post("/api/v1/process")
    async def process(
        request: Request, file: UploadFile = File(...), options: str | None = Form(None)
    ):
        from ksfix.api import check_bytes, fix_bytes
        from ksfix.report import build_report, render_html

        _cleanup(settings.workdir, settings.ttl_seconds)
        limit = settings.max_upload_mb * MB
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > limit + MB:
            raise HTTPException(413, f"파일이 너무 큽니다(최대 {settings.max_upload_mb} MB).")
        data = await file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"파일이 너무 큽니다(최대 {settings.max_upload_mb} MB).")
        opts = _options(options)
        mode = opts.get("mode", "tracked")
        if mode not in ("tracked", "clean", "report", "check"):
            raise HTTPException(400, f"알 수 없는 출력 모드: {mode}")
        rules_spec = opts.get("rules") or None
        llm_name = opts.get("llm") or "none"
        llm = None
        if llm_name not in ("none", ""):
            try:
                from ksfix.llm.config import make_client

                llm = make_client(llm_name)
            except ImportError as exc:
                raise HTTPException(400, "LLM 기능이 설치되어 있지 않습니다.") from exc
            except (KeyError, ValueError) as exc:
                raise HTTPException(400, f"LLM 프로필 오류: {exc}") from exc
        job = uuid.uuid4().hex
        t0 = time.perf_counter()
        try:
            if mode == "check":
                chk = check_bytes(data, rules=rules_spec, llm=llm)
                fix = None
            else:
                fix = fix_bytes(data, mode=mode, rules=rules_spec, llm=llm)
                chk = fix.check
        except InputError as exc:
            raise HTTPException(400, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        stem = _safe_stem(file.filename or "document.docx")
        report = build_report(chk, fix, source_name=f"{stem}.docx", input_unchanged=True)
        jobdir = settings.workdir / job
        jobdir.mkdir(parents=True)
        (jobdir / "meta.json").write_text(
            json.dumps({"stem": stem}, ensure_ascii=False), encoding="utf-8"
        )
        files = []

        def put(key: str, content: bytes | str) -> None:
            disk, label, suffix = FILES[key]
            path = jobdir / disk
            if isinstance(content, str):
                path.write_text(content, encoding="utf-8")
            else:
                path.write_bytes(content)
            files.append(
                {
                    "key": key,
                    "label": label,
                    "name": f"{stem}{suffix}",
                    "url": f"/api/v1/files/{job}/{key}",
                    "size": path.stat().st_size,
                }
            )

        if fix is not None and fix.output is not None:
            put(mode, fix.output)
        put("report_html", render_html(report))
        put("report_json", json.dumps(report, ensure_ascii=False, indent=1))
        if fix is not None:
            put("audit", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in fix.audit))
        log.info("job %s: %d bytes, mode=%s, %.2fs", job, len(data), mode, time.perf_counter() - t0)
        return JSONResponse({"job": job, "files": files, "report": report})

    @app.get("/api/v1/files/{job}/{key}")
    def download(job: str, key: str):
        if not JOB_RE.match(job) or key not in FILES:
            raise HTTPException(404, "파일을 찾을 수 없습니다.")
        jobdir = settings.workdir / job
        disk, _label, suffix = FILES[key]
        path = jobdir / disk
        if not path.is_file():
            raise HTTPException(404, "파일이 없거나 보관 기간(1시간)이 지났습니다.")
        stem = "document"
        try:
            stem = json.loads((jobdir / "meta.json").read_text(encoding="utf-8"))["stem"]
        except (OSError, ValueError, KeyError):
            pass
        media = MEDIA.get(Path(disk).suffix, "application/octet-stream")
        return FileResponse(path, media_type=media, filename=f"{stem}{suffix}")

    if static is not None:
        app.mount("/", StaticFiles(directory=str(static), html=True), name="webapp")
    return app


def serve(host: str | None = None, port: int | None = None, open_browser: bool = False) -> None:
    import threading
    import webbrowser

    import uvicorn

    host = host or os.environ.get("KSFIX_HOST", "127.0.0.1")
    port = port or int(os.environ.get("KSFIX_PORT", "8765"))
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}"
    print(f"KS-Fix 웹 UI: {url}  (끝내려면 Ctrl+C)")
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")

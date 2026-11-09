"""웹 API E2E(FastAPI TestClient): 업로드 → 결과 → 내려받기 → 재열기."""

import io
import json

import docx
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from ksfix.web.app import Settings, create_app

DOCX_MT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture()
def client(tmp_path):
    app = create_app(Settings(max_upload_mb=2, workdir=tmp_path / "jobs", ttl_seconds=3600))
    return TestClient(app)


def upload(client, data, name="표준안.docx", **opts):
    return client.post(
        "/api/v1/process",
        files={"file": (name, data, DOCX_MT)},
        data={"options": json.dumps(opts)} if opts else None,
    )


def test_health_rules_profiles(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    rules = client.get("/api/v1/rules").json()["rules"]
    assert len(rules) == 84 and any(r["implemented"] for r in rules)
    names = [p["name"] for p in client.get("/api/v1/llm/profiles").json()["profiles"]]
    assert "none" in names


def test_upload_sample01_and_download(client, sample_bytes):
    r = upload(client, sample_bytes["sample_01_violations"], mode="tracked")
    assert r.status_code == 200, r.text
    body = r.json()
    rep = body["report"]
    assert rep["summary"]["applied"] >= 7 and rep["summary"]["findings"] >= 10
    assert len(rep["checklist"]["items"]) == 53
    keys = {f["key"]: f for f in body["files"]}
    assert {"tracked", "report_html", "report_json", "audit"} <= set(keys)
    assert keys["tracked"]["name"] == "표준안.ksfix-tracked.docx"
    d = client.get(keys["tracked"]["url"])
    assert d.status_code == 200 and d.headers["content-type"].startswith(DOCX_MT)
    out = docx.Document(io.BytesIO(d.content))
    assert len(list(out.comments)) == rep["summary"]["comments"]
    assert "utf-8''" in d.headers["content-disposition"]
    h = client.get(keys["report_html"]["url"])
    assert h.status_code == 200 and "KS-Fix 점검 리포트" in h.text


def test_check_mode_has_no_docx(client, sample_bytes):
    body = upload(client, sample_bytes["sample_02_clean"], mode="check").json()
    assert {f["key"] for f in body["files"]} == {"report_html", "report_json"}
    assert body["report"]["mode"] == "check"


def test_rejects_bad_input_and_size(client):
    r = upload(client, b"not a zip", name="a.docx")
    assert r.status_code == 400 and "docx" in r.json()["detail"]
    big = b"PK" + b"0" * (3 * 1024 * 1024)
    r = upload(client, big, name="big.docx")
    assert r.status_code == 413
    r = upload(client, b"PK", name="a.docx", mode="nope")
    assert r.status_code == 400


def test_download_path_safety(client):
    assert client.get("/api/v1/files/../../etc/passwd").status_code == 404
    assert client.get("/api/v1/files/" + "0" * 32 + "/tracked").status_code == 404
    assert client.get("/api/v1/files/" + "0" * 32 + "/meta").status_code == 404


def test_static_ui_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "KS-Fix" in r.text
    assert client.get("/app.js").status_code == 200
    assert "cdn" not in r.text.lower() and "https://" not in r.text

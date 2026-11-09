"""수정 엔진 E2E: 변경추적·반영본·메모·불변성·무결성·원본 보호."""

import hashlib
import io
import json
import shutil
import subprocess
import zipfile

import docx
import pytest

from ksfix.api import analyze, check_bytes, fix_bytes
from ksfix.fix import plan
from ksfix.rules.base import Finding, FixSpec
from tests.helpers import ks_skeleton, make_docx


def test_tracked_fix_sample01(sample_bytes):
    data = sample_bytes["sample_01_violations"]
    before = hashlib.sha256(data).hexdigest()
    r = fix_bytes(data, mode="tracked", date="2026-11-10T00:00:00Z")
    assert hashlib.sha256(data).hexdigest() == before
    assert r.output and not r.integrity and r.invariants["ok"]
    s = r.summary()
    covered = sum(1 for d in r.decisions if d.covered_by)
    assert s["applied"] >= 20 and s["comments"] == len(r.check.findings) - covered
    assert s["pass_rate_after"] > s["pass_rate_before"]
    d = docx.Document(io.BytesIO(r.output))
    assert all(c.author == "KS-Fix" for c in d.comments)
    with zipfile.ZipFile(io.BytesIO(r.output)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
        settings = z.read("word/settings.xml").decode("utf-8")
    assert "<w:ins " in xml and "<w:del " in xml and "w:delText" in xml
    assert "updateFields" not in settings or 'w:updateFields w:val="true"' in settings


def test_clean_fix_leaves_no_autofixable(sample_bytes):
    r = fix_bytes(sample_bytes["sample_01_violations"], mode="clean")
    assert r.remaining_autofix == 0
    with zipfile.ZipFile(io.BytesIO(r.output)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    assert "<w:ins " not in xml and "<w:del " not in xml
    again = check_bytes(r.output)
    assert not any(
        f.rule_id in ("QTY-01", "PUN-02", "TBL-01", "FIG-01", "QTY-04") for f in again.findings
    )


def test_report_mode_produces_no_document(sample_bytes):
    r = fix_bytes(sample_bytes["sample_01_violations"], mode="report")
    assert r.output is None
    assert r.summary()["applied"] == 0


def test_clean_sample_untouched_except_nothing(sample_bytes):
    r = fix_bytes(sample_bytes["sample_02_clean"], mode="tracked")
    assert r.summary()["applied"] == 0
    assert not r.integrity


def test_existing_comments_preserved():
    base = make_docx(ks_skeleton(["최대 칭량은 150kg 이상이어야 한다."]))
    d = docx.Document(io.BytesIO(base))
    d.add_comment(d.paragraphs[1].runs, text="기존 검토 의견", author="담당자", initials="DJ")
    buf = io.BytesIO()
    d.save(buf)
    r = fix_bytes(buf.getvalue(), mode="tracked")
    out = docx.Document(io.BytesIO(r.output))
    authors = [c.author for c in out.comments]
    assert "담당자" in authors and "KS-Fix" in authors
    assert any(c.text == "기존 검토 의견" for c in out.comments)
    assert not r.integrity


def test_existing_tracked_changes_comment_only():
    base = make_docx(ks_skeleton(["최대 칭량은 150kg 이상이어야 한다."]))
    with zipfile.ZipFile(io.BytesIO(base)) as z:
        files = {n: z.read(n) for n in z.namelist()}
    xml = files["word/document.xml"].decode("utf-8")
    xml = xml.replace(
        "<w:t>이 표준은 시험용 장치에 대하여 규정한다.</w:t></w:r>",
        "<w:t>이 표준은 시험용 장치에 대하여 규정한다.</w:t></w:r>"
        '<w:ins w:id="7" w:author="x" w:date="2026-01-01T00:00:00Z"><w:r><w:t>추가</w:t></w:r></w:ins>',
    )
    files["word/document.xml"] = xml.encode("utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, v in files.items():
            z.writestr(n, v)
    r = fix_bytes(buf.getvalue(), mode="tracked")
    assert r.check.doc.meta["has_tracked_changes"]
    assert r.summary()["applied"] == 0 and r.summary()["comments"] >= 1
    r2 = fix_bytes(buf.getvalue(), mode="tracked", accept_existing_changes=True)
    assert r2.summary()["applied"] >= 1


def test_invariant_precheck_demotes_number_change(sample_bytes):
    doc = analyze(sample_bytes["sample_01_violations"])
    p = next(p for p in doc.paras if "150kg" in p.text)
    i = p.text.index("150")
    bad = Finding(
        rule_id="QTY-01",
        severity="warning",
        message="테스트",
        clause_ref="",
        block=p.idx,
        start=i,
        end=i + 3,
        snippet="",
        fix=FixSpec("replace_text", p.idx, i, i + 3, text="151"),
        priority="P0",
    )
    (d,) = plan(doc, [bad], "tracked")
    assert d.action == "suggest" and d.reason.startswith("INV-01")


def test_cli_fix_outputs(tmp_path, samples_dir):
    from ksfix.cli import main

    src = tmp_path / "in.docx"
    shutil.copy(samples_dir / "sample_01_violations.docx", src)
    h = hashlib.sha256(src.read_bytes()).hexdigest()
    rc = main(["fix", str(src), "-o", str(tmp_path / "out"), "--mode", "tracked"])
    assert rc == 0
    assert hashlib.sha256(src.read_bytes()).hexdigest() == h  # INV-02
    out = tmp_path / "out"
    assert (out / "in.ksfix-tracked.docx").exists()
    rep = json.loads((out / "in.ksfix-report.json").read_text(encoding="utf-8"))
    v = rep["verification"]
    assert v["input_unchanged"] and v["integrity"] == [] and v["invariants"]["ok"]
    assert (out / "in.ksfix-report.html").exists()
    lines = (out / "in.ksfix-audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert lines and all(json.loads(x)["rule_id"] for x in lines)


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice 없음")
def test_libreoffice_renders_tracked_output(tmp_path, sample_bytes):
    r = fix_bytes(sample_bytes["sample_01_violations"], mode="tracked")
    src = tmp_path / "t.docx"
    src.write_bytes(r.output)
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(tmp_path), str(src)],
        check=True,
        capture_output=True,
        timeout=180,
    )
    assert (tmp_path / "t.pdf").stat().st_size > 1000

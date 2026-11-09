"""골든 테스트: 샘플 1 기대 지적 재현율, 샘플 2 오탐 수."""

import json

from ksfix.api import check_bytes
from ksfix.classify import patterns as pt
from ksfix.rules.registry import implemented_ids, load_catalog


def match_expected(result, expected):
    paras = result.doc.paras
    found = {}
    for f in result.findings:
        found.setdefault(f.rule_id, []).append(pt.squash(paras[f.block].full_text))
    matched, missed = [], []
    for e in expected:
        where = pt.squash(e["where"])
        if any(where in t for t in found.get(e["rule_id"], [])):
            matched.append(e)
        else:
            missed.append(e)
    return matched, missed


def test_sample01_recall_for_implemented_deterministic_rules(samples_dir, sample_bytes):
    expected = json.loads((samples_dir / "sample_01_expected.json").read_text(encoding="utf-8"))
    impl = implemented_ids(include_system=False)
    cat = load_catalog().by_id()
    target = [e for e in expected if e["rule_id"] in impl]
    assert target, "구현된 규칙의 기대 지적이 없습니다"
    result = check_bytes(sample_bytes["sample_01_violations"])
    matched, missed = match_expected(result, target)
    det = [e for e in target if cat[e["rule_id"]]["method"] != "llm"]
    det_missed = [e for e in missed if cat[e["rule_id"]]["method"] != "llm"]
    recall = 1 - len(det_missed) / len(det)
    assert recall >= 0.95, missed


def test_sample02_false_positives_at_most_3(sample_bytes):
    result = check_bytes(sample_bytes["sample_02_clean"])
    fps = [f for f in result.findings if f.severity in ("error", "warning")]
    assert len(fps) <= 3, [(f.rule_id, f.snippet) for f in fps]


def test_no_internal_rule_errors_on_samples(sample_bytes):
    for name, data in sample_bytes.items():
        assert check_bytes(data).diagnostics == [], name


def test_cli_check_writes_json(tmp_path, samples_dir):
    from ksfix.cli import main

    rc = main(["check", str(samples_dir / "sample_02_clean.docx"), "-o", str(tmp_path)])
    assert rc == 0
    report = json.loads(
        (tmp_path / "sample_02_clean.ksfix-report.json").read_text(encoding="utf-8")
    )
    assert report["summary"]["by_severity"]["error"] == 0
    assert report["source"]["sha256"]

import pytest

from ksfix.api import analyze
from ksfix.rules import registry
from ksfix.rules.registry import load_catalog, make_context, run_rules, select_rules, validate


def test_catalog_and_implementations_consistent():
    validate()
    cat = load_catalog()
    assert len(cat.rules) == 84
    impl = registry.implemented_ids(include_system=False)
    assert impl <= set(cat.by_id())


def test_select_rules_variants():
    p0 = select_rules("P0")
    cat = load_catalog().by_id()
    assert p0 and all(cat[r]["priority"] == "P0" for r in p0)
    assert select_rules("qty-01,PUN-02") == {"QTY-01", "PUN-02"}
    with pytest.raises(ValueError):
        select_rules("NOPE-99")


def test_rule_exception_isolated(sample_bytes, monkeypatch):
    def boom(doc, ctx):
        raise RuntimeError("의도한 오류")

    monkeypatch.setitem(registry._REGISTRY, "STR-07", boom)
    doc = analyze(sample_bytes["sample_01_violations"])
    ctx = make_context({"STR-07", "PUN-02"})
    findings = run_rules(doc, ctx)
    assert any(f.rule_id == "PUN-02" for f in findings)
    assert ctx.diagnostics and ctx.diagnostics[0]["failed_rule"] == "STR-07"

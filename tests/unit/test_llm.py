"""LLM 계층: FakeLLM으로 파이프라인, 로컬 HTTP 서버로 OpenAI 호환 어댑터 오류 처리."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ksfix.api import check_bytes, fix_bytes
from ksfix.llm.base import LLMError, extract_json
from ksfix.llm.cache import LLMCache
from ksfix.llm.config import list_profiles, make_client
from ksfix.llm.openai_compat import OpenAICompatClient
from ksfix.llm.tasks.modal_verbs import guard, judge, normalize_items, split_sentences
from tests.helpers import ks_skeleton, make_docx


class FakeLLM:
    """문장 내용으로 판정하는 가짜 클라이언트(실제 네트워크 없음)."""

    name = "fake/fake-1"
    model = "fake-1"
    external = False

    def __init__(self, single=False, bad_suggestion=False):
        self.calls = 0
        self.single = single
        self.bad = bad_suggestion

    def complete_json(self, system, user, schema, **kw):
        self.calls += 1
        items = json.loads(user.split(": ", 2)[-1].split("개): ", 1)[-1])
        out = []
        for it in items:
            t = it["text"]
            if "편리한 순서" in t:
                sugg = t.replace("수행할 수 있다", "수행해도 된다")
                if self.bad:
                    sugg = sugg.replace("다른", "모든")  # 앞부분 변경 → 가드레일에 막혀야 함
                out.append({"id": it["id"], "category": "허용", "compliant": False, "suggestion": sugg,
                            "reason": "허락의 뜻", "confidence": 0.9})  # fmt: skip
            elif "반드시" in t and "법" in t:
                out.append({"id": it["id"], "category": "외적 제약", "compliant": True, "suggestion": None,
                            "reason": "법령 의무", "confidence": 0.9})  # fmt: skip
            elif "반드시" in t:
                out.append({"id": it["id"], "category": "요구사항", "compliant": False,
                            "suggestion": t.replace("반드시 ", ""), "reason": "내부 요구", "confidence": 0.85})  # fmt: skip
            else:
                out.append({"id": it["id"], "category": "가능성/역량", "compliant": True, "suggestion": None,
                            "reason": "능력", "confidence": 0.9})  # fmt: skip
        if self.single:
            return out[0]
        return {"items": out}


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('설명입니다\n```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}
    assert extract_json('앞말 {"a": "}"} 뒷말') == {"a": "}"}
    assert extract_json("없음") is None


def test_normalize_items_shapes():
    one = {"id": "x", "category": "허용"}
    assert normalize_items(one) == [one]
    assert normalize_items([one]) == [one]
    assert normalize_items({"results": [one]}) == [one]
    assert normalize_items({"items": [one]}) == [one]


def test_split_sentences_keeps_decimals():
    text = "하중은 1.5배로 한다. 시험은 23 ℃에서 한다."
    sents = [s for _, _, s in split_sentences(text)]
    assert sents == ["하중은 1.5배로 한다.", "시험은 23 ℃에서 한다."]


def test_guardrails():
    orig = "시험은 편리한 순서에 따라 수행할 수 있다."
    assert guard(orig, "시험은 편리한 순서에 따라 수행해도 된다.") == (True, None)
    ok, why = guard("시료 3개를 쓸 수 있다.", "시료 5개를 써도 된다.")
    assert not ok and "숫자" in why
    ok, why = guard(orig, "모든 시험은 순서에 따라 수행해도 된다.")
    assert not ok and "앞부분" in why
    assert guard("시험자는 반드시 장갑을 착용하여야 한다.", "시험자는 장갑을 착용하여야 한다.") == (
        True,
        None,
    )


def test_judge_single_object_fallback_asks_again():
    llm = FakeLLM(single=True)
    items = [
        {"id": "a", "text": "이 표준의 다른 시험들은 편리한 순서에 따라 수행할 수 있다."},
        {"id": "b", "text": "이 장치는 10 kg을 견딜 수 있다."},
    ]
    js = judge(llm, items)
    assert js["a"].category == "허용" and js["b"].category == "가능성/역량"
    assert llm.calls == 2  # 묶음 1회 + 빠진 문장 1회


DOC_BODY = [
    {"text": "2 시험", "bold": True},
    "이 표준의 다른 시험들은 편리한 순서에 따라 수행할 수 있다.",
    "이 장치는 최대 10 kg의 하중을 견딜 수 있다.",
    "시험자는 반드시 보호 장갑을 착용하여야 한다.",
    "제품은 반드시 전기용품 및 생활용품 안전관리법에 따른 안전인증을 받아야 한다.",
]


def test_rules_with_fake_llm():
    data = make_docx(ks_skeleton(DOC_BODY))
    plain = check_bytes(data, rules="VRB-01,VRB-02").findings
    assert {f.rule_id for f in plain} == {"VRB-01", "VRB-02"}
    assert all(f.source == "rule" for f in plain)
    res = check_bytes(data, rules="VRB-01,VRB-02", llm=FakeLLM())
    by = {(f.rule_id, f.source) for f in res.findings}
    assert ("VRB-02", "llm") in by and ("VRB-01", "llm") in by
    assert len(res.findings) == 2  # 가능성·외적 제약은 지적하지 않음
    v2 = next(f for f in res.findings if f.rule_id == "VRB-02")
    assert v2.suggestion.endswith("수행해도 된다.") and v2.llm_model == "fake-1"
    assert res.doc.meta["llm_modal"]["judged"] >= 3


def test_ai_suggestion_tracked_but_not_in_clean():
    data = make_docx(ks_skeleton(DOC_BODY))
    tr = fix_bytes(data, mode="tracked", rules="VRB-02", llm=FakeLLM())
    d = next(d for d in tr.decisions if d.finding.source == "llm")
    assert d.action == "apply" and tr.invariants["ok"] and not tr.integrity
    import io

    import docx

    texts = [c.text for c in docx.Document(io.BytesIO(tr.output)).comments]
    assert any("AI 제안 · fake-1 · 신뢰도 0.90" in t for t in texts)
    cl = fix_bytes(data, mode="clean", rules="VRB-02", llm=FakeLLM())
    d2 = next(d for d in cl.decisions if d.finding.source == "llm")
    assert d2.action == "suggest"


def test_bad_llm_suggestion_is_discarded():
    data = make_docx(ks_skeleton(DOC_BODY))
    res = check_bytes(data, rules="VRB-02", llm=FakeLLM(bad_suggestion=True))
    f = next(f for f in res.findings if f.rule_id == "VRB-02")
    # 제안 문장만 버리고 '허용' 판정은 남긴다 → 고칠 문장 없는 AI 지적
    assert f.source == "llm" and f.fix is None and f.suggestion is None
    assert "검증을 통과하지 못해" in f.message
    fx = fix_bytes(data, mode="tracked", rules="VRB-02", llm=FakeLLM(bad_suggestion=True))
    assert all(d.action != "apply" for d in fx.decisions) and fx.invariants["ok"]


def test_judge_keeps_category_and_drops_echo_suggestion():
    from ksfix.llm.tasks.modal_verbs import judge, normalize_category

    class Echo:
        model = "echo"

        def complete_json(self, system, user, schema, **kw):
            items = json.loads(user.split("개): ", 1)[-1])
            return {"items": [
                {"id": it["id"], "category": "외적제약", "compliant": True, "suggestion": it["text"]}
                for it in items
            ]}  # fmt: skip

    js = judge(
        Echo(),
        [{"id": "a", "text": "제품은 반드시 인증을 받아야 한다.", "where": "", "role": "body"}],
    )
    j = js["a"]
    assert j.category == "외적 제약" and j.suggestion is None and j.rejected is None
    assert normalize_category("요구 사항") == "요구사항"
    assert normalize_category("가능성·역량") == "가능성/역량"
    assert normalize_category("모름") == "판단보류" and normalize_category(None) == "판단보류"


# ── OpenAI 호환 어댑터(로컬 가짜 서버) ──
class _Handler(BaseHTTPRequestHandler):
    mode = "ok"
    seen: list = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Handler.seen.append(body)
        if _Handler.mode == "no_json_mode" and "response_format" in body:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error":"response_format not supported"}')
            return
        content = '{"items": [{"id": "1", "category": "설명"}]}'
        if _Handler.mode == "garbage":
            content = "죄송합니다. JSON을 만들 수 없습니다."
        resp = {"choices": [{"message": {"content": content}}]}
        data = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture()
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    _Handler.seen = []
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()


SCHEMA = {"required": ["items"], "list": "items", "item_required": ["id", "category"]}


def test_openai_compat_ok_and_cache(server):
    _Handler.mode = "ok"
    c = OpenAICompatClient("t", server, "m", cache=LLMCache(None))
    assert c.complete_json("s", "u", SCHEMA)["items"][0]["category"] == "설명"
    assert c.complete_json("s", "u", SCHEMA)["items"][0]["category"] == "설명"
    assert c.calls == 1 and c.cache_hits == 1
    assert _Handler.seen[0]["temperature"] == 0.0
    assert _Handler.seen[0]["response_format"] == {"type": "json_object"}


def test_openai_compat_falls_back_without_json_mode(server):
    _Handler.mode = "no_json_mode"
    c = OpenAICompatClient("t", server, "m")
    assert c.complete_json("s", "u", SCHEMA)["items"]
    assert "response_format" not in _Handler.seen[-1]


def test_openai_compat_invalid_json_raises(server):
    _Handler.mode = "garbage"
    c = OpenAICompatClient("t", server, "m")
    with pytest.raises(LLMError):
        c.complete_json("s", "u", SCHEMA)
    assert len(_Handler.seen) == 2  # 1회 재시도


def test_connection_failure_and_timeout():
    from ksfix.llm.base import LLMConnectionError

    c = OpenAICompatClient("t", "http://127.0.0.1:9/v1", "m", timeout=2)
    with pytest.raises(LLMConnectionError):
        c.complete_json("s", "u", SCHEMA)


def test_unreachable_llm_stops_and_warns():
    from ksfix.llm.base import LLMConnectionError

    class Down:
        name, model, external = "down/m", "m", False
        calls = 0

        def complete_json(self, *a, **kw):
            Down.calls += 1
            raise LLMConnectionError("연결 실패: 거부됨")

    data = make_docx(ks_skeleton(DOC_BODY))
    res = check_bytes(data, rules="VRB-01,VRB-02", llm=Down())
    assert Down.calls == 1  # 첫 호출에서 서버가 없으면 더 묻지 않는다
    assert {f.source for f in res.findings} == {"rule"}  # 규칙 지적으로 계속
    assert any("LLM 판정 실패" in w and "연결 실패" in w for w in res.warnings)


def test_profiles_and_env_override(monkeypatch):
    names = [p["name"] for p in list_profiles()]
    assert "none" in names and "ollama-exaone" in names and "ollama-gemma" in names
    ext = {p["name"]: p["external"] for p in list_profiles()}
    assert ext["upstage-solar"] is True and ext["ollama-gemma"] is False
    assert make_client("none") is None
    monkeypatch.setenv("KSFIX_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("KSFIX_LLM_MODEL", "my-model")
    c = make_client("env", cache_dir="memory")
    assert c.model == "my-model" and not c.external
    with pytest.raises(KeyError):
        make_client("없는-프로필")

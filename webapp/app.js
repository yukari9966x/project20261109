/* KS-Fix 웹 UI: 업로드 → 옵션 → 결과 → 내려받기. 문서 텍스트는 항상 textContent로 넣는다(XSS 방지). */
(function () {
  "use strict";
  var engine = window.KSFixEngine;
  var $ = function (id) { return document.getElementById(id); };
  var SEV = { error: "오류", warning: "경고", info: "참고" };
  var PILL = { "자동수정": "fixed", "자동수정 가능": "fixed", "제안": "sugg", "AI 제안": "sugg", "판단 필요": "sugg", "검토 필요": "review" };
  var CL_PILL = { pass: "pass", fail: "fail", partial_pass: "part", partial_fail: "fail", manual: "man", not_run: "man" };
  var MODE_HELP = {
    tracked: "자동 수정을 Word 변경 내용으로 남기고, 근거 조항은 메모로 답니다.",
    clean: "자동 수정을 모두 반영한 문서를 만듭니다. 판단이 필요한 항목은 메모로만 남깁니다.",
    check: "문서는 만들지 않고 점검 리포트만 만듭니다."
  };
  var file = null;
  var profiles = [];

  function el(tag, attrs, children) {
    var e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") e.textContent = attrs[k];
      else if (k === "cls") e.className = attrs[k];
      else if (k === "style") Object.assign(e.style, attrs[k]);  // CSSOM(인라인 style 속성은 CSP가 막음)
      else e.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }

  function setStatus(msg, kind) {
    var s = $("status");
    s.textContent = "";
    s.className = "status" + (kind === "err" ? " err" : "");
    if (kind === "busy") s.appendChild(el("span", { cls: "spinner" }));
    s.appendChild(document.createTextNode(msg || ""));
  }

  function pickFile(f) {
    if (!f) return;
    if (!/\.docx$/i.test(f.name)) { setStatus("docx 파일만 처리합니다(HWP·doc는 Word에서 .docx로 저장한 뒤 올려 주세요).", "err"); return; }
    if (f.size > engine.maxMB * 1024 * 1024) { setStatus("파일이 너무 큽니다(최대 " + engine.maxMB + " MB).", "err"); return; }
    file = f;
    $("file-name").textContent = f.name + " (" + Math.ceil(f.size / 1024) + " KB)";
    $("run").disabled = false;
    setStatus("");
  }

  function mode() { return document.querySelector("input[name=mode]:checked").value; }

  function card(k, v, d, cls) {
    return el("div", { cls: "card" }, [el("div", { cls: "k", text: k }), el("div", { cls: "v" + (cls ? " " + cls : ""), text: String(v) }), d]);
  }

  function renderCards(r) {
    var s = r.summary, c = $("cards");
    c.textContent = "";
    var sev = el("div", { cls: "d" }, [
      el("span", { cls: "sev-error", text: "오류 " + s.by_severity.error }), " · ",
      el("span", { cls: "sev-warning", text: "경고 " + s.by_severity.warning }), " · ",
      el("span", { cls: "sev-info", text: "참고 " + s.by_severity.info })]);
    c.appendChild(card("지적", s.findings, sev));
    if (r.mode === "check") c.appendChild(card("자동수정 가능", s.autofixable, el("div", { cls: "d", text: "변경추적으로 고칠 수 있는 지적" })));
    else c.appendChild(card("자동수정", s.applied, el("div", { cls: "d", text: "Word 변경추적으로 반영" })));
    c.appendChild(card("검토 필요", s.needs_review, el("div", { cls: "d", text: "제안·판단 필요(메모)" })));
    var rate = s.pass_rate_before + "%" + (s.pass_rate_after != null ? " → " + s.pass_rate_after + "%" : "");
    c.appendChild(card("규칙 통과율", rate, el("div", { cls: "d", text: (s.pass_rate_after != null ? "교정 전 " : "") + "지적 없는 규칙 " + s.rules_passed + " / " + s.rules_applied })));
    var cs = r.checklist.summary;
    c.appendChild(card("부속서 A 검토 항목", cs.total, el("div", { cls: "d", text: "자동 통과 " + cs.auto_pass + " · 지적 " + cs.auto_fail + " · 부분 " + cs.partial + " · 수동 " + cs.manual })));
    var w = $("warnings");
    w.textContent = "";
    (r.warnings || []).forEach(function (m) { w.appendChild(el("div", { cls: "warn-box", text: "⚠ " + m })); });
    if (r.verification && r.verification.invariants && r.verification.invariants.ok === false)
      w.appendChild(el("div", { cls: "warn-box", text: "⚠ 기술적 내용 불변 검증에 실패해 자동 수정을 모두 철회하고 메모만 남겼습니다." }));
  }

  function renderBars(r) {
    var b = $("bars");
    b.textContent = "";
    if (!r.categories.length) { b.appendChild(el("div", { cls: "muted small", text: "지적이 없습니다." })); return; }
    var max = Math.max.apply(null, r.categories.map(function (c) { return c.count; }));
    r.categories.forEach(function (c) {
      var track = el("div", { cls: "track" }, [
        el("div", { cls: "fill", style: { width: (100 * c.count / max) + "%" } }),
        el("div", { cls: "fixed", style: { width: (100 * c.fixed / max) + "%" } })]);
      b.appendChild(el("div", { cls: "row" }, [el("div", { text: c.name }), track, el("div", { text: c.count + "건" + (c.fixed ? " (" + c.fixed + ")" : "") })]));
    });
  }

  function fillSelect(sel, values, first) {
    sel.textContent = "";
    sel.appendChild(el("option", { value: "", text: first }));
    values.forEach(function (v) { sel.appendChild(el("option", { value: v, text: v })); });
  }

  function renderFindings(r) {
    var tb = document.querySelector("#findings tbody");
    tb.textContent = "";
    r.findings.forEach(function (f) {
      var preview = el("td", null, [el("span", { cls: "snip", text: f.snippet || "" })]);
      if (f.suggestion) { preview.appendChild(el("br")); preview.appendChild(el("span", { cls: "arrow", text: "→ " })); preview.appendChild(document.createTextNode(f.suggestion)); }
      var status = el("td", null, [el("span", { cls: "pill " + (PILL[f.status_label] || ""), text: f.status_label })]);
      if (f.reason) status.appendChild(el("div", { cls: "ref", text: f.reason }));
      var tr = el("tr", { "data-sev": f.severity, "data-cat": f.category || "", "data-status": f.status_label }, [
        el("td", { cls: "nowrap sev-" + f.severity, text: SEV[f.severity] }),
        el("td", { cls: "rule", text: f.rule_id }),
        el("td", { cls: "nowrap", text: f.location || "" }),
        el("td", null, [document.createTextNode(f.message), el("div", { cls: "ref", text: f.clause_ref })]),
        preview, status]);
      tb.appendChild(tr);
    });
    fillSelect($("f-cat"), r.categories.map(function (c) { return c.name; }), "모든 분류");
    var sts = []; r.findings.forEach(function (f) { if (sts.indexOf(f.status_label) < 0) sts.push(f.status_label); });
    fillSelect($("f-status"), sts.sort(), "모든 상태");
    $("tab-btn-findings").textContent = "지적 목록 (" + r.findings.length + ")";
    applyFilters();
  }

  function applyFilters() {
    var sev = [].slice.call(document.querySelectorAll(".f-sev:checked")).map(function (x) { return x.value; });
    var cat = $("f-cat").value, st = $("f-status").value, q = $("f-q").value.trim().toLowerCase(), n = 0;
    [].slice.call(document.querySelectorAll("#findings tbody tr")).forEach(function (tr) {
      var ok = sev.indexOf(tr.dataset.sev) >= 0 && (!cat || tr.dataset.cat === cat) && (!st || tr.dataset.status === st) &&
        (!q || tr.textContent.toLowerCase().indexOf(q) >= 0);
      tr.style.display = ok ? "" : "none"; if (ok) n++;
    });
    $("f-count").textContent = n + "건 표시";
  }

  function renderChecklist(r) {
    var tb = document.querySelector("#checklist tbody");
    tb.textContent = "";
    r.checklist.items.forEach(function (it) {
      var summary = el("td", null, [document.createTextNode(it.summary)]);
      if (it.manual) summary.appendChild(el("div", { cls: "ref", text: "수동: " + it.manual }));
      tb.appendChild(el("tr", null, [
        el("td", { cls: "rule", text: it.id }),
        el("td", null, [document.createTextNode(it.group), el("div", { cls: "ref", text: it.ref })]),
        summary,
        el("td", { cls: "ref", text: (it.rules || []).join(", ") }),
        el("td", null, [el("span", { cls: "pill " + (CL_PILL[it.status] || ""), text: it.label })])]));
    });
    $("tab-btn-checklist").textContent = "부속서 A 체크리스트 (" + r.checklist.items.length + ")";
  }

  function renderDownloads(files) {
    var d = $("downloads");
    d.textContent = "";
    files.forEach(function (f, i) {
      var a = el("a", { href: f.href, download: f.download, cls: i === 0 && /docx$/.test(f.download) ? "main" : "" }, [
        el("span", { text: "⬇" }), el("span", { text: f.label })]);
      d.appendChild(a);
    });
  }

  async function run() {
    if (!file) return;
    var opts = { mode: mode(), rules: $("rules").value || null, llm: $("llm").value || "none" };
    $("run").disabled = true;
    setStatus("처리 중… (문서 크기에 따라 수 초가 걸립니다)", "busy");
    var t0 = performance.now();
    try {
      var res = await engine.process(file, opts);
      var r = res.report;
      renderCards(r); renderBars(r); renderFindings(r); renderChecklist(r); renderDownloads(res.files);
      $("step-result").hidden = false; $("step-download").hidden = false;
      setStatus("완료(" + ((performance.now() - t0) / 1000).toFixed(1) + "초) · 지적 " + r.summary.findings + "건");
      $("step-result").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      setStatus("오류: " + (e && e.message ? e.message : e), "err");
    } finally {
      $("run").disabled = false;
    }
  }

  function bind() {
    var drop = $("drop");
    $("file").addEventListener("change", function (e) { pickFile(e.target.files[0]); });
    ["dragenter", "dragover"].forEach(function (t) { drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.add("over"); }); });
    ["dragleave", "drop"].forEach(function (t) { drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.remove("over"); }); });
    drop.addEventListener("drop", function (e) { if (e.dataTransfer.files.length) pickFile(e.dataTransfer.files[0]); });
    $("run").addEventListener("click", run);
    [].slice.call(document.querySelectorAll("input[name=mode]")).forEach(function (r) {
      r.addEventListener("change", function () { $("mode-help").textContent = MODE_HELP[mode()]; });
    });
    $("llm").addEventListener("change", function () {
      var p = profiles.filter(function (x) { return x.name === $("llm").value; })[0];
      $("llm-warn").hidden = !(p && p.external);
    });
    [].slice.call(document.querySelectorAll(".tabs button")).forEach(function (b) {
      b.addEventListener("click", function () {
        [].slice.call(document.querySelectorAll(".tabs button")).forEach(function (x) { x.classList.remove("on"); });
        [].slice.call(document.querySelectorAll(".tab")).forEach(function (x) { x.classList.remove("on"); });
        b.classList.add("on"); $("tab-" + b.dataset.tab).classList.add("on");
      });
    });
    [].slice.call(document.querySelectorAll(".f-sev")).forEach(function (x) { x.addEventListener("change", applyFilters); });
    $("f-cat").addEventListener("change", applyFilters);
    $("f-status").addEventListener("change", applyFilters);
    $("f-q").addEventListener("input", applyFilters);
  }

  async function init() {
    bind();
    $("max-mb").textContent = engine.maxMB;
    try {
      var info = await engine.init();
      $("engine-badge").textContent = engine.label + " · v" + info.version;
      $("version").textContent = "KS-Fix v" + info.version;
      profiles = await engine.profiles();
      var sel = $("llm");
      profiles.filter(function (p) { return p.name !== "none"; }).forEach(function (p) {
        sel.appendChild(el("option", { value: p.name, text: p.name + (p.model ? " (" + p.model + ")" : "") + (p.external ? " · 외부" : "") }));
      });
    } catch (e) {
      $("engine-badge").textContent = "엔진 연결 실패";
      setStatus("엔진을 시작하지 못했습니다: " + (e && e.message ? e.message : e), "err");
    }
  }
  init();
})();

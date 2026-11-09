/* KS-Fix 엔진(브라우저 데모): engine-server.js와 같은 인터페이스(window.KSFixEngine).
   처리는 Web Worker(pyodide-worker.js) 안에서 하고, 결과 파일은 Blob URL로 내려받는다. LLM은 쓰지 않는다. */
(function () {
  "use strict";
  var DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  var worker = new Worker("pyodide-worker.js");
  var seq = 0;
  var pending = {};
  worker.onmessage = function (ev) {
    var m = ev.data;
    var p = pending[m.id];
    if (!p) return;
    delete pending[m.id];
    if (m.ok) p.resolve(m); else p.reject(new Error(m.error));
  };
  function call(msg, transfer) {
    return new Promise(function (resolve, reject) {
      msg.id = ++seq;
      pending[msg.id] = { resolve: resolve, reject: reject };
      worker.postMessage(msg, transfer || []);
    });
  }
  function blobUrl(data, type) {
    return URL.createObjectURL(new Blob([data], { type: type }));
  }
  window.KSFixEngine = {
    name: "pyodide",
    label: "브라우저(설치 없음)",
    maxMB: 30,
    init: async function () {
      var manifest = await (await fetch("manifest.json")).json();
      var r = await call({ cmd: "init", manifest: manifest });
      return { version: r.version };
    },
    profiles: async function () { return []; },
    process: async function (file, options) {
      var buf = new Uint8Array(await file.arrayBuffer());
      var r = await call({ cmd: "process", bytes: buf, options: options, name: file.name }, [buf.buffer]);
      var stem = file.name.replace(/\.docx$/i, "");
      var files = [];
      if (r.docx) {
        var clean = options.mode === "clean";
        files.push({ key: options.mode, label: clean ? "반영본(.docx)" : "변경추적본(.docx)",
          href: blobUrl(r.docx, DOCX), download: stem + (clean ? ".ksfix-clean.docx" : ".ksfix-tracked.docx") });
      }
      files.push({ key: "report_html", label: "리포트(HTML)", href: blobUrl(r.html, "text/html;charset=utf-8"),
        download: stem + ".ksfix-report.html" });
      files.push({ key: "report_json", label: "리포트(JSON)", href: blobUrl(r.report, "application/json"),
        download: stem + ".ksfix-report.json" });
      if (r.audit) files.push({ key: "audit", label: "감사 로그(JSONL)", href: blobUrl(r.audit, "application/x-ndjson"),
        download: stem + ".ksfix-audit.jsonl" });
      return { report: JSON.parse(r.report), files: files };
    }
  };
})();

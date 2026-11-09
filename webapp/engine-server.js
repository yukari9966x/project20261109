/* KS-Fix 엔진(로컬 서버): app.js는 window.KSFixEngine 인터페이스만 쓴다.
   브라우저 데모는 같은 인터페이스를 engine-pyodide.js로 구현해 교체한다. */
(function () {
  "use strict";
  async function json(res) {
    var body = {};
    try { body = await res.json(); } catch (e) { /* 본문 없음 */ }
    if (!res.ok) {
      var msg = body && body.detail ? body.detail : "처리에 실패했습니다(HTTP " + res.status + ").";
      throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
    return body;
  }
  window.KSFixEngine = {
    name: "server",
    label: "로컬 서버",
    maxMB: 30,
    init: async function () {
      var info = await json(await fetch("/api/v1/health"));
      return { version: info.version };
    },
    profiles: async function () {
      try { return (await json(await fetch("/api/v1/llm/profiles"))).profiles || []; }
      catch (e) { return []; }
    },
    process: async function (file, options) {
      var fd = new FormData();
      fd.append("file", file, file.name);
      fd.append("options", JSON.stringify(options || {}));
      var body = await json(await fetch("/api/v1/process", { method: "POST", body: fd }));
      return {
        report: body.report,
        files: (body.files || []).map(function (f) {
          return { key: f.key, label: f.label, href: f.url, download: f.name, size: f.size };
        })
      };
    }
  };
})();

/* KS-Fix 브라우저 엔진(Web Worker): Pyodide로 서버와 같은 Python 코어(ksfix.api)를 실행한다.
   문서는 브라우저 밖으로 나가지 않는다. Pyodide 버전은 동작을 확인한 버전으로 고정한다. */
"use strict";
var PYODIDE_VERSION = "0.27.2";
var PYODIDE_BASE = "https://cdn.jsdelivr.net/pyodide/v" + PYODIDE_VERSION + "/full/";
importScripts(PYODIDE_BASE + "pyodide.js");

var ready = null;

var PY_SETUP = [
  "import json",
  "from ksfix import __version__",
  "from ksfix.api import check_bytes, fix_bytes",
  "from ksfix.report import build_report, render_html",
  "",
  "def ksfix_process(data, options_json, name):",
  "    if hasattr(data, 'to_bytes'):",
  "        data = data.to_bytes()",
  "    opts = json.loads(options_json)",
  "    mode = opts.get('mode', 'tracked')",
  "    rules = opts.get('rules') or None",
  "    if mode == 'check':",
  "        chk, fix = check_bytes(bytes(data), rules=rules), None",
  "    else:",
  "        fix = fix_bytes(bytes(data), mode=mode, rules=rules)",
  "        chk = fix.check",
  "    report = build_report(chk, fix, source_name=name, input_unchanged=True)",
  "    audit = ''.join(json.dumps(r, ensure_ascii=False) + '\\n' for r in (fix.audit if fix else []))",
  "    return {'report': json.dumps(report, ensure_ascii=False), 'html': render_html(report),",
  "            'docx': (fix.output if fix is not None else None), 'audit': audit}",
].join("\n");

async function init(manifest) {
  var py = await loadPyodide({ indexURL: PYODIDE_BASE });
  await py.loadPackage(["lxml", "pyyaml", "jinja2", "micropip", "typing-extensions"]);
  var micropip = py.pyimport("micropip");
  var base = new URL("./", self.location.href).href;
  var urls = manifest.wheels.map(function (w) { return base + "wheels/" + w; });
  await micropip.install(urls, { deps: false });
  py.runPython(PY_SETUP);
  return py;
}

self.onmessage = async function (ev) {
  var msg = ev.data;
  try {
    if (msg.cmd === "init") {
      ready = ready || init(msg.manifest);
      var py = await ready;
      self.postMessage({ id: msg.id, ok: true, version: py.runPython("__version__") });
      return;
    }
    if (msg.cmd === "process") {
      var py2 = await ready;
      var fn = py2.globals.get("ksfix_process");
      var res = fn(msg.bytes, JSON.stringify(msg.options || {}), msg.name);
      var obj = res.toJs({ dict_converter: Object.fromEntries });
      res.destroy();
      fn.destroy();
      var transfer = obj.docx ? [obj.docx.buffer] : [];
      self.postMessage(
        { id: msg.id, ok: true, report: obj.report, html: obj.html, docx: obj.docx || null, audit: obj.audit },
        transfer
      );
    }
  } catch (e) {
    self.postMessage({ id: msg.id, ok: false, error: String((e && e.message) || e) });
  }
};

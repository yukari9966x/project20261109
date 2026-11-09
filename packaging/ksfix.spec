# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 스펙: pyinstaller packaging/ksfix.spec --noconfirm  →  dist/ksfix/ksfix(.exe)
# PyInstaller는 GPL + 부트로더 예외 라이선스로, 만든 실행파일의 배포는 허용된다(THIRD_PARTY_NOTICES.md 참고).
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent

datas = collect_data_files("ksfix")  # 규칙팩 YAML·정형문·리포트 템플릿·프롬프트
datas += collect_data_files("docx")  # python-docx 기본 템플릿
datas += [(str(ROOT / "webapp"), "ksfix/webapp")]
datas += [(str(p), "samples") for p in sorted((ROOT / "samples").glob("*.docx"))]

hiddenimports = collect_submodules("ksfix") + collect_submodules("uvicorn") + ["python_multipart", "multipart"]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "numpy", "PIL", "pytest", "IPython"],
    noarchive=False,
    # python-docx는 __file__ 기준 상대 경로(docx/parts/../templates)로 템플릿을 읽는다 → .py도 디스크에 둔다
    module_collection_mode={"docx": "pyz+py"},
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ksfix",
    console=True,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ksfix")

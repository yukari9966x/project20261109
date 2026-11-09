"""입력 검증·원본 보호: 크기 한도, zip bomb, 암호화·매크로 문서, XXE(DOCTYPE/ENTITY) 차단."""

from __future__ import annotations

import hashlib
import io
import zipfile

MB = 1024 * 1024
DEFAULT_MAX_BYTES = 30 * MB
MAX_UNCOMPRESSED = 400 * MB
MAX_ENTRIES = 5000
MAX_RATIO = 250  # 큰 항목의 압축 비율 상한
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class InputError(ValueError):
    """사용자에게 그대로 보여 줄 수 있는 입력 오류(한국어 메시지)."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_docx(data: bytes, max_bytes: int = DEFAULT_MAX_BYTES) -> str:
    """docx bytes를 검사하고 SHA-256을 돌려준다. 문제가 있으면 InputError."""
    if not data:
        raise InputError("빈 파일입니다.")
    if len(data) > max_bytes:
        raise InputError(f"파일이 너무 큽니다(최대 {max_bytes // MB} MB).")
    if data[:8] == OLE_MAGIC:
        raise InputError(
            "암호화된 문서이거나 이전 Word(.doc) 형식입니다. 암호를 풀고 .docx로 저장한 뒤 다시 시도하세요."
        )
    if not data.startswith(b"PK"):
        raise InputError("docx(zip) 형식이 아닙니다. Word에서 .docx로 저장한 파일을 넣어 주세요.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
            if len(infos) > MAX_ENTRIES:
                raise InputError("문서 내부 파일 수가 너무 많습니다(압축 폭탄 의심).")
            total = 0
            names = set()
            for info in infos:
                names.add(info.filename)
                total += info.file_size
                if info.file_size > 10 * MB and info.compress_size > 0:
                    if info.file_size / info.compress_size > MAX_RATIO:
                        raise InputError("압축 비율이 비정상적으로 높습니다(압축 폭탄 의심).")
                if info.flag_bits & 0x1:
                    raise InputError("암호화된 zip 항목이 있습니다.")
            if total > MAX_UNCOMPRESSED:
                raise InputError("압축을 푼 크기가 너무 큽니다(압축 폭탄 의심).")
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise InputError("Word 문서(docx)가 아닙니다.")
            if any(n.lower().endswith("vbaproject.bin") for n in names):
                raise InputError("매크로가 포함된 문서(.docm)는 처리하지 않습니다.")
            ctypes = z.read("[Content_Types].xml")
            if b"macroEnabled" in ctypes:
                raise InputError("매크로가 포함된 문서(.docm)는 처리하지 않습니다.")
            for name in names:
                low = name.lower()
                if not (low.endswith(".xml") or low.endswith(".rels")):
                    continue
                with z.open(name) as fh:
                    head = fh.read(4096)
                if b"<!DOCTYPE" in head or b"<!ENTITY" in head:
                    raise InputError("DTD/엔터티 선언이 있는 XML은 처리하지 않습니다(XXE 방지).")
            bad = z.testzip()
            if bad is not None:
                raise InputError(f"손상된 docx 파일입니다(내부 파일 {bad}).")
    except zipfile.BadZipFile as exc:
        raise InputError("손상된 docx 파일입니다.") from exc
    except (zipfile.LargeZipFile, NotImplementedError, RuntimeError) as exc:
        raise InputError(f"docx를 읽을 수 없습니다: {exc}") from exc
    return sha256(data)

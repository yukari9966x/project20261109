import hashlib
import io
import json
import zipfile

import pytest

from ksfix.io import InputError, validate_docx
from ksfix.model import build


def test_samples_parse_and_roles_align(samples_dir, sample_bytes):
    for name, data in sample_bytes.items():
        doc = build(data)
        prefix = "_".join(name.split("_")[:2])
        roles = json.loads((samples_dir / f"{prefix}_roles.json").read_text(encoding="utf-8"))
        assert len(roles) == len(doc.paras), name


def test_input_bytes_untouched(sample_bytes):
    data = sample_bytes["sample_02_clean"]
    before = hashlib.sha256(data).hexdigest()
    doc = build(data)
    assert doc.meta["sha256"] == before
    assert hashlib.sha256(data).hexdigest() == before


def test_clean_sample_numbering(sample_bytes):
    doc = build(sample_bytes["sample_02_clean"])
    labels = [p.num_label for p in doc.paras if p.num_label]
    # Heading 2 이하는 Heading 1에서 numId를 상속(ilvl만 지정)
    for want in ("1", "2", "3", "3.1", "3.3", "4", "4.1", "4.2", "5.3", "6.2", "7"):
        assert want in labels
    # 부속서: lvl/pStyle 연결로 수준 결정, 하위 수준은 문자 번호를 쓴다
    assert "부속서 A" in labels and "부속서 B" in labels
    assert labels.index("부속서 A") < labels.index("A.1") < labels.index("부속서 B")
    assert "B.2" in labels
    assert "비고" in labels and "a)" in labels and "c)" in labels
    assert doc.meta["sections"] == 5
    assert doc.meta["has_toc_field"]


def test_start_override_gap(sample_bytes):
    doc = build(sample_bytes["sample_01_violations"])
    heads = [p for p in doc.paras if p.text == "포장"]
    assert heads and heads[0].num_label == "8"
    assert any(t.nested for t in doc.tables)


def test_caption_seq_field_visible(sample_bytes):
    doc = build(sample_bytes["sample_02_clean"])
    caps = [p for p in doc.paras if p.text.startswith("표 1 —")]
    assert caps and caps[0].has_field
    assert not caps[0].is_editable(2, 3)  # SEQ 필드 결과(번호)는 수정 금지


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return buf.getvalue()


@pytest.mark.parametrize(
    "data, msg",
    [
        (b"", "빈 파일"),
        (b"hello", "docx(zip)"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 100, "암호화"),
        (_zip({"a.txt": b"x"}), "Word 문서"),
        (
            _zip(
                {
                    "[Content_Types].xml": b"<Types/>",
                    "word/document.xml": b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x/>',
                }
            ),
            "XXE",
        ),
        (
            _zip(
                {
                    "[Content_Types].xml": b"<Types/>",
                    "word/document.xml": b"<x/>",
                    "word/vbaProject.bin": b"0",
                }
            ),
            "매크로",
        ),
    ],
)
def test_validate_rejects_bad_inputs(data, msg):
    with pytest.raises(InputError) as exc:
        validate_docx(data)
    assert msg in str(exc.value)


def test_validate_size_limit(sample_bytes):
    data = sample_bytes["sample_02_clean"]
    with pytest.raises(InputError, match="너무 큽니다"):
        validate_docx(data, max_bytes=1000)

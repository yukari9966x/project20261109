"""local_samples/의 실제 KS 문서가 있을 때만 실행(CI에서는 건너뜀). 문서 내용은 출력하지 않는다."""

import re
import time

from ksfix.io import read_input
from ksfix.model import build


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def test_real_docs_parse_fast(real_docs):
    for path in real_docs:
        t0 = time.perf_counter()
        doc = build(read_input(path))
        assert doc.paras, path.name
        assert time.perf_counter() - t0 < 15


def test_toc_cache_labels_match_resolved_numbering(real_docs):
    """목차 필드 캐시("5.1→시험 조건→2")의 번호와 자동번호 해석 결과가 같아야 한다."""
    for path in real_docs:
        doc = build(read_input(path))
        heads: dict[str, set[str]] = {}
        for p in doc.paras:
            if p.attrs["in_toc"] or not p.num_label:
                continue
            if re.fullmatch(r"\d+(\.\d+)*", p.num_label):
                heads.setdefault(norm(p.text), set()).add(p.num_label)
        checked = mismatched = 0
        for p in doc.paras:
            if not p.attrs["in_toc"]:
                continue
            parts = p.text.split("\t")
            if len(parts) < 3 or not re.fullmatch(r"\d+(\.\d+)*", parts[0].strip()):
                continue
            found = heads.get(norm(parts[1]))
            if found is None:
                continue  # 목차 캐시가 낡은 경우(TOC-02 대상)는 번호 해석 검증에서 제외
            checked += 1
            if parts[0].strip() not in found:
                mismatched += 1
        assert checked >= 10, path.name
        assert mismatched == 0, path.name


def test_real_docs_structure_boundaries(real_docs):
    """앞부분·본체·참고문헌·해설·뒤표지 경계와 절 번호 연속성(내용은 출력하지 않는다)."""
    from ksfix.api import analyze

    for path in real_docs:
        doc = analyze(read_input(path))
        parts = doc.meta["parts"]
        for key in ("cover", "front", "body", "biblio", "commentary", "back_cover"):
            assert key in parts, (path.name, key)
        assert parts["front"][1] < parts["body"][0] < parts["biblio"][0] < parts["commentary"][0]
        tops = [n.number for n in doc.tree.children if n.kind == "clause"]
        assert tops == [str(i) for i in range(1, len(tops) + 1)], path.name
        assert doc.meta["std_number"] and doc.meta["std_number"].startswith("KS")
        assert doc.meta["title_ko"] and doc.meta["title_en"]

# 결과 예시 (examples)

설치·실행하지 않고도 KS-Fix의 결과를 볼 수 있도록 합성 표준안을 처리한 결과를 둡니다(LLM 끔, v1.0.0).
다시 만들기: `python scripts/make_examples.py` (규칙을 바꾸고 다시 만들지 않으면 `tests/golden/test_examples.py`가 알려 줍니다).

| 파일 | 입력 | 내용 |
|---|---|---|
| [sample_01_violations.ksfix-tracked.docx](sample_01_violations.ksfix-tracked.docx) | `samples/sample_01_violations.docx` | 변경추적본 — Word에서 열면 고친 곳마다 변경 표시와 근거 메모 |
| [sample_01_violations.ksfix-clean.docx](sample_01_violations.ksfix-clean.docx) | 〃 | 반영본 — 자동 수정을 반영하고 판단이 필요한 항목만 메모 |
| [sample_01_violations.ksfix-report.html](sample_01_violations.ksfix-report.html) | 〃 | 리포트(내려받아 브라우저로 열기): 요약·구조·지적 목록·부속서 A 체크리스트·검증 |
| [sample_01_violations.ksfix-report.json](sample_01_violations.ksfix-report.json) | 〃 | 같은 리포트의 JSON |
| [sample_01_violations.ksfix-audit.jsonl](sample_01_violations.ksfix-audit.jsonl) | 〃 | 감사 로그: 지적·편집마다 규칙·문단·전후 텍스트·결정 |
| [sample_02_clean.ksfix-report.html](sample_02_clean.ksfix-report.html) | `samples/sample_02_clean.docx` | 정상본 점검 리포트 — 오류·경고 0건(‘할 수 있다’ 의미 확인 요청 참고 3건) |
| [sample_02_clean.ksfix-report.json](sample_02_clean.ksfix-report.json) | 〃 | 같은 리포트의 JSON |

샘플 1 요약: 지적 57건(오류 13 · 경고 40 · 참고 4) · 자동수정 25건 · 제안 3건 · 검토·판단 필요 29건(메모) · 규칙 통과율 0 % → 51.1 % · 기술적 내용 불변·출력 무결성·입력 불변 검증 통과

모든 입력은 직접 만든 가상의 표준안(‘KS X 9999 디지털 체중계’)이며 실제 KS 문서의 내용이 없습니다.

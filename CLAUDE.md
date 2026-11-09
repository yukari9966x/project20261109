# CLAUDE.md — KS-Fix

## 프로젝트
KS(한국산업표준) 표준안 .docx를 KS A 0001:2023에 맞춰 점검·교정하는 도구.
- 상세 계획: docs/PLAN.md (항상 우선 참고) · 진행 기록: docs/PROGRESS.md
- 마감: 2026-11-11(수) 공공 GitLab 등록 후 동결. Phase 6 = 제출 가능 최소선.

## 명령
- 설치: `pip install -e ".[dev,web]"` (가상환경 권장)
- 샘플 생성: `python scripts/make_samples.py`
- 전체 검사: `python scripts/check.py` (ruff + pytest + 샘플 처리)
- 점검: `ksfix check <docx> -o out/`
- 교정: `ksfix fix <docx> -o out/ --mode tracked|clean [--llm <profile>]`
- 구조 보기: `ksfix inspect <docx>`
- 규칙 목록: `ksfix rules [--markdown]`
- 웹: `ksfix serve` → http://127.0.0.1:8765
- LLM 평가: `ksfix eval --profiles ollama-exaone,ollama-gemma`

## 구조
src/ksfix/{io,model,classify,rules,fix,llm,report,web}
- 코어(io~report)는 순수 Python: 네트워크·subprocess·전역 상태 금지, bytes → bytes (api.process_bytes)
- 규칙 = rules/packs/ksa0001_2023/catalog.yaml(메타데이터) + 분류별 모듈(@rule 데코레이터)
- 웹 UI = webapp/(정적, CDN 금지) — 서버 엔진과 Pyodide 엔진이 같은 UI를 공유

## 규칙 추가 절차
1. catalog.yaml에 메타데이터(id, title, clause, category, severity, method, autofix, priority)
2. 구현 + 양성·음성 단위 테스트 각 1개 이상
3. scripts/make_samples.py에 위반 사례 추가, samples/*_expected.json 갱신
4. `ksfix rules --markdown > docs/RULES.md`

## 반드시 지킬 것
- 입력 파일은 읽기 전용. 산출물은 별도 디렉터리.
- 기술적 내용(수치·단위·표준번호·표 값) 변경 금지 — fix/invariants.py를 통과 못 한 편집은 철회.
- 필드 코드·필드 결과·수식(OMML)·그림·텍스트 상자·기존 변경추적·기존 메모는 건드리지 않는다. 애매하면 자동 수정 대신 메모.
- local_samples/(실제 KS 문서)는 커밋 금지, 외부 LLM API 전송 금지.
- KS 원문을 저장소에 복제하지 않는다(정형문·짧은 인용만). 규칙 설명은 요약해서 쓴다.
- LLM 없이(--llm none) 모든 핵심 기능이 동작해야 한다. LLM 테스트는 FakeLLM으로.
- 사용자에게 보이는 문자열은 한국어, 코드 식별자는 영어. 파일명은 ASCII.
- 비밀값은 .env(커밋 금지). .env.example만 커밋.
- GitHub 저장소 생성·공개 전환, GitLab 푸시, 태그 생성은 사용자 확인 후.
- 제출 동결 태그(v1.0.0) 이후 GitLab에 푸시 금지.

## 작업 방식
- Phase 단위로 진행: check.py 통과 → PROGRESS.md 갱신 → 커밋 → push → 5줄 보고.
- P1이 30분 이상 막히면 중단·기록 후 다음으로. P2는 로드맵에만.
- Python 3.11+, 타입 힌트, ruff, pytest. 작은 커밋, Conventional Commits(feat/fix/docs/test/chore).

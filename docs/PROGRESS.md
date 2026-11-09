# 진행 기록 (PROGRESS)

계획: [PLAN.md](PLAN.md) · 마감 2026-11-11(수) · Phase 6 = 제출 가능 최소선

## 현재 상태

| Phase | 내용 | 상태 |
|---|---|---|
| 0 | 저장소 부트스트랩 | 완료(CI 초록불) |
| 1 | 합성 표준안 생성기 + IR + 자동번호 | 완료 |
| 2 | 구조 인식 | 완료 |
| 3 | 규칙 엔진 + 첫 규칙 8종 | 완료(+VRB-01·02) |
| 4 | 수정 엔진(변경추적·메모) + 불변성 | 완료 |
| 5 | 리포트 | 완료 |
| 6 | 웹 UI + Docker ★ 제출 가능 최소선 | 완료(v0.9.0) |
| 7 | LLM 계층 + 모델 2종 평가 | 완료(평가표 추가 예정) |
| 8 | 규칙 확장 | 대기 |
| 9 | 배포 산출물(P1) | 대기 |
| 10 | 문서화·제출 패키지 | 대기 |
| 11 | 공공 GitLab 이관·동결 | 대기 |

## 작업 환경 메모

- GitHub 저장소: 이미 만들어진 `yukari9966x/project20261109`를 원격(origin)으로 쓴다(`gh repo create` 단계 생략).
- 개발 브랜치: 이 세션은 `claude/fervent-mccarthy-x1tvo3`에 커밋·푸시한다. `main` 반영(병합)은 사용자가 결정한다.
- 실제 KS 문서: `local_samples/`(미커밋) — KS C IEC 60974-11, KS C IEC 60384-22, `reference/` KS A 0001:2023(.doc).
- 개발 환경: Python 3.12 가상환경(`.venv`), LibreOffice 24.2 있음(렌더링 검사 가능).

## Phase 기록

### Phase 0 — 저장소 부트스트랩 (2026-11-09)

- 한 일: `.gitignore`(local_samples·out·.env 등), `.gitattributes`, `pyproject.toml`(hatchling, src 레이아웃, extras web/llm/dev/exe, 진입점 `ksfix`), `CLAUDE.md`(부록 A 원문), `docs/PLAN.md`(원문), README 골격, `LICENSE`(가칭 MIT + 기관 확인 필요), `.env.example`, `config/llm_profiles.example.yaml`, `scripts/check.py`(ruff·format·저장소 위생·pytest·샘플 처리), `.github/workflows/ci.yml`, `.gitlab-ci.yml`(기본 비활성), CLI 골격(`ksfix --version`, `--help`, 하위 명령 6종 자리).
- 검사: `python scripts/check.py` 통과.
- 남은 일: Phase 1부터.
- 알려진 문제: 없음.

### Phase 1 — 합성 표준안 생성기 + 문서 모델(IR) + 자동번호 해석 (2026-11-09)

- 한 일
  - `model/`: `ir.py`(Role·Span·Para·Table·KSDoc), `styles.py`(스타일 ID 대신 이름·basedOn 체인으로 해석), `numbering.py`(abstractNum·num·lvlOverride/startOverride·lvl/pStyle 연결·하위 수준 초기화·문자/로마/가나다 서식), `text.py`(보이는 텍스트·span 매핑, 문단을 넘는 필드 상태 기계, 필드 결과·기존 w:ins·다중 w:t 런은 수정 금지 표시), `builder.py`(본문·표·sdt 순회, 구역 번호, 정렬·굵게·한글 비율·기존 변경추적·메모 수 메타)
  - `io/safety.py`(크기 30 MB·zip bomb·암호화/OLE·매크로·DOCTYPE/ENTITY 차단), `io/loader.py`
  - `scripts/make_samples.py`: KSDT 유사 스타일(Heading 1~6 다단계 번호, Heading 2 이하는 numId 상속), `[KSDT] 표제목`·`그림제목`·`부속서 A`(lvl/pStyle 연결), SEQ 필드 캡션, TOC 필드, zlib PNG 그림. 샘플 3종 + `sample_0N_roles.json` + `sample_01_expected.json`(52건: P0 20종·P0b 27종 전부 + P1 일부). zip 시각 고정으로 재생성 결과가 같다
  - `ksfix inspect FILE [--json] [--all]`, `assets/boilerplate.yaml`(부록 E 정형문)
- 확인 사항(실제 KS 문서, 로컬 전용)
  - 두 문서 모두 파싱 성공(0.2초·0.6초). 목차 필드 캐시 번호와 자동번호 해석 결과 일치: 60974-11 25/25, 60384-22 45/45
  - 60974-11 목차 캐시에 "8.1 직접 접촉 **장지**"(본문 제목은 "방지") → 목차 미갱신 실사례(TOC-02 시연 소재)
  - 특허 정형문: KS A 0001 부속서 E 예시는 "출원공개 **후의**", KS A 0001 자체 머리말·발간본은 "출원공개 **이후의**" → 두 형태 모두 허용하도록 정형문 자산에 반영
  - 실제 문서의 부속서 제목은 한 문단에 `부속서 A`(자동번호) + 줄바꿈 + `(규정)` + 제목이 함께 있다. 참고문헌·해설 제목은 `[KSDT] 머리말 제목` 스타일을 쓴다. "비고" 라벨이 자동번호(lvlText "비고")로 생성되는 경우가 있다
- 검사: `python scripts/check.py` 통과(pytest 34건, 실제 문서 테스트 포함). Phase 4 전까지 샘플 처리 단계는 `ksfix inspect`로 대체
- 남은 일: Phase 2(구조 인식)
- 알려진 문제: 텍스트 상자 안 문단은 블록으로 다루지 않는다(자동 수정 금지 구역). 번호 카운터는 abstractNum 단위(대부분의 Word 문서와 동일)

### Phase 2 — 구조 인식 (2026-11-09)

- 한 일
  - `classify/patterns.py`(캡션·비고·표준번호·손번호 등 공용 정규식), `classify/heuristics.py`(1차: 스타일 이름·자동번호 라벨·텍스트 패턴·서식으로 문단별 후보 역할과 신뢰도, 2차: 구역 상태 기계 — 표지→표지 뒷면→목차→머리말→개요→제목→본체(적용범위·인용표준·용어와 정의·일반 절)→부속서→참고문헌→해설→뒤표지), `classify/tree.py`(절·부속서 트리, 문단별 소속 절 번호, 부분 경계)
  - 손번호 제목은 직전 절 번호에 이어지는 번호일 때만 인정(그림 범례 "1→용접봉 홀더" 오인 방지), 표지·뒤표지는 구역 단위로 판정, 부속서 제목 한 문단 안의 (규정)/(참고)·제목 파싱, 용어 항목 두 형식(자동번호 Heading+줄바꿈 / 손입력 "3.1"+다음 문단) 처리
  - 메타: 표준번호·국문/영문 제목·부합화(IDT 추정)·KS A 0001 적용 대상 여부(한글 비율 ≥ 30 %)·저신뢰 블록 수
- 결과
  - 샘플 역할 정확도: sample_01 166/166, sample_02 151/151, sample_03 116/116 (각 100 %)
  - 실제 문서 경계(`ksfix inspect`·로컬 확인): 두 문서 모두 표지 → 표지 뒷면 → 목차 → 머리말 → 개요 → 제목(표준번호·국문·영문, 60974-11은 제목이 1×1 표 안) → 본체(1~12절 / 1~8절) → (부속서 A·B·C·X, 60384-22) → 참고문헌 → 해설 → 뒤표지 순으로 정확히 구분. 60384-22의 부속서 B 하위 절(B.1~B.4)은 손으로 친 번호임을 확인(NUM-05 대상)
  - 저신뢰(< 0.6) 블록: 두 실제 문서 모두 0개
- 검사: `python scripts/check.py` 통과(pytest 45건, §4.3 함정 2·3·11·12 테스트 포함)
- 남은 일: Phase 3(규칙 엔진 + 첫 규칙 8종)
- 알려진 문제: 구조가 KS 형태가 아닌 문서는 "시작" 구역에서 BODY(신뢰도 0.5)로 남는다 → 규칙 일부 건너뜀(LLM 보조 T2는 Phase 7)

### Phase 3 — 규칙 엔진 + 첫 규칙 (2026-11-09)

- 한 일
  - `rules/base.py`(Finding·FixSpec), `registry.py`(@rule 등록, catalog 검증 — 구현 ID ⊆ catalog, 우선순위·ID로 규칙 선택, 규칙별 예외 격리 → `ksfix.internal` 진단), `context.py`(매개변수·정형문·화이트리스트·LLM 자리)
  - `packs/ksa0001_2023/catalog.yaml`: 계획서 §4.2 규칙 84종(81 + 신뢰성 3) 메타데이터 전부(근거 조항은 KS A 0001 원문의 절 번호로 확인 — 예: 연속부호 H.3.4, 표 제목 J.2.3, 숫자 표시 J.3)
  - 규칙 10종: BLT-03, BLT-04, PUN-02, QTY-01, QTY-04, TBL-01, FIG-01, REF-01 (+ 함정 8 검증용 P0 규칙 VRB-01, VRB-02 규칙 부분)
  - `ksfix check FILE -o OUT [--rules] [--fail-on]`(JSON 리포트 + 콘솔 요약), `ksfix rules [--markdown]` → `docs/RULES.md` 생성
- 결과
  - 샘플 1: 구현 규칙의 주입 위반 100 % 탐지 / 샘플 2: 오류·경고 0건(참고 VRB-02 판단 필요 3건)
  - 실제 문서(로컬): 계획서 §2.2 프로토타입 수치 재현 — 60974-11 연속부호 17건·"1 000V" 1건, 60384-22 연속부호 30건·"표 13 —최대" 검출. 프로토타입의 오탐("그룹 1A")은 코드 꼴 판정으로 제거, "개별 규격의 1.9" 같은 다른 문서 참조도 제외
  - 60384-22 용어 정형문 변형("…KS C IEC 60384-1 및 다음의 용어와 정의를 적용한다.") → 둘째 정형문 꼴로 제안
  - §4.3 함정 1·2·4·6·7·8 테스트 통과
- 검사: `python scripts/check.py` 통과(pytest 70건). 샘플 처리 단계는 Phase 4 전까지 `ksfix check`
- 남은 일: Phase 4(수정 엔진·변경추적·메모·불변성)
- 알려진 문제: VRB-02는 LLM이 꺼져 있으면 "판단 필요(info)"만 낸다(Phase 7에서 LLM 판정)

### Phase 4 — 수정 엔진(변경추적·메모) + 불변성 (2026-11-09)

- 한 일
  - `fix/textedit.py`: 보이는 텍스트 오프셋 → 런 분할(서식 복사) → `w:del`(w:t→w:delText) + `w:ins`, clean은 직접 반영. 교체는 단어 단위 최소 차이로 쪼개 변경 표시를 작게("필요하다"→"필**수적이**다")
  - `fix/paragraphs.py`(문단 삽입·삭제·이동 — 문단 표시와 런 모두 추적), `fix/styles.py`(스타일·정렬 변경 → `w:pPrChange`), `fix/comments.py`(python-docx 1.2.0 Comments로 본문 생성, 범위 표시·참조 런은 w:ins 바깥에 직접 배치, 기존 메모 보존), `fix/settings.py`(`w:updateFields` — 스키마 순서 준수), `fix/revisions.py`(ID = 문서 전체 w:id 최댓값 + 1000부터, 메모 ID도 같은 발급기 사용)
  - `fix/planner.py`: 겹침 해소(우선순위 → 심각도 → 넓은 구간), 다른 수정에 포함된 지적은 "포함"으로 처리, 수정 금지 구역·판단 필요·AI 제안·기존 변경추적 문서는 메모로 강등, **INV-01 사전 점검**(편집 전후 수치·단위·표준번호·표 셀 토큰 비교)
  - `fix/invariants.py`: 문서 전체 토큰 다중집합 비교(허용 정규화만) + **INV-03 무결성**(재열기·XML·변경추적/메모 ID 중복·메모 범위 짝). 결과 검증 실패 시 편집 전체 철회 후 메모만 남긴 문서로 재생성
  - `api.fix_bytes()`(점검→계획→적용→재점검→검증), `ksfix fix FILE -o OUT --mode tracked|clean|report` → `.ksfix-tracked.docx`/`.ksfix-clean.docx`, `.ksfix-report.json`, `.ksfix-audit.jsonl`. **INV-02**: 입력 파일 해시를 처리 전후 비교, 출력 경로가 입력과 같으면 거부
- 결과
  - 샘플 1(tracked): 자동수정 7건·메모 11건(지적 수와 같음), 규칙 통과율 0 % → 70 %, 불변성·무결성·입력 불변 통과. clean 재점검 시 자동 수정 가능 지적 0건
  - LibreOffice 24.2 PDF 변환 성공, 렌더링에서 삭제·삽입·변경 표시줄 확인(그림·표 제목, 허용오차 괄호, 정형문 최소 차이, 삽입 문단)
  - 실제 문서(로컬): 60974-11 0.96초·자동수정 17건·기존 메모 2건 보존, 60384-22 3.17초·자동수정 30건 — 둘 다 불변성·무결성 통과, PDF 변환 성공
- 검사: `python scripts/check.py` 통과(pytest 87건). 샘플 처리 단계를 계획서대로 `ksfix fix … --mode tracked`로 전환
- 사용자 확인 필요: 변경추적본을 Word로 열어 수락·거절, 메모 표시 확인. LibreOffice는 삽입 문단 바로 뒤의 자동번호를 "3.2[3.1]"처럼 옛 번호와 함께 표시함(Word 표시 확인 필요)
- 남은 일: Phase 5(리포트)

### Phase 5 — 리포트 (2026-11-09)

- 한 일
  - `report/json_report.py`: 한 dict로 요약(지적·자동수정·검토 필요·규칙 통과율 전→후)·분류별 집계·지적 목록(위치·상태·사유)·체크리스트·검증(INV-01/02/03)·재점검·처리 시간·규칙팩·LLM 정보
  - `report/html_report.py` + `templates/report.html.j2`: 단일 HTML(CSS·JS 인라인, 외부 리소스 없음, 인쇄 대응). 요약 카드, 분류별 막대(자동수정 비율 겹쳐 표시), 지적 목록(심각도·분류·상태·검색 필터), 부속서 A 체크리스트 탭, 문서·처리 정보 탭. JSON을 HTML에 그대로 내장해 수치 일치를 보장
  - `report/checklist.py` + `packs/ksa0001_2023/checklist.yaml`: 부속서 A 검토 항목을 규칙에 매핑(자동 통과 / 자동 지적 n건 / 부분 자동 / 수동 확인)
  - CLI `check`·`fix`가 `.ksfix-report.html`·`.ksfix-report.json`(+ `fix`는 `.ksfix-audit.jsonl`)을 쓴다
- **계획서와 다른 점**: KS A 0001:2023 원문 부속서 A의 검토 항목은 **53개**(표 54행 = 머리행 1 + 항목 53, 구분 18개)다. 계획서 §4.4의 구분별 개수 합도 53이다. 체크리스트는 53개로 구현했고, README·신청서에도 53개로 쓴다(계획서의 "54개"는 표 행 수로 보임)
- 결과: Playwright 스크린샷으로 HTML 표시 확인(요약 카드·분류 막대·지적 표·체크리스트). 오프라인 단일 파일·HTML 수치 = JSON 수치·체크리스트 53항목 상태 표시 테스트 통과
- 검사: `python scripts/check.py` 통과(pytest 93건)
- 남은 일: Phase 6(웹 UI + Docker, 제출 가능 최소선)

### Phase 6 — 웹 UI + Docker ★ 제출 가능 최소선 (2026-11-09, v0.9.0)

- 한 일
  - `web/app.py`(FastAPI): `GET /api/v1/health`·`/rules`·`/llm/profiles`, `POST /api/v1/process`(multipart: file + options JSON → 요약·리포트·내려받기 URL), `GET /api/v1/files/{job}/{key}`. 기본 바인딩 127.0.0.1, 업로드 한도 30 MB(Content-Length·실제 읽기 양쪽 검사), 작업별 임시 디렉터리 1시간 뒤 삭제, 내려받기 경로는 작업 ID(32자리 hex)·고정 키만 허용, 문서 내용은 로그에 남기지 않음, 한글 파일명은 RFC 5987로 내려받기
  - `webapp/`(정적, 한국어, CDN 없음): 끌어놓기 업로드 → 출력·규칙 범위·LLM 선택(외부 프로필이면 전송 경고) → 요약 카드·분류 막대·지적 목록(필터)·부속서 A 체크리스트 → 내려받기. 문서 텍스트는 모두 textContent로 넣음(XSS 방지). 엔진 인터페이스(`window.KSFixEngine`)를 `engine-server.js`로 분리 → 브라우저 데모(Pyodide)가 같은 UI 재사용 가능
  - `ksfix serve [--host] [--port] [--open]`, 휠에 `webapp/` 포함(설치형·편집형 모두 정적 파일 찾음)
  - `Dockerfile`(python:3.12-slim, `.[web,llm]`, 비루트 사용자, 헬스체크, TLS 검사 프록시 망용 선택 비밀값 `pip_ca`), `docker-compose.yml`(127.0.0.1에만 노출, 읽기 전용 파일시스템 + /tmp tmpfs), `.dockerignore`(`local_samples/` 제외), CI에 Docker 빌드·실행 검사 작업 추가
- 결과
  - FastAPI TestClient E2E 6건(샘플 1 업로드 → 변경추적본 내려받기 → python-docx 재열기, 점검 모드, 잘못된 입력·크기 초과, 경로 조작 차단, 정적 UI)
  - 실제 서버 + Playwright로 화면 조작 확인(업로드 → 0.4초 처리 → 결과·내려받기 4종)
  - Docker: 샌드박스에서 이미지 빌드(232 MB)·실행(읽기 전용, 비루트) → 헬스체크 healthy, 업로드 처리·UI 응답 확인
- 검사: `python scripts/check.py` 통과(pytest 99건)
- **제출 가능 상태**: 업로드 → 지적 → 변경추적 docx → 리포트 → 웹 UI 수직 슬라이스 완성
- 사용자 확인 필요: 브라우저 UI 직접 사용(피드백), 변경추적본 Word 확인
- 남은 일: Phase 7(LLM)·8(규칙 확장)·9(배포물 P1) → Phase 10(문서화)·11(GitLab 이관) 필수

### Phase 7 — LLM 계층 + 문장 말미 판정 + 모델 2종 평가 (2026-11-09)

- 한 일
  - `llm/base.py`(LLMClient 프로토콜·JSON 추출·가벼운 스키마 검사), `transport.py`(urllib — 추가 의존성 없음), `openai_compat.py`(`POST {base_url}/chat/completions`, temperature 0, `response_format=json_object` → 모르는 서버면 빼고 재시도, 스키마 실패 시 1회 재시도), `null.py`, `cache.py`(SQLite, 키 = 모델·프롬프트 버전·입력 해시), `config.py`(`config/llm_profiles.yaml` → 없으면 패키지 기본 프로필, `${환경변수}` 치환, `KSFIX_LLM_BASE_URL`·`KSFIX_LLM_MODEL` 직접 지정, 로컬 주소가 아니면 외부로 표시)
  - T1 `tasks/modal_verbs.py`: VRB-01·VRB-02 후보 문장 묶음 판정. 가드레일 — 제안은 공통 접두 비율 ≥ 0.7(‘반드시’ 삭제는 예외), 숫자·단위·표준번호가 바뀌면 폐기 → 판단보류, 정형문은 대상 제외. 단일 객체·배열 응답 정규화, 빠진 문장은 한 문장씩 재질의
  - 프롬프트: `modal_verbs.v1.md`(부록 F 원본) 보존, 기본은 **v2**(예시를 묶음 입력→`items` 배열 출력으로 바꿈). 이유: gemma3:4b가 v1 예시를 따라 첫 문장만 단일 객체로 답함
  - T2 `tasks/classify_blocks.py`(신뢰도 0.6 미만 블록 묶음 재판정)
  - 규칙 연동: LLM이 켜지면 VRB-02 허용 의미 → "~해도 된다" AI 제안, 가능성·역량은 지적하지 않음, VRB-01 외적 제약은 적합 처리. 변경추적본에서는 AI 제안을 변경추적 + "[AI 제안 · 모델 · 신뢰도]" 메모로, 반영본에서는 메모로만. VRB-04(금지 표현) 규칙 추가
  - `ksfix check/fix --llm PROFILE`(외부 API면 경고), 웹 UI 프로필 목록·외부 전송 경고, 리포트에 모델·판정 통계
  - `ksfix eval --profiles A,B` + `tests/llm_gold/modal_verbs.jsonl`(직접 작성한 합성 60문장, 유형별 10) → `docs/eval/modal_verbs_eval.md`(정확도·적합성 정확도·판단보류·문장당 시간·혼동행렬)
- 로컬 모델: 이 개발 환경에서 Docker `ollama/ollama` 이미지로 Ollama를 띄우고 `exaone3.5:7.8b`(4.8 GB)·`gemma3:4b`(3.4 GB)를 받아 실제로 구동(합성 문장만 사용, 실제 KS 문서는 보내지 않음). 스모크 테스트에서 두 모델 모두 허용→"수행해도 된다", 가능성/역량, 요구사항→"반드시" 삭제를 맞힘
- 검사: `python scripts/check.py` 통과(pytest 112건, `--llm none` 기본 + FakeLLM·가짜 HTTP 서버로 잘못된 JSON·JSON 모드 미지원·연결 실패 처리 테스트)
- 남은 일: 2모델 평가표(실행 중) 커밋, Phase 8(규칙 확장)

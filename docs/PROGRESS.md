# 진행 기록 (PROGRESS)

계획: [PLAN.md](PLAN.md) · 마감 2026-11-11(수) · Phase 6 = 제출 가능 최소선

## 현재 상태

| Phase | 내용 | 상태 |
|---|---|---|
| 0 | 저장소 부트스트랩 | 완료(CI 초록불) |
| 1 | 합성 표준안 생성기 + IR + 자동번호 | 완료 |
| 2 | 구조 인식 | 완료 |
| 3 | 규칙 엔진 + 첫 규칙 8종 | 대기 |
| 4 | 수정 엔진(변경추적·메모) + 불변성 | 대기 |
| 5 | 리포트 | 대기 |
| 6 | 웹 UI + Docker ★ 제출 가능 최소선 | 대기 |
| 7 | LLM 계층 + 모델 2종 평가 | 대기 |
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

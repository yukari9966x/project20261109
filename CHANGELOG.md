# 변경 이력 (CHANGELOG)

형식: [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) · 버전: [유의적 버전](https://semver.org/lang/ko/)

## 1.0.0 - 2026-11-09

첫 제출 버전(2026 공공 AI 대전환 챌린지 세션1).

### 추가
- **구조 인식**: 스타일 이름·자동번호(numbering.xml, 스타일 상속·lvlOverride·startOverride)·내용 신호와 구역 상태 기계로 표지~해설 역할 인식, 절 트리, 용어 항목 두 가지 꼴, 손입력 번호의 연속성 검사. LLM 보조 재판정(T2, 선택)
- **규칙 점검**: KS A 0001:2023 규칙팩(카탈로그 84종) 중 47종 + 신뢰성 규칙 3종 구현 — 구조·번호·정형문·문장부호·숫자와 단위·표와 그림·비고·참조·인용표준·용어·목차와 제목·KSDT 서식·문장 말미. 지적마다 근거 조항
- **교정**: Word 변경추적(텍스트 단어 단위 최소 차이, 문단 삽입·삭제·이동, 스타일 변경) + 근거 메모, 반영본(clean), 겹치는 수정 정리(“함께 해결”), 목차 필드 갱신 설정
- **검증**: 기술적 내용 불변(INV-01, 실패 시 전체 철회), 입력 파일 불변(INV-02), 출력 무결성(INV-03)
- **리포트**: 단일 파일 HTML·JSON, 부속서 A 검토 항목 53개 체크리스트, 교정 전후 규칙 통과율, 감사 로그(JSONL)
- **LLM(선택)**: OpenAI 호환 어댑터(urllib, JSON 모드·재시도·SQLite 캐시), 문장 말미 판정(T1, 프롬프트 v2)과 가드레일, 연결 실패 시 즉시 규칙 지적으로 전환, `ksfix eval` 모델 비교(합성 골드셋 60문장)
- **실행 형태**: CLI(`check`·`fix`·`inspect`·`rules`·`eval`·`serve`), 로컬 웹 UI(FastAPI + 정적 UI), Docker, Windows 실행파일(PyInstaller, `--selftest`), 브라우저 데모(Pyodide)
- **보안**: 입력 검증(크기·압축 폭탄·매크로·DTD/ENTITY·암호화), 127.0.0.1 바인딩, 작업 파일 1시간 뒤 삭제, 보안 헤더·CSP
- **모의데이터·예시**: 합성 표준안 3종과 정답(역할·기대 지적), `examples/` 처리 결과
- **문서**: README, 사용자 안내서, LLM 연결 안내, 보안, 아키텍처, 규칙 목록(자동 생성), 오픈소스 고지, 제출 문서 초안

### 보안
- LLM 전송은 http·https 주소만 허용하고 http·https 처리기만 넣은 전용 opener로 연다(file:// 등 다른 스킴과 리다이렉트 차단). 공공 GitLab 푸시 보안 검사(Semgrep `dynamic-urllib-use-detected`) 대응

### 품질
- pytest 단위·골든·E2E(웹 API 업로드→내려받기→재열기), Playwright로 화면 조작·CSP 확인, 합성 위반본 결정형 규칙 재현율 49/49, 정상본 오류·경고 0건
- 발간 KS 문서 2종으로 로컬 검증(저장소 미포함): 찾은 오탐은 합성 테스트로 고정
- GitHub Actions: 검사(ruff·pytest·샘플 처리)·Docker 빌드·Windows 실행파일 빌드와 자체 시험


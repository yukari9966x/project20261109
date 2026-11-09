# KS-Fix 로컬 웹 UI(포트 8765)
#   빌드: docker build -t ksfix .
#   실행: docker run --rm -p 127.0.0.1:8765:8765 ksfix   → http://127.0.0.1:8765
#   TLS 검사 프록시를 거치는 망(업무망 등): 프록시 CA를 비밀값으로 넘긴다(이미지에 남지 않음)
#     docker build --secret id=pip_ca,src=<프록시 CA 파일> -t ksfix .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    KSFIX_HOST=0.0.0.0 \
    KSFIX_PORT=8765 \
    KSFIX_MAX_UPLOAD_MB=30 \
    KSFIX_LLM_PROFILE=none

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY webapp ./webapp
COPY config ./config

RUN --mount=type=secret,id=pip_ca \
    if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; \
    pip install ".[web,llm]" \
    && useradd --create-home --uid 10001 ksfix

USER ksfix
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/v1/health', timeout=3)" || exit 1
CMD ["ksfix", "serve", "--host", "0.0.0.0", "--port", "8765"]

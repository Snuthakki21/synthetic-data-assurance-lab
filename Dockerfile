FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY app app
COPY portfolio portfolio
COPY projects projects
COPY web web
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /app/var && python -m portfolio build && chown -R app:app /app
USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health',timeout=3).read()"
CMD ["python", "-m", "portfolio", "serve", "--host", "0.0.0.0", "--port", "8765", "--database", "/app/var/workspace.sqlite"]

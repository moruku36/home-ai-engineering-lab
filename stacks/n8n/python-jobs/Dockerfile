FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin jobs \
 && mkdir -p /data/reports /data/state && chown 10001 /data/reports /data/state
COPY server.py github_snapshot.py /app/
USER 10001
ENV PYTHONUNBUFFERED=1
WORKDIR /app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"
CMD ["python", "/app/server.py"]

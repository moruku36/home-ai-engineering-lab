FROM python:3.12-slim
RUN useradd --uid 10002 --no-create-home --shell /usr/sbin/nologin mcp \
 && mkdir -p /var/log/mcp /data/reports && chown 10002 /var/log/mcp
COPY server.py policy.json /app/
USER 10002
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"
CMD ["python", "/app/server.py"]

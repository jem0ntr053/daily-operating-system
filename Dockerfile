FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e '.[server]'
ENV DAYCTL_STORAGE=sqlite:///data/dayctl.db
ENV DAYCTL_ENABLE_SCHEDULER=1
EXPOSE 8080
CMD ["uvicorn", "dayctl.server.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]

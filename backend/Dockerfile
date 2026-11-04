FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.lock requirements.lock
RUN pip install --no-cache-dir -r requirements.lock && useradd --create-home tipro
COPY --chown=tipro:tipro . .
USER tipro
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

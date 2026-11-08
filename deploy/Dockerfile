FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY deploy/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home enwen
COPY backend /app/backend
COPY frontend /app/frontend
COPY deploy/entrypoint.py /app/entrypoint.py
COPY deploy/check_config.py /app/check_config.py
USER enwen
WORKDIR /app/backend
EXPOSE 8000
CMD ["python", "/app/entrypoint.py"]

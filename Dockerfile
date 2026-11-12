FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt
COPY . .
RUN python manage.py collectstatic --no-input
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]

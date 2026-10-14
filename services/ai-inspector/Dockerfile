FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /svc
COPY services/ai-inspector/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY packages/proof-core/python /proof-core
RUN pip install --no-cache-dir /proof-core
COPY services/ai-inspector .
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

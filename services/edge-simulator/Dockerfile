FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/services/edge-simulator
COPY packages/proof-core/python /proof-core
COPY services/edge-simulator/requirements.txt .
RUN pip install --no-cache-dir /proof-core -r requirements.txt
COPY services/edge-simulator .
ENTRYPOINT ["python", "-m", "simulator"]
CMD ["--count", "0", "--rate", "1"]

FROM python:3.11-slim

WORKDIR /app

# freetds-dev + freetds-bin necessários para pymssql compilar e conectar ao MSSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl-dev ca-certificates freetds-dev freetds-bin && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8011", "--workers", "2"]

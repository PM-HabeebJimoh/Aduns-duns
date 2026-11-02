FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY aduns ./aduns
ENV ADUNS_DB=/data/aduns.db PYTHONUNBUFFERED=1
VOLUME ["/data"]
EXPOSE 8000
# API + dashboard + the 24/7 worldwide discovery loop in one process
CMD ["python", "-m", "aduns", "serve", "--port", "8000", "--daemon"]

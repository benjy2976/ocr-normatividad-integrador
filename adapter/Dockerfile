FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY worker_entrypoint.py /app/worker_entrypoint.py
COPY worker_main.py /app/worker_main.py

CMD ["python3", "worker_entrypoint.py"]

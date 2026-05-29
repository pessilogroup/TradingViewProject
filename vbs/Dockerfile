FROM python:3.11-slim

WORKDIR /app

# Copy dependency list and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create volume mount point for database
RUN mkdir -p /app/data

# Default port
EXPOSE 5000

ENV PORT=5000
ENV HOST=0.0.0.0
ENV DB_PATH=/app/data/signal_queue.db

CMD ["python", "main.py"]

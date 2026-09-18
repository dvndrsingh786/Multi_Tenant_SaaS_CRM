# The image for the API and the background worker (same code, different command).
FROM python:3.12-slim

# Do not write .pyc files, and print logs straight away.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install the Python packages first. Docker caches this step, so it only
# runs again when the requirements files change.
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy the rest of the project.
COPY . .

EXPOSE 8000

# Default command: create the tables, add demo data, start the API.
CMD ["sh", "-c", "python migrate.py && python seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

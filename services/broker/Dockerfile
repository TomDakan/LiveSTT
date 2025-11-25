FROM python:3.11-slim

# We only need pyzmq for the broker.
# Using pip directly here is acceptable for this "infrastructure" container
# to keep the build ultra-light and fast, bypassing the heavy PDM install.
RUN pip install --no-cache-dir pyzmq

WORKDIR /app

# Copy the source
COPY src/ /app/src/

# Ensure Python path finds the module if needed, though we run by file path below
ENV PYTHONPATH=/app

# Run unbuffered so logs show up in Docker immediately
CMD ["python", "-u", "src/main.py"]

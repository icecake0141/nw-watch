# Dockerfile for nw-watch
FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    ssh \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY collector/ ./collector/
COPY webapp/ ./webapp/
COPY shared/ ./shared/
COPY config.example.yaml ./

# Install Python dependencies
# First install setuptools and wheel
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org setuptools wheel
# Then install the package
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .

# Create data directory
RUN mkdir -p /app/data

# Expose web application port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command - can be overridden in docker-compose
CMD ["uvicorn", "webapp.main:app", "--host", "0.0.0.0", "--port", "8000"]

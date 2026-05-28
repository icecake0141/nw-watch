# Copyright 2026 icecake0141
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# This file was created or modified with the assistance of an AI (Large Language Model).
# Review required for correctness, security, and licensing.
# Dockerfile for nw-watch
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY README.md LICENSE NOTICE ./
COPY src/ ./src/
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
CMD ["python", "-m", "nw_watch.runtime", "--config", "/app/config.yaml", "--host", "0.0.0.0", "--port", "8000", "--data-dir", "/app/data"]

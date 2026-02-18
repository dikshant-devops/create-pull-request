FROM python:3.11-slim

LABEL maintainer="Create Pull Request Action"
LABEL description="Creates a pull request for changes to your repository in the actions workspace"
LABEL version="1.0.0"

# Install git
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /action

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Set Python path
ENV PYTHONPATH=/action/src

# Set entrypoint
ENTRYPOINT ["python", "-m", "create_pull_request"]

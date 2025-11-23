# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install uv
# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV PATH="/app/.venv/bin:$PATH"

# Install GitHub CLI
RUN type -p curl >/dev/null || (apt update && apt install curl -y)
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt update \
    && apt install gh -y

# Install Kilo CLI
RUN npm install -g @kilocode/cli

# Copy the current directory contents into the container at /app
COPY . /app

# Define environment variable
ENV NAME CodingAgent

# Run fix_issue.py when the container launches
# The arguments will be passed via the ECS RunTask overrides
ENTRYPOINT ["uv", "run", "fix_issue.py"]

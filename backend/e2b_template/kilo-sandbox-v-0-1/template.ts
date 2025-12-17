import { Template } from 'e2b'

const dockerfile = `
FROM python:3.12-slim

# Ensure we are root for installations
USER root

# Install system utilities
RUN apt-get update && apt-get install -y curl git unzip

# Install Node.js (required for Kilocode CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \\
    && apt-get install -y nodejs \\
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI (gh)
RUN mkdir -p -m 755 /etc/apt/keyrings \\
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \\
    && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \\
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \\
    && apt-get update \\
    && apt-get install -y gh

# Install Kilocode CLI
RUN npm install -g @kilocode/cli

# Verify
RUN git --version && gh --version && kilocode --version && node --version
`

export const template = Template()
  .fromDockerfile(dockerfile)
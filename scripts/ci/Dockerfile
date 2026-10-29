# Local pre-push and GitHub test share a Linux toolchain, on native architecture.
FROM ghcr.io/astral-sh/uv:0.13.1 AS uv
FROM node:24-bookworm-slim
COPY --from=uv /uv /uvx /usr/local/bin/
RUN apt-get update && apt-get install -y --no-install-recommends git jq ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN npm install --global @earendil-works/pi-coding-agent@1.4.0 --ignore-scripts --no-audit --no-fund
ENV UV_PYTHON=3.14 UV_PYTHON_PREFERENCE=only-managed UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/python DISABLE_MKDOCS_2_WARNING=true
RUN uv python install 3.14
WORKDIR /workspace
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --all-extras --no-install-project
COPY . .
# GitHub checks run unprivileged; root would bypass chmod/permission tests.
RUN chown -R node:node /workspace
USER node
CMD ["bash", "scripts/ci/checks.sh"]

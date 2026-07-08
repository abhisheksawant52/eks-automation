# Slim single-stage image packaging the eks-automation CLI.
FROM python:3.12-slim

# Do not write .pyc files; flush stdout/stderr immediately.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the package first (layer caching for dependencies).
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

ENTRYPOINT ["eks-automation"]
CMD ["--help"]

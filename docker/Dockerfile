FROM python:3.14-slim@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir hatchling==1.27.0 PyYAML==6.0.3 \
    && pip install --no-cache-dir --no-build-isolation --no-deps .
COPY agents ./agents
COPY config ./config
USER 1000:1000
CMD ["python", "-m", "personal_ai_brain.runtime", "serve"]

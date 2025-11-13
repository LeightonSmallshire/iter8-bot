FROM python:3.11-slim AS base_builder
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_ROOT_USER_ACTION=ignore
COPY base-requirements.txt .
RUN python -m pip install --no-cache-dir -r base-requirements.txt
RUN python -m venv /venv --system-site-packages

FROM gcr.io/distroless/python3-debian12:debug-nonroot AS base_runner
ENV PYTHONPATH="/usr/local/lib/python3.11/site-packages"
COPY --chown=nonroot:nonroot --from=base_builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

FROM base_builder AS repo_builder
ARG REPO_BRANCH=main
ADD [ "https://github.com/LeightonSmallshire/iter8-bot.git#${REPO_BRANCH}", "/app/" ]
RUN /venv/bin/pip install --no-cache-dir -r /app/requirements.txt

FROM base_runner AS final_runner
COPY --chown=nonroot:nonroot --from=repo_builder /venv/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --chown=nonroot:nonroot --from=repo_builder /app/ /app/

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
ENTRYPOINT ["python3", "/app/entrypoint.py"]

FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_ROOT_USER_ACTION=ignore

COPY requirements.txt .
RUN python -m pip install -r requirements.txt

FROM gcr.io/distroless/python3-debian12:debug-nonroot AS runner
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH="/usr/local/lib/python3.11/site-packages"
COPY --chown=nonroot:nonroot --from=builder ${PYTHONPATH} ${PYTHONPATH}
COPY . .

ENTRYPOINT ["python3", "/app/entrypoint.py"]

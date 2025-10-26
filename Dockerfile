FROM python:3.11-slim-bookworm AS builder

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        git \
        build-essential \
    && rm -rf /var/lib/apt/lists/*
#        ldd \

# Set up a working directory and a non-root user for installation
WORKDIR /tmp/build

# Copy requirements and install them as the non-root user
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# --- Prepare Git and its dependencies for copying ---
# Git must be explicitly copied to the distroless image. We use ldd to find
# all required dynamic libraries and stage them into a single temporary folder.
ENV GIT_DEST_DIR=/tmp/git-runtime
RUN mkdir -p ${GIT_DEST_DIR}/usr/bin \
    && cp /usr/bin/git ${GIT_DEST_DIR}/usr/bin/git \
    && ldd /usr/bin/git | awk '{print $3}' | grep '^/' | xargs -I {} sh -c 'mkdir -p $(dirname ${GIT_DEST_DIR}{}) && cp {} ${GIT_DEST_DIR}{}'

FROM gcr.io/distroless/python3-debian12:debug-nonroot AS final
# https://github.com/GoogleContainerTools/distroless

WORKDIR /app

ENV PYTHONPATH="/usr/local/lib/python3.11/site-packages"
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /tmp/git-runtime/ /

COPY . /app

EXPOSE 8080
ENTRYPOINT ["python3", "main.py"]
CMD []

FROM python:3.11 AS base_builder

# expensive pip install
COPY base-requirements.txt /
RUN python -m pip install --no-cache-dir -r /base-requirements.txt

#ARG CACHE_BUST=${CACHE_BUST}
ADD https://github.com/LeightonSmallshire/iter8-bot.git /app/
RUN python -m pip install --no-cache-dir -r /app/requirements.txt

#FROM gcr.io/distroless/python3-debian12:debug-nonroot AS runner

ENV PYTHONPATH="/usr/local/lib/python3.11/site-packages/"
#COPY --chown=nonroot:nonroot --from=base_builder /app/ /app/
#COPY --chown=nonroot:nonroot --from=base_builder ${PYTHONPATH} ${PYTHONPATH}

WORKDIR /app
ENTRYPOINT ["python3"]
CMD ["main.py"]

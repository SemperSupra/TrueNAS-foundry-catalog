# SOURCE CANDIDATE ONLY: supply a reviewed immutable OCI base digest.
ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE} AS stage
ARG FOUNDRY_REF=4efc55a2d0069bd4a4a0b7fcbb4eec8c7e091825
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git && rm -rf /var/lib/apt/lists/*
COPY scripts/fetch-foundry.sh /tmp/fetch-foundry.sh
RUN FOUNDRY_REF="$FOUNDRY_REF" sh /tmp/fetch-foundry.sh
FROM ${PYTHON_IMAGE}
WORKDIR /app
COPY --from=stage /app/vendor /app/vendor
COPY src /app/src
COPY assets /app/assets
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 65532:65532
EXPOSE 8443
ENTRYPOINT ["python3", "/app/src/server.py"]
CMD ["--index", "/data/indexes/foundry.json", "--token-file", "/run/secrets/catalog-token", "--tls-cert-file", "/run/secrets/tls.crt", "--tls-key-file", "/run/secrets/tls.key", "--bind", "0.0.0.0", "--port", "8443"]

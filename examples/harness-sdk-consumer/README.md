# Harness SDK Consumer

This is a minimal external-service example for using `deerflow-harness` as an
installed Python dependency without importing the Gateway or frontend.

Build and install the wheel from the backend workspace:

```bash
cd backend
uv build packages/harness --wheel --out-dir dist
uv venv .venv-sdk-consumer
uv pip install --python .venv-sdk-consumer/Scripts/python.exe dist/deerflow_harness-*.whl
```

Then run the consumer with a registry manifest:

```bash
.venv-sdk-consumer/Scripts/python.exe ../examples/harness-sdk-consumer/consumer.py \
  --repo-root .. \
  --manifest ../registries/demo_extensions.json \
  --output-dir .deer-flow/sdk-consumer
```

The script validates the registry, loads enabled capabilities, generates HTML,
CSV, and PDF artifacts, and prints a JSON summary.

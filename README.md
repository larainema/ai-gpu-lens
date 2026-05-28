# ai-gpu-lens

`ai-gpu-lens` is a small CLI for finding waste in Kubernetes GPU fleets.
It reads DCGM exporter metrics from Prometheus and produces an HTML/JSON report
covering GPU utilization, memory usage, idle GPU hours, namespace attribution,
and quick recommendations.

The first target is a practical consulting workflow:

```text
7 day GPU cost audit -> report -> concrete remediation backlog
```

## Current status

This is an early MVP. It is intentionally dependency-light and uses only the
Python standard library at runtime.

## Install locally

```bash
./bin/ai-gpu-lens --help
```

or install/run through uv:

```bash
uv run ai-gpu-lens --help
```

For direct module execution from a source checkout:

```bash
PYTHONPATH=src python3 -m ai_gpu_lens --help
```

## Generate a sample report

```bash
./bin/ai-gpu-lens audit \
  --from-file examples/sample-prometheus.json \
  --output reports/sample.html \
  --json-output reports/sample.json \
  --price-per-gpu-hour 2.50
```

## Audit a Prometheus endpoint

```bash
./bin/ai-gpu-lens audit \
  --prometheus-url http://prometheus.example.com:9090 \
  --hours 24 \
  --step 5m \
  --output reports/gpu-audit.html \
  --json-output reports/gpu-audit.json \
  --price-per-gpu-hour 2.50
```

By default the tool queries these DCGM metrics:

- `DCGM_FI_DEV_GPU_UTIL`
- `DCGM_FI_DEV_FB_USED`
- `DCGM_FI_DEV_FB_TOTAL`

You can override the metric names if your deployment uses recording rules:

```bash
./bin/ai-gpu-lens audit \
  --prometheus-url http://localhost:9090 \
  --gpu-util-query 'avg by (Hostname, UUID, namespace, pod) (DCGM_FI_DEV_GPU_UTIL)' \
  --memory-used-query 'DCGM_FI_DEV_FB_USED' \
  --memory-total-query 'DCGM_FI_DEV_FB_TOTAL'
```

## What it reports

- Fleet average GPU utilization
- Estimated idle GPU hours
- Estimated waste based on `--price-per-gpu-hour`
- Per-GPU utilization and framebuffer memory usage
- Namespace-level utilized GPU-hour equivalents when Kubernetes labels exist
- Gaps in telemetry that make attribution weaker
- Practical recommendations for the next audit pass

## Prometheus label expectations

The analyzer works best when DCGM exporter exposes Kubernetes labels:

- `namespace`
- `pod`
- `container`
- `Hostname` or `node`
- `UUID` or `gpu`
- `modelName`

If namespace/pod labels are missing, the report still works, but attribution
will be grouped under `unknown`.

## Development

```bash
python3 -m unittest discover -s tests
./bin/ai-gpu-lens audit --from-file examples/sample-prometheus.json --output reports/sample.html
```

## Roadmap

- More precise GPU allocation accounting from kube-state-metrics
- Prometheus recording-rule recommendations
- Markdown export for customer-facing audit reports
- Helm chart for an in-cluster scheduled audit job
- Grafana dashboard JSON export

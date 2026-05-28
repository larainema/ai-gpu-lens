# ai-gpu-lens

`ai-gpu-lens` is a small CLI for finding waste in Kubernetes GPU fleets.
It reads DCGM exporter metrics from Prometheus and produces an HTML/JSON report
covering GPU utilization, memory usage, idle GPU hours, namespace attribution,
executive summaries, and concrete action items.

`ai-gpu-lens` 是一个面向 Kubernetes GPU 集群的小型审计 CLI。它从
Prometheus/DCGM 读取指标，生成中英文 HTML/JSON 报告，帮助定位 GPU
利用率低、显存使用异常、空闲 GPU 小时、namespace 成本归因和可执行整改项。

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

Install directly from GitHub with pipx:

```bash
pipx install git+https://github.com/larainema/ai-gpu-lens.git
ai-gpu-lens --help
```

## Generate a sample report

```bash
./bin/ai-gpu-lens audit \
  --from-file examples/sample-prometheus.json \
  --output reports/sample.html \
  --json-output reports/sample.json \
  --markdown-output reports/sample.md \
  --price-per-gpu-hour 2.50
```

Generate a Chinese report:

```bash
./bin/ai-gpu-lens audit \
  --from-file examples/sample-prometheus.json \
  --output reports/sample.zh.html \
  --json-output reports/sample.zh.json \
  --markdown-output reports/sample.zh.md \
  --price-per-gpu-hour 2.50 \
  --language zh
```

You can also run from a config file:

```bash
./bin/ai-gpu-lens audit --config examples/ai-gpu-lens.yaml
```

## Audit a Prometheus endpoint

```bash
./bin/ai-gpu-lens audit \
  --prometheus-url http://prometheus.example.com:9090 \
  --hours 24 \
  --step 5m \
  --output reports/gpu-audit.html \
  --json-output reports/gpu-audit.json \
  --markdown-output reports/gpu-audit.md \
  --price-per-gpu-hour 2.50
```

Use `--language en` or `--language zh` to choose the report language. English is
the default.

By default the tool queries these DCGM metrics:

- `DCGM_FI_DEV_GPU_UTIL`
- `DCGM_FI_DEV_FB_USED`
- `DCGM_FI_DEV_FB_TOTAL`
- fallback when total memory is missing:
  `DCGM_FI_DEV_FB_USED + ignoring(__name__) DCGM_FI_DEV_FB_FREE`
- `kube_pod_container_resource_requests`

You can override the metric names if your deployment uses recording rules:

```bash
./bin/ai-gpu-lens audit \
  --prometheus-url http://localhost:9090 \
  --gpu-util-query 'avg by (Hostname, UUID, namespace, pod) (DCGM_FI_DEV_GPU_UTIL)' \
  --memory-used-query 'DCGM_FI_DEV_FB_USED' \
  --memory-total-query 'DCGM_FI_DEV_FB_TOTAL' \
  --memory-total-fallback-query 'DCGM_FI_DEV_FB_USED + ignoring(__name__) DCGM_FI_DEV_FB_FREE' \
  --kube-gpu-request-query 'sum by (namespace, pod) (kube_pod_container_resource_requests{resource=~"nvidia_com_gpu|nvidia.com/gpu"} * on(namespace, pod) group_left() max by (namespace, pod) (kube_pod_status_phase{phase=~"Pending|Running"} == 1))'
```

If kube-state-metrics is not installed, use `--skip-kube-gpu-requests`.
If your exporter exposes `DCGM_FI_DEV_FB_TOTAL` directly and you do not want the
fallback query, use `--skip-memory-total-fallback`.

## Audit through Grafana

If Prometheus is only reachable through a Grafana datasource proxy, point
`--prometheus-url` at the proxied datasource API. Use a Viewer-level account
or service account token where possible.

```bash
./bin/ai-gpu-lens audit \
  --prometheus-url https://grafana.example.com/api/datasources/proxy/uid/prometheus \
  --basic-auth-user viewer \
  --prompt-basic-auth-password \
  --hours 24 \
  --step 5m \
  --output reports/grafana-audit.html \
  --json-output reports/grafana-audit.json \
  --markdown-output reports/grafana-audit.md
```

For automation, put the password in an environment variable and use
`--basic-auth-password-env` instead of prompting.

Bearer tokens are also supported:

```bash
export GRAFANA_TOKEN=...
./bin/ai-gpu-lens audit \
  --prometheus-url https://grafana.example.com/api/datasources/proxy/uid/prometheus \
  --bearer-token-env GRAFANA_TOKEN \
  --hours 24 \
  --step 5m \
  --output reports/grafana-audit.html
```

## Docker

Build the local image:

```bash
docker build -t ai-gpu-lens:local .
```

Run against the bundled sample data:

```bash
docker run --rm ai-gpu-lens:local audit \
  --from-file examples/sample-prometheus.json \
  --output /tmp/sample.html \
  --json-output /tmp/sample.json \
  --markdown-output /tmp/sample.md
```

For real environment configs, mount a local directory that is not committed:

```bash
docker run --rm \
  -v "$PWD/local:/configs:ro" \
  -v "$PWD/reports:/reports" \
  ai-gpu-lens:local audit \
  --config /configs/grafana.yaml
```

## Doctor

Use `doctor` to check whether a Prometheus or Grafana datasource proxy has the
metrics needed for a useful audit:

```bash
./bin/ai-gpu-lens doctor \
  --prometheus-url http://localhost:9090
```

For Grafana:

```bash
./bin/ai-gpu-lens doctor \
  --prometheus-url https://grafana.example.com/api/datasources/proxy/uid/prometheus \
  --basic-auth-user viewer \
  --prompt-basic-auth-password
```

`doctor` checks for DCGM GPU utilization, framebuffer memory metrics,
kube-state-metrics GPU requests, exported workload labels, GPU model
distribution, and recommended PromQL defaults.

## Config file

`ai-gpu-lens` accepts a small YAML/JSON config file. CLI flags override config
values.

```yaml
prometheus_url: http://prometheus.example.com:9090
hours: 168
step: 5m
language: en

output: reports/gpu-audit.html
json_output: reports/gpu-audit.json
markdown_output: reports/gpu-audit.md

price_per_gpu_hour: 2.50
gpu_prices:
  default: 2.50
  H100: 4.25
  A100: 3.20
  L40S: 1.35
```

GPU model prices are matched by exact name first, then by substring. For
example `H100` matches `NVIDIA H100 80GB HBM3`. The `default` price is used
when no model-specific price matches.

Keep environment-specific configs under `local/`; that directory is ignored by
Git. Do not commit real Grafana URLs, kubeconfig paths, usernames, passwords, or
tokens to a public repository.

## What it reports

- Fleet average GPU utilization
- Estimated idle GPU hours
- Estimated waste based on `--price-per-gpu-hour`
- Per-GPU utilization and framebuffer memory usage
- Per-model GPU price matching
- kube-state-metrics requested GPU hours
- Namespace-level utilized GPU-hour equivalents when Kubernetes labels exist
- Executive summary and prioritized action items for a remediation backlog
- Physical GPU de-duplication when DCGM exporter emits repeated container
  series for the same GPU
- Gaps in telemetry that make attribution weaker
- Practical recommendations for the next audit pass

## 报告内容

- GPU 集群平均利用率
- 估算的空闲 GPU 小时
- 基于 `--price-per-gpu-hour` 的浪费成本估算
- 单卡利用率和显存使用情况
- 不同 GPU 型号的价格匹配
- kube-state-metrics 中的 GPU 申请小时数
- namespace 维度的 GPU 小时归因
- 执行摘要和按优先级排序的行动清单，方便形成整改 backlog
- 针对同一物理 GPU 重复 DCGM 序列的去重
- 影响成本归因准确性的遥测缺口
- 下一轮审计可执行建议

## Prometheus label expectations

The analyzer works best when DCGM exporter exposes Kubernetes labels:

- `namespace`
- `pod`
- `container`
- `Hostname` or `node`
- `UUID` or `gpu`
- `modelName`
- kube-state-metrics `namespace`, `pod`, and GPU `resource` labels

If namespace/pod labels are missing, the report still works, but attribution
will be grouped under `unknown`.

## Development

```bash
make test
make sample
make docker-build
```

GitHub Actions runs unit tests on Python 3.10 through 3.13, builds the Python
package, and smoke-tests the Docker image.

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE).

## Roadmap

- More precise GPU allocation accounting from kube-state-metrics
- Prometheus recording-rule recommendations
- Markdown export for customer-facing audit reports
- Helm chart for an in-cluster scheduled audit job
- Grafana dashboard JSON export

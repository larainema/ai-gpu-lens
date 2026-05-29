# Grafana Datasource Proxy

Use this path when Prometheus is not directly reachable but Grafana can query
it.

当 Prometheus 不能直接访问，但 Grafana 可以查询 Prometheus 时，使用
Grafana datasource proxy。

## Endpoint Shape

Grafana datasource proxy endpoints usually look like this:

```text
https://grafana.example.com/api/datasources/proxy/uid/<datasource-uid>
```

For a datasource UID named `prometheus`:

```text
https://grafana.example.com/api/datasources/proxy/uid/prometheus
```

The endpoint should behave like the Prometheus HTTP API. `ai-gpu-lens` will call:

```text
/api/v1/query
/api/v1/query_range
```

## Authentication

Prefer a read-only Viewer account or a service account token.

Interactive Basic Auth:

```bash
ai-gpu-lens doctor \
  --prometheus-url https://grafana.example.com/api/datasources/proxy/uid/prometheus \
  --basic-auth-user viewer \
  --prompt-basic-auth-password
```

Basic Auth from an environment variable:

```bash
export GRAFANA_PASSWORD='...'

ai-gpu-lens audit \
  --prometheus-url https://grafana.example.com/api/datasources/proxy/uid/prometheus \
  --basic-auth-user viewer \
  --basic-auth-password-env GRAFANA_PASSWORD \
  --hours 168 \
  --step 5m \
  --output reports/grafana-audit.html \
  --json-output reports/grafana-audit.json \
  --markdown-output reports/grafana-audit.md
```

Bearer token:

```bash
export GRAFANA_TOKEN='...'

ai-gpu-lens audit \
  --prometheus-url https://grafana.example.com/api/datasources/proxy/uid/prometheus \
  --bearer-token-env GRAFANA_TOKEN \
  --hours 168 \
  --step 5m \
  --output reports/grafana-audit.html
```

## Config File

Keep real configs in `local/`, which is ignored by Git:

```yaml
prometheus_url: https://grafana.example.com/api/datasources/proxy/uid/prometheus
hours: 168
step: 5m
language: zh

output: reports/grafana-audit.html
json_output: reports/grafana-audit.json
markdown_output: reports/grafana-audit.md

price_per_gpu_hour: 2.50
gpu_prices:
  default: 2.50
  H100: 4.25
  A100: 3.20
  L40S: 1.35
  4090: 0.65

basic_auth_user: viewer
prompt_basic_auth_password: true
```

Run:

```bash
ai-gpu-lens doctor --config local/grafana.yaml
ai-gpu-lens audit --config local/grafana.yaml
```

To create an importable Grafana dashboard for the same datasource:

```bash
ai-gpu-lens dashboard \
  --config local/grafana.yaml \
  --output reports/grafana-dashboard.json
```

## Preflight Checklist

Run `doctor` before `audit`. A useful Grafana-backed audit should have:

- `dcgm_gpu_utilization`: OK
- `dcgm_memory_used`: OK
- `dcgm_memory_total` or `dcgm_memory_total_fallback`: OK
- `kube_gpu_requests`: OK, if you want requested-vs-used analysis
- `dcgm_exported_workload_labels`: OK, if you want workload attribution

If `DCGM_FI_DEV_FB_TOTAL` is missing but `DCGM_FI_DEV_FB_FREE` exists,
`ai-gpu-lens` automatically tries:

```promql
DCGM_FI_DEV_FB_USED + ignoring(__name__) DCGM_FI_DEV_FB_FREE
```

## Common Issues

`HTTP 401` or `HTTP 403`:

Check the Grafana user/token. A Viewer role is usually enough if the datasource
is queryable by that user.

`Prometheus query did not return a range vector`:

The endpoint may not be a Prometheus-compatible datasource proxy, or the URL may
point to a Grafana page instead of the datasource proxy API.

No namespace or pod attribution:

Check whether dcgm-exporter exposes Kubernetes workload labels such as
`exported_namespace` and `exported_pod`.

## 中文速记

- 使用只读 Viewer 或 service account token。
- 先跑 `doctor`，再跑 `audit`。
- 配置放 `local/`，密码用 prompt 或环境变量，不要写进 public repo。
- 如果没有 `DCGM_FI_DEV_FB_TOTAL`，工具会自动尝试 `USED + FREE` 作为显存总量。

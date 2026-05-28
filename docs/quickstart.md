# Quickstart / 快速开始

This guide gets you from zero to a local GPU audit report in a few minutes.

这份文档帮助你在几分钟内生成第一份本地 GPU 审计报告。

## 1. Run The Sample

From a source checkout:

```bash
./bin/ai-gpu-lens audit \
  --from-file examples/sample-prometheus.json \
  --output reports/sample.html \
  --json-output reports/sample.json \
  --markdown-output reports/sample.md \
  --price-per-gpu-hour 2.50 \
  --language zh
```

Open `reports/sample.html` in a browser. The report includes:

- executive summary
- prioritized action items
- idle GPU ranking
- over-requested namespace and workload ranking
- per-GPU utilization and memory details
- telemetry gaps

## 2. Use The Released Container

```bash
docker run --rm ghcr.io/larainema/ai-gpu-lens:v0.1.0 --help
```

Run the bundled sample inside the image:

```bash
docker run --rm ghcr.io/larainema/ai-gpu-lens:v0.1.0 audit \
  --from-file examples/sample-prometheus.json \
  --output /tmp/sample.html \
  --json-output /tmp/sample.json \
  --markdown-output /tmp/sample.md
```

For real audits, mount local config and report directories:

```bash
mkdir -p local reports

docker run --rm \
  -v "$PWD/local:/configs:ro" \
  -v "$PWD/reports:/reports" \
  ghcr.io/larainema/ai-gpu-lens:v0.1.0 audit \
  --config /configs/grafana.yaml
```

Keep `local/` and `reports/` out of Git. They may contain environment names,
internal URLs, or customer data.

## 3. Install From GitHub

```bash
pipx install git+https://github.com/larainema/ai-gpu-lens.git
ai-gpu-lens --help
```

Or run directly from a checkout:

```bash
./bin/ai-gpu-lens --help
```

## 4. Audit Prometheus

```bash
ai-gpu-lens doctor \
  --prometheus-url http://prometheus.example.com:9090

ai-gpu-lens audit \
  --prometheus-url http://prometheus.example.com:9090 \
  --hours 168 \
  --step 5m \
  --price-per-gpu-hour 2.50 \
  --output reports/gpu-audit.html \
  --json-output reports/gpu-audit.json \
  --markdown-output reports/gpu-audit.md
```

Use a 24 hour window for a first smoke test. Use a 7 day window for a real
capacity or cost discussion.

## 5. Audit Through Grafana

If Prometheus is only reachable through Grafana, use the datasource proxy:

```bash
ai-gpu-lens doctor \
  --prometheus-url https://grafana.example.com/api/datasources/proxy/uid/prometheus \
  --basic-auth-user viewer \
  --prompt-basic-auth-password
```

Then run `audit` with the same endpoint and authentication settings.

See [Grafana datasource proxy](grafana-datasource-proxy.md) for details.

## 中文速记

- 先用 sample 跑通：`./bin/ai-gpu-lens audit --from-file examples/sample-prometheus.json ...`
- 真实环境先跑 `doctor`，确认 DCGM、kube-state-metrics、workload labels 是否齐全。
- 初测用 24 小时窗口，正式审计用 7 天窗口。
- 环境配置放 `local/`，报告放 `reports/`，两者都不要提交到 public repo。

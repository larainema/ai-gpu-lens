# Grafana Dashboard JSON / Grafana 仪表盘 JSON

`ai-gpu-lens dashboard` generates an importable Grafana dashboard JSON file. It
does not connect to Grafana and does not modify any cluster or datasource.

`ai-gpu-lens dashboard` 会生成一个可导入 Grafana 的 dashboard JSON 文件。它
不会连接 Grafana，也不会修改集群或 datasource。

## Generate

```bash
./bin/ai-gpu-lens dashboard \
  --output reports/ai-gpu-lens-dashboard.json
```

By default, the dashboard asks you to select a Prometheus datasource during
Grafana import. If you already know the datasource UID, set it explicitly:

```bash
./bin/ai-gpu-lens dashboard \
  --datasource-uid prometheus \
  --title "Production GPU Fleet" \
  --uid production-gpu-fleet \
  --output reports/production-gpu-dashboard.json
```

## Import

In Grafana:

1. Open **Dashboards**.
2. Select **New** or **Import**.
3. Upload `reports/ai-gpu-lens-dashboard.json`.
4. Choose the Prometheus datasource that has DCGM exporter metrics.
5. Save the dashboard.

## Panels

The generated dashboard includes:

- fleet average GPU utilization
- GPU series count
- idle GPU count
- framebuffer memory metric coverage
- fleet utilization trend
- per-device utilization trend
- per-device framebuffer memory used percent
- lowest average utilization table for the selected range
- metric coverage trend
- requested GPUs by namespace and workload, when kube-state-metrics GPU request
  data is enabled

## Config File

You can use a config file for repeatable dashboard generation:

```bash
./bin/ai-gpu-lens dashboard --config examples/dashboard.yaml
```

Example:

```yaml
dashboard_output: reports/ai-gpu-lens-dashboard.json
dashboard_title: ai-gpu-lens GPU Fleet
dashboard_uid: ai-gpu-lens
dashboard_datasource_uid: ${DS_PROMETHEUS}
dashboard_time_from: now-24h
dashboard_refresh: 1m

gpu_util_query: DCGM_FI_DEV_GPU_UTIL
memory_used_query: DCGM_FI_DEV_FB_USED
dashboard_memory_total_query: DCGM_FI_DEV_FB_TOTAL or (DCGM_FI_DEV_FB_USED + ignoring(__name__) DCGM_FI_DEV_FB_FREE)
kube_gpu_request_query: sum by (namespace, pod) (kube_pod_container_resource_requests{resource=~"nvidia_com_gpu|nvidia.com/gpu"} * on(namespace, pod) group_left() max by (namespace, pod) (kube_pod_status_phase{phase=~"Pending|Running"} == 1))
```

Keep real environment configs under `local/`; that directory is ignored by Git.

## Query Overrides

Use query overrides when your Prometheus has recording rules or different
metric names:

```bash
./bin/ai-gpu-lens dashboard \
  --gpu-util-query 'cluster:dcgm_gpu_utilization:avg' \
  --memory-used-query 'DCGM_FI_DEV_FB_USED' \
  --memory-total-query 'DCGM_FI_DEV_FB_TOTAL' \
  --kube-gpu-request-query 'namespace_workload:gpu_requests:sum' \
  --output reports/custom-dashboard.json
```

If kube-state-metrics GPU request data is unavailable, omit requested-GPU
panels:

```bash
./bin/ai-gpu-lens dashboard \
  --skip-kube-gpu-requests \
  --output reports/gpu-utilization-dashboard.json
```

## 中文速记

- `dashboard` 只生成 JSON，不会连接或修改 Grafana。
- 默认导入时选择 Prometheus datasource。
- 已知 datasource UID 时，用 `--datasource-uid` 固化到 JSON。
- 真实配置放 `local/`，不要提交内部 datasource 名称或环境信息。
- 如果没有 kube-state-metrics GPU request 数据，使用
  `--skip-kube-gpu-requests`。

# Helm Chart / Helm Chart

The `charts/ai-gpu-lens` chart installs a read-only Kubernetes CronJob that
runs `ai-gpu-lens bundle` on a schedule. It reads Prometheus-compatible metrics
from Prometheus or a Grafana datasource proxy and writes report files to a PVC.

`charts/ai-gpu-lens` 会安装一个只读 CronJob，定期运行 `ai-gpu-lens bundle`。
它只读取 Prometheus/Grafana datasource proxy 指标，把报告写入 PVC，不修改
workload 或集群对象。

## Safety Model

- no Kubernetes API write permissions are required
- `automountServiceAccountToken` is disabled
- Grafana/Prometheus credentials come from a Secret
- reports are written to `/reports`
- the container runs as non-root with privilege escalation disabled

## Render Locally

```bash
helm lint charts/ai-gpu-lens
helm template gpu-audit charts/ai-gpu-lens
```

## Install With A Prometheus URL

```bash
helm upgrade --install gpu-audit charts/ai-gpu-lens \
  --namespace gpu-audit \
  --create-namespace \
  --set config.prometheusUrl=http://prometheus.monitoring.svc:9090
```

## Install With Grafana Bearer Token

Create the token Secret outside the chart:

```bash
kubectl create namespace gpu-audit
kubectl -n gpu-audit create secret generic grafana-viewer-token \
  --from-literal=token="$GRAFANA_TOKEN"
```

Use a values file:

```bash
helm upgrade --install gpu-audit charts/ai-gpu-lens \
  --namespace gpu-audit \
  --values examples/helm-values.yaml
```

The values file uses:

```yaml
auth:
  bearerToken:
    existingSecret: grafana-viewer-token
    existingSecretKey: token
```

## Install With Grafana Basic Auth

```bash
kubectl -n gpu-audit create secret generic grafana-viewer-basic-auth \
  --from-literal=basic-auth-password="$GRAFANA_PASSWORD"

helm upgrade --install gpu-audit charts/ai-gpu-lens \
  --namespace gpu-audit \
  --set config.prometheusUrl=https://grafana.example.com/api/datasources/proxy/uid/prometheus \
  --set auth.basicAuth.username=viewer \
  --set auth.basicAuth.existingSecret=grafana-viewer-basic-auth
```

## Trigger One Run

For an immediate run, create a Job from the CronJob:

```bash
kubectl -n gpu-audit create job \
  --from=cronjob/gpu-audit-ai-gpu-lens \
  gpu-audit-manual-$(date +%Y%m%d%H%M)
```

Check status:

```bash
kubectl -n gpu-audit get jobs,pods
kubectl -n gpu-audit logs job/<job-name>
```

## Retrieve Reports

The chart writes to a PVC by default. One simple retrieval method is a temporary
pod that mounts the same claim:

```bash
kubectl -n gpu-audit run report-copy \
  --image=busybox:1.36 \
  --restart=Never \
  --overrides='
{
  "spec": {
    "containers": [{
      "name": "report-copy",
      "image": "busybox:1.36",
      "command": ["sh", "-c", "sleep 3600"],
      "volumeMounts": [{"name": "reports", "mountPath": "/reports"}]
    }],
    "volumes": [{
      "name": "reports",
      "persistentVolumeClaim": {"claimName": "gpu-audit-ai-gpu-lens-reports"}
    }]
  }
}'

kubectl -n gpu-audit cp report-copy:/reports ./reports-from-cluster
kubectl -n gpu-audit delete pod report-copy
```

## Key Values

| Value | Purpose |
| --- | --- |
| `config.prometheusUrl` | Prometheus URL or Grafana datasource proxy URL |
| `config.hours` | Audit window |
| `config.step` | Prometheus query step |
| `config.pricePerGpuHour` | Default cost used for savings estimates |
| `config.gpuPrices` | Optional per-model GPU pricing |
| `auth.bearerToken.existingSecret` | Existing Secret for Grafana/Prometheus bearer token |
| `auth.basicAuth.username` | Basic Auth username |
| `auth.basicAuth.existingSecret` | Existing Secret for Basic Auth password |
| `persistence.enabled` | Use a PVC for report output |
| `cron.schedule` | Cron schedule |

## 中文速记

- chart 只安装 CronJob、ConfigMap、可选 Secret、可选 PVC。
- 默认不挂载 service account token，不需要 Kubernetes API 权限。
- 密码/token 用 Secret，不写入 ConfigMap。
- 报告默认写到 `/reports/latest` 和 `/reports/latest.zip`。
- 先用 `helm template` 看渲染结果，再部署真实环境。

# Redaction / 脱敏

`ai-gpu-lens redact` turns report JSON into public-safe artifacts by replacing
environment identifiers with deterministic aliases. It keeps utilization, cost,
and capacity numbers intact so the report remains useful for demos, customer
reviews, and public case studies.

`ai-gpu-lens redact` 会把报告里的环境标识替换成稳定别名，同时保留利用率、
成本和容量数据，方便生成公开 demo、客户复盘材料或脱敏案例。

## What Gets Redacted

- namespace names
- pod/workload names
- container names
- node/host names
- GPU UUIDs and composite GPU IDs
- Prometheus/Grafana URLs
- action item targets and embedded text references

Examples:

```text
prod-inference -> namespace-001
vllm-worker-0 -> workload-001
gpu-node-a -> node-001
GPU-abc123 -> GPU-REDACTED-001
```

## Generate Redacted Artifacts

```bash
./bin/ai-gpu-lens redact \
  --input reports/customer-audit.json \
  --output reports/customer-audit.redacted.json \
  --html-output reports/customer-audit.redacted.html \
  --markdown-output reports/customer-audit.redacted.md \
  --case-study-output reports/customer-case-study.md \
  --title "Anonymized GPU Audit Case Study" \
  --cluster-name demo-cluster \
  --language en
```

For Chinese output:

```bash
./bin/ai-gpu-lens redact \
  --input reports/customer-audit.json \
  --output reports/customer-audit.redacted.json \
  --case-study-output reports/customer-case-study.zh.md \
  --title "脱敏 GPU 审计案例" \
  --cluster-name demo-cluster \
  --language zh
```

## Public Demo Workflow

For a fresh customer audit, use `bundle --public` to create private and public
deliverables in one run:

```bash
./bin/ai-gpu-lens bundle \
  --config local/customer-grafana.yaml \
  --name customer-gpu-audit \
  --output-dir reports/customer-gpu-audit \
  --archive reports/customer-gpu-audit.zip \
  --public \
  --public-output-dir reports/customer-gpu-audit-public \
  --public-archive reports/customer-gpu-audit-public.zip \
  --public-title "Anonymized GPU Audit Case Study" \
  --public-cluster-name demo-cluster
```

If you already have an audit JSON, use `redact` directly:

1. Run `redact` on the audit JSON.
2. Review the redacted HTML/Markdown/case-study output manually.
3. Share only the redacted artifacts.
4. Keep original reports under `reports/` or another private location.

`reports/` and `local/` are ignored by Git. Do not commit original customer or
environment reports to the public repository.

## Notes

- Redaction aliases are deterministic within one report, not globally stable
  across unrelated runs.
- GPU model names and numeric metrics are preserved.
- The tool redacts identifiers; it does not determine whether business metrics
  or usage patterns are confidential. Review outputs before publishing.

## 中文速记

- `redact` 保留指标和成本，替换环境名称。
- 新审计建议用 `bundle --public` 一次生成私有包和公开脱敏包。
- 可以输出 redacted JSON、HTML、Markdown 和 case study。
- 真实报告仍然只放在 `reports/`，不要提交到 public repo。
- 发布前人工检查一遍脱敏结果。

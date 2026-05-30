# GPU Audit Playbook / GPU 审计交付流程

This playbook turns `ai-gpu-lens` into a repeatable consulting workflow.

目标是把一次 GPU 审计变成可重复交付的流程，而不是只生成一份报表。

## 1. Scope

Clarify before running the audit:

- cluster or Grafana endpoint
- audit window, usually 24 hours for smoke test and 7 days for real review
- GPU hourly price or model-specific prices
- desired report language, `en` or `zh`
- whether the output is internal triage, customer-facing notes, or chargeback

## 2. Safety Rules

`ai-gpu-lens` only reads Prometheus-compatible metrics. It does not write to the
cluster.

Recommended safety posture:

- use a read-only Grafana Viewer or service account
- keep configs under `local/`
- keep generated reports under `reports/`
- do not commit real URLs, usernames, passwords, tokens, or customer reports
- run `doctor` before `audit`

## 3. Preflight

```bash
ai-gpu-lens doctor --config local/customer-grafana.yaml \
  --json-output reports/customer-doctor.json
```

Review:

- DCGM GPU utilization count
- DCGM memory metrics
- kube-state-metrics GPU request availability
- exported workload labels
- GPU model distribution

If core metrics are missing, fix monitoring first or clearly mark the report as
limited.

## 4. First 24 Hour Audit

```bash
ai-gpu-lens audit --config local/customer-grafana.yaml
```

Use this pass to validate:

- credentials and endpoint
- report shape
- whether labels are usable
- whether action items are plausible

Do not make capacity commitments from a single 24 hour window unless the waste
pattern is obvious and operationally safe.

## 5. Seven Day Audit

Update the config:

```yaml
hours: 168
step: 5m
```

Run again:

```bash
ai-gpu-lens audit --config local/customer-grafana.yaml
```

This is the window to use for a customer-facing remediation backlog.

## 6. Review Questions

For each high-priority action item:

- Is the workload still needed?
- Is it batch, notebook, inference, training, or system infrastructure?
- Is low GPU utilization caused by CPU, network, storage, data loading, or queueing?
- Can requests be reduced safely?
- Can jobs be packed onto fewer GPUs?
- Is there a business reason to keep idle headroom?

## 7. Deliverables

A useful delivery package includes:

- HTML report for exploration
- Markdown report for notes
- JSON report for automation or tracking
- optional Grafana dashboard JSON for ongoing visibility
- optional scheduled Helm deployment for recurring audits
- short written summary of top findings
- remediation backlog with owner, risk, and expected savings

Suggested backlog columns:

```text
priority | owner | namespace/workload | finding | proposed action | risk | expected savings | status
```

Use `bundle` to create the standard delivery directory and zip archive:

```bash
ai-gpu-lens bundle \
  --config local/customer-grafana.yaml \
  --name customer-gpu-audit \
  --output-dir reports/customer-gpu-audit \
  --archive reports/customer-gpu-audit.zip
```

For live Prometheus or Grafana endpoints, the bundle includes `doctor.json` and
`doctor.txt`. Use `--skip-doctor` if you do not want preflight details in the
delivery package.

If the customer wants continuous monitoring after the audit, include a Grafana
dashboard JSON:

```bash
ai-gpu-lens dashboard \
  --config local/customer-grafana.yaml \
  --output reports/customer-gpu-dashboard.json
```

If the customer wants recurring audits, deploy the read-only CronJob chart with
a Secret-backed Grafana or Prometheus credential:

```bash
helm upgrade --install customer-gpu-audit charts/ai-gpu-lens \
  --namespace gpu-audit \
  --create-namespace \
  --values local/customer-helm-values.yaml
```

## 8. Follow-Up

After remediation:

- rerun the same audit window length
- compare idle GPU hours, over-requested GPU hours, and telemetry gaps
- keep notes about workload changes that explain metric movement
- avoid comparing a weekday-only audit to a weekend-heavy audit

Use `compare` to produce a follow-up report:

```bash
ai-gpu-lens compare \
  --before reports/customer-week-1/audit.json \
  --after reports/customer-week-2/audit.json \
  --output reports/customer-comparison.html \
  --json-output reports/customer-comparison.json \
  --markdown-output reports/customer-comparison.md \
  --language zh
```

## 中文速记

- 先明确范围：环境、窗口、价格、语言、交付对象。
- 先跑 `doctor`，指标不全就不要直接承诺节省。
- 24 小时适合冒烟测试，7 天适合正式审计。
- 报告中的 action item 是 backlog 起点，需要结合 workload owner 做确认。
- 交付物最好包括 HTML、Markdown、JSON、可选 Grafana dashboard、可选定期审计 CronJob 和一份人工总结。
- 整改后用 `compare` 生成前后对比，重点看节省、回归和遥测缺口变化。

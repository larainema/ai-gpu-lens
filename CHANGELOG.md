# Changelog

## v0.1.0 - 2026-05-28

- Generate bilingual GPU audit reports from Prometheus/DCGM metrics.
- Support Grafana datasource proxy access with Basic Auth or bearer tokens.
- Add doctor checks for DCGM, kube-state-metrics, workload labels, and GPU models.
- Estimate idle GPU hours, requested GPU hours, and over-requested capacity.
- Add executive summaries and prioritized action items.
- Support framebuffer memory total fallback from used plus free memory.
- Add CI, Python package builds, and Docker image packaging.

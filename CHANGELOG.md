# Changelog

## v0.2.0 - 2026-05-29

- Add `ai-gpu-lens bundle` for shareable audit delivery packages.
- Include audit HTML, Markdown, JSON, manifest, and bundle README outputs.
- Include doctor JSON/text outputs in bundles for live Prometheus or Grafana endpoints.
- Add bundle example config, documentation, Makefile target, and CI smoke tests.

## v0.1.0 - 2026-05-28

- Generate bilingual GPU audit reports from Prometheus/DCGM metrics.
- Support Grafana datasource proxy access with Basic Auth or bearer tokens.
- Add doctor checks for DCGM, kube-state-metrics, workload labels, and GPU models.
- Estimate idle GPU hours, requested GPU hours, and over-requested capacity.
- Add executive summaries and prioritized action items.
- Support framebuffer memory total fallback from used plus free memory.
- Add CI, Python package builds, and Docker image packaging.

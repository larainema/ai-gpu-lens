# Changelog

## v0.7.0 - 2026-05-30

- Add `ai-gpu-lens bundle --public` to generate private and public redacted delivery bundles in one run.
- Include redacted audit HTML/JSON/Markdown, public case study, README, manifest, and zip archive in public bundles.
- Support config-driven public bundle paths, case study title, cluster alias, and archive controls.
- Add public bundle docs, example config comments, Makefile target, tests, and CI/package/Docker smoke coverage.

## v0.6.0 - 2026-05-30

- Add `ai-gpu-lens redact` for anonymizing audit and comparison JSON reports.
- Generate redacted audit HTML/Markdown outputs and public case study Markdown from audit JSON.
- Replace namespaces, workloads, nodes, GPU UUIDs, URLs, and embedded text references with deterministic aliases.
- Add redaction documentation, sample public case study, Makefile target, and CI/package/Docker smoke tests.

## v0.5.0 - 2026-05-30

- Add a Helm chart that runs `ai-gpu-lens bundle` as a read-only Kubernetes CronJob.
- Include ConfigMap, optional Secret, optional PVC, ServiceAccount, and hardened pod/container security defaults.
- Support Grafana/Prometheus bearer token or Basic Auth credentials through Kubernetes Secrets.
- Add Helm values example, chart documentation, CI chart validation, and release chart packaging.

## v0.4.0 - 2026-05-29

- Add `ai-gpu-lens dashboard` to generate importable Grafana dashboard JSON.
- Include panels for fleet utilization, per-GPU utilization, framebuffer memory, requested GPUs, low-utilization devices, and metric coverage.
- Support datasource UID, dashboard title/UID, time range, refresh interval, metric query overrides, and config-driven dashboard generation.
- Add dashboard documentation, Makefile target, and CI/package/Docker smoke tests.

## v0.3.0 - 2026-05-29

- Add `ai-gpu-lens compare` for before/after audit JSON reports.
- Generate HTML, Markdown, and JSON comparison outputs.
- Highlight core metric deltas, improved/regressed namespaces and workloads, and telemetry gap changes.
- Add comparison examples, Makefile target, and CI/package/Docker smoke tests.

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

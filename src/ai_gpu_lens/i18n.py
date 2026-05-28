from __future__ import annotations


DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("en", "zh")


TEXT = {
    "en": {
        "active_ratio": "Active ratio",
        "avg_mem": "Avg mem",
        "avg_util": "Avg util",
        "estimated_waste": "Estimated waste based on `--price-per-gpu-hour`",
        "estimated_request_cost": "Estimated request cost",
        "fleet_avg_util": "Fleet avg util",
        "gap_deduped_gpu_series": "One or more physical GPUs had duplicate DCGM series and were deduplicated by GPU UUID/index.",
        "gap_no_memory_total": "Memory total metric is missing for one or more GPUs.",
        "gap_no_memory_used": "Memory used metric is missing for one or more GPUs.",
        "gap_no_kube_gpu_requests": "kube-state-metrics GPU request data is missing; requested-vs-used analysis is limited.",
        "gap_no_namespace_labels": "GPU utilization series do not include Kubernetes namespace labels.",
        "gap_no_pod_labels": "GPU utilization series do not include pod labels.",
        "generated": "Generated",
        "gpu": "GPU",
        "gpu_detail": "GPU Detail",
        "gpus": "GPUs",
        "idle_cost": "Idle cost",
        "idle_gpu_hours": "Idle GPU hours",
        "idle_hours": "Idle hours",
        "json_written": "wrote JSON report: {path}",
        "lang_html": "en",
        "max_util": "Max util",
        "model": "Model",
        "namespace": "Namespace",
        "namespace_attribution": "Namespace Attribution",
        "no_telemetry_gaps": "No major telemetry gaps detected.",
        "node": "Node",
        "not_available": "n/a",
        "pod": "Pod",
        "price_per_hour": "Price/hour",
        "rec_add_memory_metrics": "Add or validate DCGM framebuffer memory metrics to separate compute-bound and memory-bound workloads.",
        "rec_compare_requests": "Compare {requested_hours:,.2f} requested GPU hours against utilized GPU-hour equivalents to find over-requested workloads.",
        "rec_enable_k8s_labels": "Enable Kubernetes pod resource labels in dcgm-exporter so cost can be attributed to teams, namespaces, and workloads.",
        "rec_idle_cost": "At the configured price, idle GPU time represents about ${cost:,.2f} in the audit window.",
        "rec_investigate_idle_gpus": "Investigate {count} GPU series with average utilization below 5%.",
        "rec_low_fleet_utilization": "Fleet utilization is below 35%; start with scheduling fragmentation, right-sizing model replicas, and batch sizing.",
        "rec_no_major_waste": "No major waste pattern was detected in this window; compare against a longer 7 day audit before making capacity changes.",
        "rec_review_binpacking": "Review bin-packing, autoscaling, and model replica counts for GPUs below 20% average utilization and 50% peak utilization.",
        "recommendations": "Recommendations",
        "report_subtitle": "GPU utilization, idle hours, and cost attribution",
        "report_title": "ai-gpu-lens report",
        "requested_cost": "Requested cost",
        "requested_gpu_hours": "Requested GPU hours",
        "requested_gpus": "Requested GPUs",
        "series": "Series",
        "source_series": "Source series",
        "summary": "summary: {gpus} GPU series, {util:.1f}% avg util, {idle_hours:.2f} idle GPU hours",
        "telemetry_gaps": "Telemetry Gaps",
        "utilized_gpu_hour_eq": "Utilized GPU-hour eq.",
        "workload_requests": "Workload GPU Requests",
        "window": "Window",
        "wrote_html": "wrote HTML report: {path}",
        "wrote_markdown": "wrote Markdown report: {path}",
    },
    "zh": {
        "active_ratio": "活跃比例",
        "avg_mem": "平均显存",
        "avg_util": "平均利用率",
        "estimated_waste": "基于 `--price-per-gpu-hour` 估算的浪费成本",
        "estimated_request_cost": "申请成本估算",
        "fleet_avg_util": "集群平均利用率",
        "gap_deduped_gpu_series": "部分物理 GPU 出现重复 DCGM 序列，已按 GPU UUID/index 去重。",
        "gap_no_memory_total": "部分 GPU 缺少显存总量指标。",
        "gap_no_memory_used": "部分 GPU 缺少显存已用指标。",
        "gap_no_kube_gpu_requests": "缺少 kube-state-metrics GPU request 数据，申请量和实际使用量对比会受限。",
        "gap_no_namespace_labels": "GPU 利用率序列缺少 Kubernetes namespace 标签。",
        "gap_no_pod_labels": "GPU 利用率序列缺少 pod 标签。",
        "generated": "生成时间",
        "gpu": "GPU",
        "gpu_detail": "GPU 明细",
        "gpus": "GPU 数量",
        "idle_cost": "空闲成本",
        "idle_gpu_hours": "空闲 GPU 小时",
        "idle_hours": "空闲小时",
        "json_written": "已写入 JSON 报告：{path}",
        "lang_html": "zh-Hans",
        "max_util": "峰值利用率",
        "model": "型号",
        "namespace": "命名空间",
        "namespace_attribution": "命名空间归因",
        "no_telemetry_gaps": "未发现明显的遥测缺口。",
        "node": "节点",
        "not_available": "无数据",
        "pod": "Pod",
        "price_per_hour": "每小时价格",
        "rec_add_memory_metrics": "补充或校验 DCGM 显存指标，用来区分计算瓶颈和显存瓶颈 workload。",
        "rec_compare_requests": "将 {requested_hours:,.2f} 个已申请 GPU 小时与有效 GPU 小时等价进行对比，优先定位过度申请的 workload。",
        "rec_enable_k8s_labels": "为 dcgm-exporter 启用 Kubernetes pod 资源标签，以便把成本归因到团队、命名空间和 workload。",
        "rec_idle_cost": "按当前配置价格估算，本审计窗口内空闲 GPU 时间约为 ${cost:,.2f}。",
        "rec_investigate_idle_gpus": "排查 {count} 条平均利用率低于 5% 的 GPU 序列。",
        "rec_low_fleet_utilization": "集群利用率低于 35%；优先检查调度碎片、模型副本数是否过大，以及 batch size 是否合理。",
        "rec_no_major_waste": "本窗口未发现明显浪费模式；做容量调整前建议再对比 7 天以上的审计数据。",
        "rec_review_binpacking": "检查平均利用率低于 20% 且峰值低于 50% 的 GPU：重点看 bin-packing、自动扩缩容和模型副本数。",
        "recommendations": "建议",
        "report_subtitle": "GPU 利用率、空闲时间和成本归因",
        "report_title": "ai-gpu-lens 报告",
        "requested_cost": "申请成本",
        "requested_gpu_hours": "已申请 GPU 小时",
        "requested_gpus": "申请 GPU 数",
        "series": "序列数",
        "source_series": "来源序列",
        "summary": "摘要：{gpus} 条 GPU 序列，平均利用率 {util:.1f}%，空闲 GPU 小时 {idle_hours:.2f}",
        "telemetry_gaps": "遥测缺口",
        "utilized_gpu_hour_eq": "有效 GPU 小时等价",
        "workload_requests": "Workload GPU 申请量",
        "window": "窗口",
        "wrote_html": "已写入 HTML 报告：{path}",
        "wrote_markdown": "已写入 Markdown 报告：{path}",
    },
}


def normalize_language(language: str | None) -> str:
    if not language:
        return DEFAULT_LANGUAGE
    value = language.strip().lower()
    if value in {"zh", "zh-cn", "zh_hans", "zh-hans", "cn", "chinese", "中文"}:
        return "zh"
    if value in {"en", "en-us", "english"}:
        return "en"
    raise ValueError(f"unsupported language: {language}")


def t(language: str, key: str, **kwargs: object) -> str:
    lang = normalize_language(language)
    template = TEXT[lang].get(key, TEXT[DEFAULT_LANGUAGE][key])
    return template.format(**kwargs)

.PHONY: test sample bundle compare docker-build docker-sample

test:
	python3 -m unittest discover -s tests

sample:
	./bin/ai-gpu-lens audit \
		--from-file examples/sample-prometheus.json \
		--output reports/sample.html \
		--json-output reports/sample.json \
		--markdown-output reports/sample.md \
		--price-per-gpu-hour 2.50 \
		--language zh

bundle:
	./bin/ai-gpu-lens bundle \
		--from-file examples/sample-prometheus.json \
		--name sample-delivery \
		--output-dir reports/sample-delivery \
		--archive reports/sample-delivery.zip \
		--price-per-gpu-hour 2.50 \
		--language zh

compare: sample bundle
	./bin/ai-gpu-lens compare \
		--before reports/sample.json \
		--after reports/sample-delivery/audit.json \
		--output reports/sample-comparison.html \
		--json-output reports/sample-comparison.json \
		--markdown-output reports/sample-comparison.md \
		--language zh

docker-build:
	docker build -t ai-gpu-lens:local .

docker-sample: docker-build
	docker run --rm ai-gpu-lens:local audit \
		--from-file examples/sample-prometheus.json \
		--output /tmp/sample.html \
		--json-output /tmp/sample.json \
		--markdown-output /tmp/sample.md \
		--price-per-gpu-hour 2.50 \
		--language zh

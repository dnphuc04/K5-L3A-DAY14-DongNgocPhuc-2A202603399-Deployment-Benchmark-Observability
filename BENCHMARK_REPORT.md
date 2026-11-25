# Benchmark & Observability Report — Day 14

**Họ tên** Dong Ngoc Phuc

**Ngày chạy** 25/11/2026 (GMT+7)

**Môi trường** Windows, AMD Ryzen 7 H 255, Docker Desktop báo 16 CPU và khoảng 15,3 GiB RAM. Benchmark develop chạy qua loopback bằng Python 3.14. Locust 2.47.0 chạy từ Ubuntu WSL2, qua Nginx của Docker Desktop.

## 1. SLO của agent

| SLI | Ngưỡng | Lý do |
| --- | ---: | --- |
| p95 latency `/ask` | ≤ 500 ms | Giới hạn chờ của 95% request trong bài load test. |
| Error rate `/ask` | ≤ 2% | Dùng cùng ngưỡng với `load_test.py` để so được giữa các lượt. |
| Accuracy trong CI | ≥ 85% | Quality gate cơ bản cho pull request. Lần xác nhận bản v2 sửa KB dùng ngưỡng 100% và không có regression. |

Alert Prometheus của stack dùng các ngưỡng riêng trong cấu hình bài lab, ví dụ error rate > 5% và p95 > 1 giây trong thời gian quy định.

## 2. Benchmark hiệu năng

### 2.1. Concurrency so với latency

Mỗi lượt gửi 300 request đến bản v2 ban đầu với `MOCK_SLOW_RATE=0.03` và `MOCK_ERROR_RATE=0.01`.

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 4.30 | 200.6 | 233.5 | 1691.6 | 1.33% | PASS |
| 10 | 33.11 | 200.7 | 234.2 | 1713.0 | 1.00% | PASS |
| 50 | 107.89 | 200.0 | 247.5 | 1708.4 | 0.67% | PASS |
| 100 | 55.88 | 335.9 | 3462.7 | 3752.3 | 1.00% | FAIL |

RPS tăng đến concurrency 50, rồi giảm ở 100 trong khi p95 vượt 3 giây. Đây là dấu hiệu bão hòa của cấu hình thử nghiệm. Chỉ riêng lượt đo này chưa xác định được nút thắt cụ thể trong app, HTTP client hay hệ điều hành.

### 2.2. Tail latency

Mỗi lượt gửi 300 request ở concurrency 20. Các biến khác được giữ nguyên.

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
| --- | ---: | ---: | ---: |
| 0 | 199.6 | 232.4 | 240.6 |
| 0.03 | 252.9 | 233.8 | 1720.9 |
| 0.1 | 337.9 | 1690.9 | 1727.0 |

p99 đã tăng mạnh khi bật mức 3%, vì nhóm request chậm lọt vào đuôi 1%. Khi lên mức 10%, p95 cũng tăng mạnh. Trung bình pha loãng ảnh hưởng của nhóm chậm với số đông request nhanh, nên khó đọc trải nghiệm ở phần đuôi.

### 2.3. Đọc metrics

Đã xác nhận qua `GET /metrics`: `http_requests_total` là Counter, `agent_in_flight_requests` là Gauge, và `agent_question_length_chars` là Histogram. Sau một lần gọi `/ask`, histogram mới có count bằng 1. Nếu lấy URL gốc làm label, mỗi đường dẫn lạ sinh thêm series và tăng bộ nhớ Prometheus. Route template và nhãn `unmatched` giới hạn số giá trị.

## 3. Benchmark chất lượng

| Chỉ số | v1 | v2 ban đầu | v2 sau sửa KB |
| --- | ---: | ---: | ---: |
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100.00% (23/23) |
| Avg tokens / câu | 56.5 | 109.0 | 112.7 |
| Tổng cost (USD) | 0.000396 | 0.000760 | 0.000783 |
| Cost / câu đúng (USD) | 0.00039615 | 0.00003619 | 0.00003403 |
| Quality gate | FAIL | PASS | PASS |

| ID | Keyword bị thiếu | Thay đổi |
| --- | --- | --- |
| `security-02` | token, hết hạn, chữ ký | Thêm tài liệu phân biệt API key và JWT. |
| `scaling-03` | cpu, memory, custom metrics | Thêm tài liệu về tín hiệu Kubernetes HPA sử dụng để scale. |

Retrieval tăng token và tổng chi phí, nhưng chi phí trên mỗi câu đúng giảm vì v2 trả lời đúng nhiều câu hơn. Lượt eval cuối có bốn request rơi vào nhánh độ trễ giả lập. p95 cao của lượt này chưa đủ để quy chênh lệch latency cho việc sửa KB. Lần eval cuối đạt 23/23 và có 0 regression so với v2 ban đầu.

Trong GitHub Actions, chạy agent v2 với `MOCK_ERROR_RATE=0`, đợi endpoint sẵn sàng, rồi chạy `python eval/run_eval.py --min-accuracy 0.85 --baseline <baseline>`. Job phải truyền nguyên exit code, vì script trả 1 nếu dưới ngưỡng hoặc có regression. Đặt job làm required status check để chặn merge khi thất bại.

## 4. Observability stack

### 4.1. Grafana và metrics qua proxy

[Dashboard Grafana dưới tải](screenshots/grafana-dashboard.png) hiển thị 3 instance, khoảng 62,3 request/s, error rate 1,11%, p95 291,07 ms và 17 request đang xử lý. Truy vấn Prometheus ngay lúc chụp cho p95 khoảng 291,27 ms và trung bình 224,66 ms. Chênh lệch khoảng 67 ms cho thấy nhóm request chậm hơn mức điển hình. Cùng cửa sổ đo, ba instance xử lý lần lượt 21,07, 20,73 và 20,84 request/s, nên tải được chia khá đều. Token đầu vào khoảng 4.598 token/s và đầu ra khoảng 2.447 token/s.

`GET /metrics` qua Nginx trả **404** theo cấu hình. Prometheus scrape từng agent trực tiếp qua mạng Docker. Token đầu vào nhiều hơn vì prompt gồm cả câu hỏi và tài liệu truy xuất. Biểu đồ Tokens/s dùng kiểu xếp chồng, nên số liệu từng loại được đọc riêng qua truy vấn Prometheus.

### 4.2. Thí nghiệm alert

`promtool test rules /p/alert_rules_test.yml` báo **SUCCESS**.

Dùng 30 user, tăng 5 user/giây. Bật hai lỗi mock trong cùng lượt để chụp chúng firing đồng thời. Thời gian tính từ lúc áp dụng cấu hình đến lần đầu API Prometheus báo `firing`.

| Thay đổi | Alert | Thời gian | Panel |
| --- | --- | ---: | --- |
| `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 96,4 giây | Error rate |
| `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 154,8 giây | Latency p95 |
| `docker pause` 1 instance | `AgentInstanceDown` | 38,3 giây | Instances up |

[Ảnh Prometheus](screenshots/prometheus-alert-firing.png) cho thấy hai alert trên cùng firing. Alert chi phí cũng đang firing sau lượt tải nền. Ở lượt riêng, khôi phục cấu hình ban đầu rồi tạm dừng instance `172.22.0.4:8000`. Prometheus vẫn biết target qua Docker DNS nhưng không scrape được, nên `AgentInstanceDown` firing. Sau khi đo, instance đã được unpause. Thời gian phát hiện gồm thời gian chờ đủ dữ liệu trong cửa sổ PromQL, khoảng `for` và chu kỳ đánh giá.

Khi đổi sang v1, endpoint vẫn có thể nhanh và trả 200 nhưng nội dung kém đi. Chạy eval định kỳ hoặc trên canary với golden dataset, so với baseline và đặt cảnh báo riêng cho accuracy hoặc regression.

### 4.3. Trace chậm và trace lỗi

- [Trace chậm](screenshots/jaeger-slow-trace.png) có trace ID `7a9dcb25924bfab9ba7930e95914586f` và tổng thời gian **1704,21 ms**. Span con `chat mock-llm-small` mất **1682,13 ms**, khoảng **98,7%** tổng thời gian. Retrieval mất **17,56 ms**.
- [Trace lỗi](screenshots/jaeger-error-trace.png) có trace ID `8215955b7be73c13801652b6c6a2a9e2`. `POST /ask` trả **503**. Span `chat mock-llm-small` mất **81,95 ms**, có trạng thái ERROR và event `exception`.

Dòng log JSON có cùng trace ID với trace chậm:

```json
{"ts":"2026-11-25T08:49:06.282312+00:00","level":"INFO","service":"observable-agent","instance":"062635dadb27","event":"llm_call","trace_id":"7a9dcb25924bfab9ba7930e95914586f","span_id":"101ce30f811f4150","request_id":"5e9ac2ac6aa2","model":"mock-llm-small","agent_version":"v2","input_tokens":74,"output_tokens":37,"cost_usd":0.000033,"llm_ms":1670.8}
```

## 5. Benchmark scaling

Locust headless, 100 user, 10 user/giây, 2 phút mỗi lượt. Bảng dùng dòng **POST /ask** của CSV.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 59.60 | 190 | 240 | 1700 | 78/7059 (1.10%) |
| 3 | 60.41 | 190 | 220 | 1700 | 73/7215 (1.01%) |

Với 3 instance, p95 giảm từ 240 xuống 220 ms và p99 giữ ở 1700 ms. RPS chỉ tăng từ 59.60 lên 60.41. Ở 100 user với thời gian nghỉ 0,5–2 giây, số request phát sinh có giới hạn và một phần độ trễ đến từ mock LLM, nên thêm instance chỉ cải thiện nhẹ ở tải này.

## 6. Kết luận

1. Đo RPS cùng p95/p99 ở nhiều mức tải để thấy điểm bão hòa và tác động của request chậm.
2. Eval và quality gate phát hiện regression về nội dung ngay cả khi HTTP vẫn trả 200.
3. Metrics phát hiện thời điểm có sự cố. Trace và log có chung `trace_id` giúp xác định khâu xảy ra sự cố.

Với production thật, sẽ thêm SLI về accuracy trên canary và tỉ lệ lỗi theo upstream, cùng cảnh báo theo tốc độ tiêu hao error budget.

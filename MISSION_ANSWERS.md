# Day 14 — Mission Answers

## Part 1 — Localhost vs Production

### 1.1. Anti-patterns

1. `develop/app.py:17–18` ghi API key mẫu và URL database có thông tin đăng nhập trong mã. Secret thật dùng theo cách này sẽ xuất hiện trong lịch sử Git.
2. Dòng 21–22 cố định cấu hình debug và giới hạn token trong mã, khiến việc đổi cấu hình theo môi trường cần sửa source.
3. Dòng 33–38 dùng `print()` để in dữ liệu đầu vào, đầu ra và cả key. Dòng log cũng thiếu các trường nhất quán như thời gian và mức độ.
4. Dòng 42–43 ghi nhận bản develop thiếu endpoint health, nên hệ thống triển khai không có probe riêng để kiểm tra tiến trình.
5. Dòng 51–52 bind vào localhost và cố định cổng 8000. Container cần lắng nghe trên interface phù hợp và nền tảng có thể cấp cổng qua `PORT`.
6. Dòng 53 bật auto-reload, thêm tiến trình giám sát file dành cho phát triển.
7. Bản develop thiếu hook lifecycle riêng để đóng tài nguyên của ứng dụng khi tắt.

### 1.2. Kết quả chạy bản develop

Chạy hai bản mẫu bằng Uvicorn trên Windows, gửi request HTTP qua `127.0.0.1` và đặt `PYTHONIOENCODING=utf-8` để log in được tiếng Việt. Bản production chạy với `ENVIRONMENT=staging`.

| Bản | Request | Kết quả thực tế |
| --- | --- | --- |
| Develop | `POST /ask?question=Hello` | **200**, trả về JSON có trường `answer` từ mock LLM. |
| Develop | `POST /ask` với JSON `{"question":"Hello"}` | **422**, thiếu `query.question`. Chữ ký `ask_agent(question: str)` ở dòng 31 khai báo query parameter. |
| Develop | `GET /health` | **404**, route chưa được định nghĩa. |
| Production | `POST /ask` với cùng JSON | **200**, trả về `question`, `answer` và `model`. |
| Production | `GET /health` | **200**, có `"status":"ok"`. |
| Production | `GET /ready` | **200**, trả về `{"ready":true}`. |

### 1.3. So sánh

| Hạng mục | Develop | Production | Vì sao quan trọng |
| --- | --- | --- | --- |
| Cấu hình | Giá trị cố định trong `app.py:17–22` | `settings` đọc biến môi trường, Uvicorn dùng `settings.port` ở dòng 197 | Một image có thể chạy với cấu hình riêng của từng môi trường. |
| Health và readiness | Thiếu endpoint riêng | `/health` ở dòng 135 và `/ready` ở dòng 152 | Phân biệt tiến trình còn sống và agent đã sẵn sàng nhận tải. |
| Logging | `print()` và in key ở dòng 34 | Log có trường sự kiện và độ dài ở dòng 110–122 | Hỗ trợ truy vấn log và hạn chế đưa dữ liệu nhạy cảm vào log. |
| Shutdown | Thiếu hook dọn tài nguyên của ứng dụng | Shutdown trong lifespan ở dòng 63–67 | Có điểm đóng kết nối sau khi server xử lý các request đang chạy. |
| Bind và reload | `localhost:8000`, reload luôn bật | Host, port và reload theo `settings` ở dòng 196–198 | Container nhận được kết nối từ bên ngoài và có thể tắt reload trong production. |

## Part 2 — Docker

### 2.1. Dockerfile develop

1. Base image là `python:3.11`.
2. Working directory là `/app`.
3. Copy `requirements.txt` trước bước cài dependencies để Docker dùng lại layer cài đặt khi chỉ sửa mã ứng dụng.
4. `ENTRYPOINT` xác định lệnh chính của container. `CMD` đặt lệnh mặc định khi thiếu `ENTRYPOINT`, hoặc đặt đối số mặc định cho `ENTRYPOINT`. Đối số sau tên image trong `docker run` thay thế `CMD`.

### 2.2. Build và chạy container develop

Build từ gốc repo bằng `docker build -f 02-docker/develop/Dockerfile -t day14-lab:develop .`. Chạy container với cổng 8000 ánh xạ ra một cổng loopback tự chọn. `POST /ask?question=What%20is%20Docker%3F` trả **HTTP 200** từ Uvicorn, với câu trả lời mock “Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!”.

### 2.3. Multi-stage build và kích thước image

- Stage `builder` dùng `python:3.11-slim`, cài `gcc` và `libpq-dev`, rồi cài các gói Python vào `/root/.local`.
- Stage `runtime` bắt đầu từ một base slim mới, chép các gói Python đã cài và mã ứng dụng, sau đó chạy dưới quyền `appuser`. Base slim và việc chỉ chép phần cần cho runtime giúp image nhỏ hơn. Công cụ biên dịch nằm trong stage builder.

Build bản production bằng `docker build -f 02-docker/production/Dockerfile -t day14-lab:production .`. Kết quả đo từ `docker image ls day14-lab`:

| Image | DISK USAGE | CONTENT SIZE |
| --- | ---: | ---: |
| `day14-lab:develop` | 1.67 GB | 426 MB |
| `day14-lab:production` | 240 MB | 57.4 MB |

Mức giảm theo **CONTENT SIZE**, tính từ số byte của `docker image inspect`: `(426320381 − 57408971) / 426320381 × 100 = 86.53%`.

### 2.4. Docker Compose và Nginx

```text
Client ── HTTP :80 ──> Nginx ── HTTP :8000 ──> agent
                                             ├── Redis :6379  (cache, session, rate limit)
                                             └── Qdrant :6333 (lưu vector)
```

Nginx, agent, Redis và Qdrant cùng nằm trên mạng nội bộ của Compose. Host truy cập agent qua Nginx. Compose đợi Redis và Qdrant báo healthy trước khi bật agent. Hai đường nối đến Redis và Qdrant biểu diễn cấu hình của stack. Endpoint mẫu `/ask` gọi mock LLM trực tiếp.

Chạy `docker compose -p k5-day14-docker up -d --build --wait` trong `02-docker/production/` với file `.env.local` rỗng đã được Git ignore. Cả bốn service khởi động thành công.

| HTTP qua Nginx | Kết quả thực tế |
| --- | --- |
| `GET /health` | **200 OK**, header `Server: nginx`, JSON có `"status":"ok"` và version `2.0.0`. |
| `POST /ask` với JSON `{"question":"Explain microservices"}` | **200 OK**, header `Server: nginx`, JSON có câu trả lời mock trong trường `answer`. |

## Part 3 — Cloud Deployment

### 3.1. Deploy Railway

Agent Part 6 và Redis đã chạy trong môi trường production. [URL public](https://agent-production-4e6fa674.up.railway.app). Kiểm tra trực tiếp cho kết quả `/health` → 200, `/ready` → 200, `POST /ask` thiếu key → 401 và có key → 200. Xem [bằng chứng dashboard](screenshots/dashboard.png) và [kết quả kiểm tra](DEPLOYMENT.md).

### 3.2. So sánh cấu hình mẫu Railway và Render

Cả hai cấu hình chạy Uvicorn trên `0.0.0.0:$PORT` và dùng `/health`. Mẫu Railway khai báo builder Nixpacks, timeout health check và số lần restart khi lỗi. Mẫu Render khai báo lệnh cài dependencies, region, tự deploy khi push, cách cấp biến môi trường và service Redis trong cùng Blueprint.

### 3.3. Pipeline Cloud Run

1. Cloud Build cài dependencies và chạy pytest.
2. Sau bước test, pipeline build Docker image với tag commit SHA và `latest`, rồi push hai tag lên registry.
3. Pipeline deploy image theo commit SHA lên Cloud Run tại `asia-southeast1` và lấy secret qua Secret Manager.
4. `service.yaml` là cấu hình khai báo riêng cho Cloud Run, có giới hạn 1–10 instance, concurrency 80, startup probe `/ready` và liveness probe `/health`.

## Part 4 — API Security

### 4.1–4.3. API key, JWT và rate limit

Chạy hai app mẫu qua Uvicorn trên Windows và gọi bằng `curl.exe -i`. Các kết quả dưới đây giữ lại status line, header liên quan và response body.

```http
HTTP/1.1 401 Unauthorized

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

```http
HTTP/1.1 200 OK

{"question":"What is Docker?","answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

Ở bản production mẫu, `POST /auth/token` với tài khoản lab trả `200` và cấp JWT bearer có thời hạn 60 phút. Dùng cùng token gọi `POST /ask` 11 lần. Mười lần đầu trả `200`, lần thứ 11 trả:

```http
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 59

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### 4.4. Cost guard

Kiểm tra số tiền đã dùng trước khi gọi LLM. Sau khi hoàn tất, tính chi phí từ token vào và ra theo đơn giá tương ứng, rồi cộng vào tổng. Agent final dùng Redis với tổng theo ngày UTC và trả `402` khi tổng đã ghi đạt ngân sách. Chi phí được cộng nguyên tử trong Redis sau khi có phản hồi. Các request đã qua kiểm tra và đang chạy đồng thời vẫn có thể làm tổng chi phí vượt ngưỡng. Rate limit bảo vệ năng lực phục vụ theo phút, còn cost guard chặn chi phí tích lũy khi mỗi request tiêu thụ số token khác nhau.

## Part 5 — Scaling & Reliability

1. **Health và readiness.** `/health` kiểm tra tiến trình còn sống. `/ready` kiểm tra dependency cần để nhận tải, ví dụ Redis. Agent final giữ `/health` ở `200` khi Redis lỗi và trả `503` ở `/ready`.
2. **Graceful shutdown.** Khi nhận SIGTERM, Uvicorn dừng nhận công việc mới, đợi request đang chạy hoàn tất rồi chạy phần cleanup trong lifespan để đóng Redis. Checker Part 6 nhận được `200` cho request đang chạy khi gửi SIGTERM.
3. **Stateless.** State đặt trong RAM sẽ nằm riêng ở từng process và mất khi process restart. Bản mẫu lưu lịch sử theo session trong Redis để mọi instance đọc cùng một lịch sử.
4. **Load balancing.** Chạy `docker compose -p k5-day14-scaling up -d --build --pull never --scale agent=3 --wait` trong thư mục production. Dùng image Redis và Nginx đã có ở local sau khi Docker Hub giới hạn pull. Cả ba agent healthy. `GET /health` và `GET /ready` qua Nginx cổng 8080 đều trả `200`; header `X-Served-By` cho thấy hai địa chỉ upstream khác nhau.
5. **Kiểm tra session.** `python test_stateless.py` gửi 5 lượt qua 3 instance. Redis trả về đủ 10 tin nhắn của phiên, gồm 5 câu hỏi và 5 câu trả lời. Script kiểm tra lịch sử xuyên instance. Thí nghiệm chưa thử dừng một instance khi đang gửi request.

## Part 6 — Final Project

Chạy `python check_production_ready.py` đầy đủ trong Ubuntu WSL2 với Python 3.11 và Docker Desktop. Docker CLI được gọi qua một wrapper ngoài repo để đổi đường dẫn Compose từ WSL sang Windows. Smoke test bổ sung qua Docker Compose trên cổng 18065 trả `ready: true` và câu trả lời mock với API key thử nghiệm. Trích phần checklist của checker:

```text
📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 41/41 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

## AI log

- Dùng Codex để đọc đề, xác định anti-patterns, lập bảng so sánh, đọc cấu hình cloud mẫu và chạy kiểm tra Part 1. Kiểm tra ban đầu bằng TestClient, sau đó chạy lại bằng Uvicorn và xác nhận đủ sáu mã HTTP trong bảng. Mã mẫu được giữ nguyên.

- Dùng Codex để đọc Dockerfile và Compose, chạy container develop, đo kích thước image Docker và xác nhận hai request qua Nginx. Số đo và mã HTTP trong Part 2 lấy từ lệnh chạy trên máy.

- Dùng Codex để chạy mẫu Security và Scaling, triển khai các TODO của Part 6 và xem lại kết quả checker. Đã xác nhận các mã HTTP, lịch sử Redis và PASS 12/12 trên máy. Checker được giữ nguyên.

- Dùng Codex để chạy benchmark và eval, thêm histogram và tài liệu JWT/HPA, khắc phục Docker image observability thiếu đường dẫn package, thu screenshot rồi đối chiếu báo cáo với JSON/CSV gốc. Golden dataset được giữ nguyên.

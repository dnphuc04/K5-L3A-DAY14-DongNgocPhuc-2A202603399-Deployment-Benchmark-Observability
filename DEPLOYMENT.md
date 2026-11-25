# Deployment — Day 14

**Nền tảng** Railway, project `day14-agent-deployment`, môi trường `production`.

**URL public** [https://agent-production-4e6fa674.up.railway.app](https://agent-production-4e6fa674.up.railway.app).

Cấu hình deploy ở `06-lab-complete/railway.toml`. Service `agent` đã được build từ `06-lab-complete/` và kết nối tới service Redis cùng dự án. Railway CLI báo bản triển khai `bcbb2966-0406-48db-a417-814863ea7b75` ở trạng thái `SUCCESS`.

| Biến môi trường | Cấu hình đã đặt |
| --- | --- |
| `AGENT_API_KEY` | Giá trị ngẫu nhiên lưu trong Railway. |
| `REDIS_URL` | Tham chiếu biến kết nối từ service Redis. |
| `ENVIRONMENT` | `production` |
| `PORT` | Do Railway cấp. |
| `LOG_LEVEL` | `INFO` |

## Kiểm tra URL public

Đặt `BASE=https://agent-production-4e6fa674.up.railway.app` và nạp `AGENT_API_KEY` vào biến môi trường của shell. Các lệnh chỉ in mã HTTP.

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"    # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'    # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'                                      # 200
```

Kết quả kiểm tra trực tiếp qua HTTPS:

```text
https://agent-production-4e6fa674.up.railway.app

GET /health -> HTTP 200
{"status":"ok","environment":"production"}
GET /ready -> HTTP 200
{"ready":true}
POST /ask (no API key) -> HTTP 401
{"detail":"Missing or invalid API key"}
POST /ask (API key redacted) -> HTTP 200
{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

- [Dashboard Railway](screenshots/dashboard.png) cho thấy cả agent và Redis Online.
- [Bản deploy đang chạy](screenshots/running.png) hiển thị ACTIVE và Deployment successful trên Railway.
- [Kết quả kiểm tra HTTP](screenshots/test.png) chụp trang tổng hợp từ bốn request HTTPS thực tế. Trang chỉ hiển thị trạng thái và response body, đã ẩn API key.

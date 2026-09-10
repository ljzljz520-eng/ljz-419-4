# 售后工单微服务系统

三个服务 + 一个前端页面，通过网关统一访问；全链路日志携带 `trace_id`。

## 架构

```
浏览器 ──> gateway :8000 ──┬──> auth   :8001  (用户 / 角色 / JWT)
           (静态页面+反代)  └──> ticket :8002  (工单创建 / 派发 / 关闭)
```

- **gateway**：托管前端静态页；`/api/auth/*` 代理到 auth 服务，`/api/tickets*` 代理到 ticket 服务；在边界生成 `X-Trace-ID` 并向下游透传。
- **auth**：角色（admin / agent / customer）与用户管理，注册、登录（JWT）、token 校验接口。
- **ticket**：工单创建、列表、派发（assign）、关闭（close）；通过调用 auth 服务校验 token，并转发 `X-Trace-ID`，两个服务的日志可用同一 trace_id 串联。

每个服务独立 SQLite 数据库，启动时先执行 Alembic 迁移再拉起服务。

## 快速开始（Docker）

```bash
docker compose up --build
```

然后打开 http://localhost:8000 ，初始管理员账号 `admin / admin123`。

健康检查：

```bash
curl localhost:8000/health    # 网关 + 下游状态
curl localhost:18001/health   # auth（宿主端口 18001 映射到容器 8001）
curl localhost:18002/health   # ticket（宿主端口 18002 映射到容器 8002）
```

## 本地开发

```bash
# auth
cd services/auth && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --port 8001

# ticket（另一个终端）
cd services/ticket && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --port 8002

# gateway（另一个终端）
cd gateway && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000
```

## 运行测试

```bash
cd services/auth   && .venv/bin/python -m pytest tests/ -q
cd services/ticket && .venv/bin/python -m pytest tests/ -q
```

测试使用临时 SQLite 库并执行真实 Alembic 迁移；ticket 服务的测试通过依赖覆盖模拟 auth 服务返回值。

## API 摘要

| 方法 | 路径（经网关） | 说明 | 权限 |
|---|---|---|---|
| POST | /api/auth/register | 注册（固定为客户角色，忽略客户端传入的 role） | 公开 |
| POST | /api/auth/login | 登录，返回 JWT | 公开 |
| GET  | /api/auth/verify | 校验 token，返回当前用户 | 登录 |
| GET  | /api/auth/users | 用户列表 | admin |
| POST | /api/auth/users | 开通账号（可指定 admin/agent/customer 角色） | admin |
| GET  | /api/auth/users/{id} | 查询用户 | admin / agent |
| GET  | /api/auth/roles | 角色列表 | 公开 |
| POST | /api/tickets | 创建工单 | 登录 |
| GET  | /api/tickets?status= | 工单列表（客户只见自己的） | 登录 |
| GET  | /api/tickets/{id} | 工单详情 | 相关人 / 客服 / 管理员 |
| POST | /api/tickets/{id}/assign | 派发工单 | admin / agent |
| POST | /api/tickets/{id}/close | 关闭工单 | 创建人 / 处理人 / admin |

## trace_id 说明

- 请求可自带 `X-Trace-ID` 头；不带时网关自动生成。
- 网关 → ticket → auth 的每一次内部调用都转发该头。
- 三个服务的每条日志都包含 `trace_id=<id>`，响应头也会回传 `X-Trace-ID`。

示例：`curl -H "X-Trace-ID: demo-1" localhost:8000/health`，随后在各服务日志中检索 `demo-1`。

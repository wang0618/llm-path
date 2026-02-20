# Proxy 实现设计

## 项目结构

```
llm-trace/
├── pyproject.toml          # 项目配置和依赖
├── llm_trace/
│   ├── __init__.py
│   ├── cli.py              # 命令行入口
│   ├── proxy.py            # 代理服务器核心逻辑
│   ├── storage.py          # JSONL 存储
│   └── models.py           # 数据模型定义
└── traces/                 # 默认存储目录
    └── .gitkeep
```

## 依赖

- `httpx` - HTTP 客户端，支持流式和异步
- `uvicorn` - ASGI 服务器
- `starlette` - 轻量 Web 框架

## 实现步骤

### 第一步：数据模型 (`models.py`)

定义请求记录的结构：

```python
@dataclass
class TraceRecord:
    id: str                    # uuid
    timestamp: str             # ISO format
    request: dict              # 原始请求体
    response: dict | None      # 响应内容
    duration_ms: int           # 耗时
    error: str | None          # 如果出错
```

### 第二步：存储层 (`storage.py`)

- `append(record: TraceRecord)` - 追加一条记录到 JSONL
- 线程安全（用锁或 queue）
- 文件路径可配置

### 第三步：代理核心 (`proxy.py`)

处理 `/v1/chat/completions` 路由：

1. 接收客户端请求
2. 提取 `Authorization` header（透传）
3. 判断 `stream` 参数
4. 转发到 `https://api.openai.com/v1/chat/completions`
5. **非流式**：等待完整响应，存储，返回
6. **流式**：使用 `StreamingResponse`，边转发边收集 chunks，结束后存储

### 第四步：CLI 入口 (`cli.py`)

```bash
python -m llm_trace --port 8080 --output ./traces/trace.jsonl
```

参数：
- `--port` 监听端口（默认 8080）
- `--output` JSONL 输出路径
- `--target` 目标 API 地址（默认 OpenAI，方便以后扩展）

## 流式处理细节

OpenAI 的 SSE 格式：

```
data: {"id":"...","choices":[{"delta":{"content":"Hello"}}]}
data: {"id":"...","choices":[{"delta":{"content":" world"}}]}
data: [DONE]
```

Proxy 需要：

1. 逐行转发给客户端（保持实时性）
2. 解析每个 chunk，提取 `delta.content`
3. 最后拼接成完整响应存储

## JSONL 记录格式

每行一个请求记录：

```json
{
  "id": "uuid",
  "timestamp": "2024-01-15T10:30:00Z",
  "request": {
    "model": "gpt-4",
    "messages": [...],
    "...其他参数"
  },
  "response": {
    "content": "...",
    "usage": {"prompt_tokens": 100, "completion_tokens": 50}
  },
  "duration_ms": 1200
}
```

## 数据流

```
Client Request
      │
      ▼
┌─────────────┐
│   Proxy     │
│  (Starlette)│
└─────────────┘
      │
      ▼
┌─────────────┐        ┌─────────────┐
│   httpx     │───────▶│  OpenAI API │
│   client    │◀───────│             │
└─────────────┘        └─────────────┘
      │
      ▼
┌─────────────┐
│   Storage   │───────▶ trace.jsonl
└─────────────┘
      │
      ▼
Client Response
```

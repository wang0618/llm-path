# LLM上下文trace可视化 -- 实现设计

总体流程:
1. 通过 Cli 工具将LLM原始请求进行预处理，生成用于可视化的json文件
2. 使用Web UI，加载可视化json文件，对LLM请求可视化

## 原始数据预处理

LLM原始数据为JSONL结构，每一行为一个TraceRecord，表示一次LLM请求的request和response信息。格式如下:

### TraceRecord 格式

```json
{
  "id": "uuid",
  "timestamp": "ISO format",
  "request": {
    "messages": [...],
    "model": "...",
    "tools": [...],
    ...
  },
  "response": {
    "choices": [{"message": {...}, ...}],
    ...
  },
  "duration_ms": 1200,
  "error": null
}
```


messages 示例：

```json
[
  {
      "role": "system",
      "content": "..."
  },
  {
      "role": "user",
      "content": "查询今年中国都有哪些节假日"
  },
  {
      "role": "assistant",
      "content": "我来帮你查询2026年中国法定节假日。",
      "tool_calls": [
          {
              "id": "call_gst80jbkh7bamkv81tyucky3",
              "type": "function",
              "function": {
                  "name": "web_search",
                  "arguments": "{\"query\": \"2026年中国法定节假日 放假安排\", \"count\": 5}",
              }
          }
      ]
  },
  {
      "role": "tool",
      "tool_call_id": "call_gst80jbkh7bamkv81tyucky3",
      "name": "web_search",
      "content": "..."
  },
]
```

tools格式:

```json
[
  {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the contents of a file at the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to read"
                }
            },
            "required": [
                "path"
            ]
        }
    }
  },
  ...
]
```

choices格式：

```json
// 普通消息的格式
[
  {
      "finish_reason": "stop",
      "message": {
          "content": "根据国务院办公厅发布的通知，**2026年中国法定节假日**安排如下：...",
          "role": "assistant"
      }
  }
]

// tool_use时的格式
[
    {
        "finish_reason": "tool_calls",
        "message": {
            "content": "我来帮你查询2026年中国法定节假日。",
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "arguments": "{\"query\": \"2026年中国法定节假日 放假安排\", \"count\": 5}",
                        "name": "web_search"
                    },
                    "id": "call_gst80jbkh7bamkv81tyucky3",
                    "type": "function"
                }
            ]
        }
    }
]
```

### 预处理算法

预处理的目的是为了更便于UI比较两次请求间上下文的差异，同时提供更标准化的message和tool的表示，以及减少数据体积。

预处理后输出格式：

```json
{
  "messages": [
    {
      "id": "msg-uuid",
      "role": "system" | "user" | "tool_use" | "tool_result" | "assistant", // 上下文新增的输入的类型
      "content": "我来帮你查询2026年中国法定节假日。",
      "tool_calls": [ // tool_calls 仅当role=tool_use时提供
          {
            "name": "web_search",
            "arguments": {  // 如果原arguments为json编码，则先解码
                "query": "2026年中国法定节假日 放假安排",
                "count": 5
            }
          }
      ]
    },
    ...
  ],
  "tools": [
    {
        "id": "tool-uuid",
        "name": "read_file",
        "description": "Read the contents of a file at the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to read"
                }
            },
            "required": [
                "path"
            ]
        }
    },
    ...
  ],
  "requests": [
    {
      "id": "request-uuid",
      "parent_id": "parent-request-uuid" | null,  // 本次会话的上一个llm请求id
      "timestamp": "unix timestamp in ms",
      "request_messages": ["msg-1", "msg-2", ...],  // 本次请求发送的全部message，为 $.messages 中id的引用
      "response_message": "msg-n",  // 为 $.messages 中id的引用
      "model": "...",
      "tools": ["tool1", ...],  // 列表元素为 $.tools 中id的引用
      "duration_ms": 1200  // 请求耗时
    },
    ...
  ]
}
```

messages中存储所有请求的消息集合，消息会在去重后分配唯一的uuid。tools也是如此。
requests存储llm的请求列表，通过直接引用messages和tools中的id来减少存储体积。

目前的实现中，暂时假设原始数据中的所有请求都属于同一个llm会话（且逻辑关系为线性关系），因此 request.parentId 为时间上的上一个llm请求的id。

预处理命令:

uv run llm-trace cook ./traces/trace.jsonl -o ./viewer/public/data.json

## 可视化

由于目前假设requests间逻辑关系为线性关系，因此先仅对requests列表进行可视化，不渲染requests间的关系图。

UI整体分为左右两部分，左侧请求列表栏，右侧展示选中的请求的详情。

请求列表栏显示请求耗时和类型(类型通过图标区分)。
请求详情面板分上下两部分，上部分展示请求的request信息，下部分展示response信息。

request信息有messages和tools两个tab：
messages tab以差分的形式展示本次请求的request messages与parent-request的 requestMessages + responseMessage 的diff。
diff以message为粒度，有三种形态：新增message、删除message、修改message
未发生变化的message默认隐藏，可通过点击来展开。

messages tab UI结构示意：

[old-message] -> [new-message]
...
-[del-message]
...
+[new-message]

其中可通过点击 ... 来展开未变化的message

tools tab显示当前请求携带的所有tool列表

原型图参考 @ui.jpg （注意图中的messages和tools两个tab内容应该是同一时间只展示一个）

启动可视化服务:
```bash
cd viewer
npm install  # 首次运行
npm run dev
```
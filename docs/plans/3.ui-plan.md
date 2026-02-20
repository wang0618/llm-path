# 前端设计规划

功能设计参见 viz-design.md 

UI设计图参见 ui.jpg


## 技术栈

| 类别 | 选择 | 理由 |
|------|------|------|
| 框架 | React + TypeScript | 类型安全，组件化 |
| 构建 | Vite | 快速开发，已有配置 |
| 样式 | Tailwind CSS | 快速原型，与原型图风格匹配 |
| 状态 | React Context / Zustand | 轻量，请求列表+详情的简单状态 |

## 目录结构

```
viewer/
├── src/
│   ├── types/
│   │   └── index.ts          # Message, Tool, Request 类型定义
│   ├── hooks/
│   │   ├── useTraceData.ts   # 加载 data.json
│   │   └── useDiff.ts        # 计算 message diff
│   ├── components/
│   │   ├── layout/
│   │   │   └── Layout.tsx    # 左右分栏布局
│   │   ├── sidebar/
│   │   │   ├── RequestList.tsx      # 请求列表
│   │   │   └── RequestListItem.tsx  # 单个请求项（时间、耗时、图标）
│   │   ├── detail/
│   │   │   ├── RequestDetail.tsx    # 详情面板容器
│   │   │   ├── RequestHeader.tsx    # 请求头（ID、模型、时间）
│   │   │   ├── MessageTab.tsx       # Messages 差分视图
│   │   │   ├── ToolsTab.tsx         # Tools 列表
│   │   │   └── ResponseSection.tsx  # Response 展示
│   │   └── diff/
│   │       ├── DiffView.tsx         # 差分容器
│   │       ├── AddedMessage.tsx     # + 新增消息（绿色）
│   │       ├── DeletedMessage.tsx   # - 删除消息（红色）
│   │       ├── ModifiedMessage.tsx  # 修改消息（左→右）
│   │       └── CollapsedGroup.tsx   # ... 折叠的未变化消息
│   ├── utils/
│   │   └── diff.ts           # diff 算法（LCS 或简单比较）
│   ├── App.tsx
│   └── main.tsx
├── public/
│   └── data.json             # cook 命令输出
└── index.html
```

## 核心组件设计

### 1. Layout（左右分栏）

```
┌──────────────┬──────────────────────────────────────────┐
│  TRACE       │  req-uuid-abc123  Model: gpt-4  10:45:32 │
│  REQUESTS    ├──────────────────────────────────────────┤
│              │  REQUEST CONTEXT                         │
│  [列表项...]  │  [Messages] [Tools]  ← Tab 切换          │
│              │  ┌────────────────────────────────────┐  │
│              │  │ Diff View                          │  │
│              │  └────────────────────────────────────┘  │
│              ├──────────────────────────────────────────┤
│              │  RESPONSE                                │
│              │  [response message]                      │
└──────────────┴──────────────────────────────────────────┘
```

### 2. Message Diff 算法

```typescript
interface DiffResult {
  type: 'unchanged' | 'added' | 'deleted' | 'modified';
  oldMessage?: Message;
  newMessage?: Message;
}

function computeDiff(
  parentMessages: string[],   // parent.request_messages + parent.response_message
  currentMessages: string[]   // current.request_messages
): DiffResult[]
```

diff 策略：
- 基于 message ID 比较（因为 cook 已做去重）
- `unchanged`: 两边都有相同 ID
- `added`: 仅在 current 中存在
- `deleted`: 仅在 parent 中存在
- `modified`: 同位置但 ID 不同（可选，按索引对齐）

### 3. 消息渲染

根据 role 显示不同样式标签：
- `system` → 灰色
- `user` → 蓝色
- `tool_use` → 紫色 + 显示 tool_calls
- `tool_result` → 橙色
- `assistant` → 绿色

## 数据流

```
data.json
    ↓
useTraceData() → { messages, tools, requests }
    ↓
App (selectedRequestId state)
    ↓
    ├── RequestList (显示所有 requests)
    │       └── onClick → setSelectedRequestId
    │
    └── RequestDetail (显示选中的 request)
            ├── useDiff(parentRequest, currentRequest)
            ├── MessageTab → DiffView
            ├── ToolsTab → 工具列表
            └── ResponseSection
```

## 关键交互

| 交互 | 实现 |
|------|------|
| 点击请求列表项 | 高亮选中，右侧显示详情 |
| Tab 切换 | Messages / Tools 面板切换 |
| 点击 `...` 展开 | 显示折叠的未变化消息 |
| 工具参数折叠 | 点击 "Parameter schema ∨" 展开 JSON |

## 类型定义

```typescript
interface Message {
  id: string;
  role: 'system' | 'user' | 'tool_use' | 'tool_result' | 'assistant';
  content: string;
  tool_calls?: ToolCall[];
}

interface Tool {
  id: string;
  name: string;
  description: string;
  parameters: object;
}

interface Request {
  id: string;
  parent_id: string | null;
  timestamp: number;
  request_messages: string[];
  response_message: string;
  model: string;
  tools: string[];
  duration_ms: number;
}

interface TraceData {
  messages: Message[];
  tools: Tool[];
  requests: Request[];
}
```

## 实现优先级

### P0 - 核心功能 ✅ (已完成)
- [x] 数据加载 + 请求列表展示
- [x] 请求详情基础展示（不含 diff）
- [x] Response 展示
- [x] Tools Tab

### P1 - Diff 功能
- [ ] Message diff 计算
- [ ] Diff 视图渲染（增/删/改）
- [ ] 折叠展开交互

### P2 - 完善
- [ ] 样式优化

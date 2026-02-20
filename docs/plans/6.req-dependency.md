# 请求依赖分析

在目前的设计中(见 ./viz-design.md 文档)，是假设 requests 间逻辑关系为线性关系。实际请求之间的关系不为线性（对话回退如 rewind 会产生分叉），本文档描述如何分析请求间依赖关系的算法。

## 输入

请求列表：

```json
[
    {
      "id": "request-uuid",
      "parent_id": null,
      "timestamp": "unix timestamp in ms",
      "request_messages": ["msg-1", "msg-2", ...],  // 本次请求发送的全部 message，为 $.messages 中 id 的引用
      "response_message": "msg-n",  // 为 $.messages 中 id 的引用，可能为 null（请求失败时）
      "model": "...",
      "tools": ["tool1", ...],  // 列表元素为 $.tools 中 id 的引用
      "duration_ms": 1200  // 请求耗时
    },
    ...
]
```

## 目标

为每个请求的 `parent_id` 赋值，构建请求间的**依赖森林**（允许多个根节点）。

## 算法

### 核心思路

1. 按时间戳排序，保证 parent 一定出现在当前请求之前
2. **过滤候选**：跳过 model 不同的请求（不同模型间无依赖关系）
3. 优先检查前缀关系（精确匹配）
4. 若无精确匹配，使用综合得分（消息编辑距离 + 工具相似度）找最相似的 parent
5. **森林支持**：如果最佳得分低于阈值，则成为新的根节点

### 得分计算

综合得分由两部分组成：

```
total_score = message_score + tool_score

message_score = -edit_distance(candidate_messages, curr_messages)
tool_score = -TOOL_DIFF_PENALTY * tool_diff_count
```

其中：
- `message_score`：消息编辑距离的负值
- `tool_score`：工具差异的惩罚，`tool_diff_count` 为工具集合的对称差集大小
- `TOOL_DIFF_PENALTY`：工具差异惩罚系数（默认 0.5）

### 阈值判断（森林支持）

使用相对阈值判断是否应该成为新根节点：

```python
# 相对阈值：编辑距离超过当前消息数的一定比例，则成为新根
RELATIVE_THRESHOLD = 0.5  # 50%

if best_score < -len(curr.request_messages) * RELATIVE_THRESHOLD:
    return None  # 成为新根节点
```

这个设计使得：
- 消息数少时（如 2 条），阈值为 -1，稍有不同就成为新根
- 消息数多时（如 20 条），阈值为 -10，允许更大的差异

### 伪代码

```python
TOOL_DIFF_PENALTY = 0.5   # 每个不同的 tool 扣 0.5 分
RELATIVE_THRESHOLD = 0.5  # 编辑距离超过消息数的 50% 则成为新根


def find_parent(curr, candidates):
    """
    为当前请求找到最合适的 parent

    Args:
        curr: 当前请求
        candidates: 时间早于 curr 的所有请求（按时间升序）

    Returns:
        parent_id 或 None（成为新根节点）
    """
    # 过滤：只考虑相同 model 的候选
    same_model_candidates = [c for c in candidates if c.model == curr.model]

    if not same_model_candidates:
        return None  # 没有相同 model 的候选，成为新根

    # 优化：优先检查前缀关系（从最近的开始找）
    for c in reversed(same_model_candidates):
        expected_prefix = build_expected_prefix(c)
        if is_prefix(expected_prefix, curr.request_messages):
            return c.id

    # 回退：使用综合得分找最相似的 parent
    best_score = float('-inf')
    best_parent_id = None

    for c in reversed(same_model_candidates):
        score = match_score(curr, c)
        if score > best_score:
            best_score = score
            best_parent_id = c.id

    # 森林支持：得分过低则成为新根节点
    threshold = -len(curr.request_messages) * RELATIVE_THRESHOLD
    if best_score < threshold:
        return None

    return best_parent_id


def match_score(curr, candidate):
    """
    计算综合匹配得分

    得分 = 消息编辑距离得分 + 工具相似度得分
    """
    # 消息得分：编辑距离的负值
    a = build_expected_prefix(candidate)
    b = curr.request_messages
    message_score = -levenshtein(a, b)

    # 工具得分：工具差异的惩罚
    curr_tools = set(curr.tools)
    candidate_tools = set(candidate.tools)
    tool_diff = len(curr_tools.symmetric_difference(candidate_tools))
    tool_score = -TOOL_DIFF_PENALTY * tool_diff

    return message_score + tool_score


def build_expected_prefix(candidate):
    """
    构建期望的消息前缀

    如果 candidate 有 response_message，则前缀为 request_messages + [response_message]
    否则只有 request_messages
    """
    prefix = list(candidate.request_messages)
    if candidate.response_message is not None:
        prefix.append(candidate.response_message)
    return prefix


def is_prefix(prefix, messages):
    """检查 prefix 是否为 messages 的前缀"""
    if len(prefix) > len(messages):
        return False
    return messages[:len(prefix)] == prefix


def levenshtein(a, b):
    """
    计算两个列表的编辑距离（Levenshtein distance）

    操作：添加、删除、替换
    """
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i-1] == b[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(
                    dp[i-1][j],    # 删除
                    dp[i][j-1],    # 添加
                    dp[i-1][j-1]   # 替换
                )

    return dp[m][n]


# 主流程
def analyze_dependencies(requests):
    requests.sort(key=lambda r: r.timestamp)

    for idx, req in enumerate(requests):
        if idx == 0:
            req.parent_id = None  # 第一个请求无 parent
        else:
            req.parent_id = find_parent(req, requests[:idx])
```

## 边界情况

| 场景 | 处理方式 |
|------|----------|
| 第一个请求 | `parent_id = None` |
| 请求失败（无 response_message） | `build_expected_prefix` 只返回 `request_messages` |
| 多个候选得分相同 | 选择时间最近的（通过 `reversed` 遍历实现） |
| 空的 request_messages | 正常处理，编辑距离会计算为对方的长度 |
| 不同 model | 直接跳过，不考虑作为候选 parent |
| 没有相同 model 的候选 | 成为新根节点 |
| 工具集合差异大 | 降低匹配得分，但不直接排除 |
| 得分低于阈值 | 成为新根节点（森林结构） |

## 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `TOOL_DIFF_PENALTY` | 0.5 | 每个不同的工具扣除的分数 |
| `RELATIVE_THRESHOLD` | 0.5 | 编辑距离超过消息数的该比例时成为新根 |

## 复杂度

- 时间复杂度：O(n² × m²)，其中 n 为请求数，m 为平均消息数
- 空间复杂度：O(m²)（编辑距离 DP 表）

对于典型的 trace 文件（几百个请求），性能可接受。


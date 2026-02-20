export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
}

export interface Message {
  id: string;
  role: 'system' | 'user' | 'tool_use' | 'tool_result' | 'assistant' | 'thinking';
  content: string;
  tool_calls?: ToolCall[];
}

export interface Tool {
  id: string;
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

export interface Request {
  id: string;
  parent_id: string | null;
  timestamp: number;
  request_messages: string[];
  response_messages: string[];
  model: string;
  tools: string[];
  duration_ms: number;
}

export interface TraceData {
  messages: Message[];
  tools: Tool[];
  requests: Request[];
}

export interface DiffItem {
  type: 'unchanged' | 'added' | 'deleted' | 'modified';
  oldMessage?: Message;  // unchanged/deleted/modified
  newMessage?: Message;  // unchanged/added/modified
}

export interface DiffResult {
  items: DiffItem[];
  summary: { unchanged: number; added: number; deleted: number; modified: number };
}

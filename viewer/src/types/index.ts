export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
  id?: string;  // Tool use ID (e.g., "call_xxx")
}

export interface Message {
  id: string;
  role: 'system' | 'user' | 'tool_use' | 'tool_result' | 'assistant' | 'thinking';
  content: string;
  tool_calls?: ToolCall[];
  tool_use_id?: string;  // For tool_result: references the tool_use it responds to
  is_error?: boolean;    // For tool_result: whether the tool execution failed
}

export interface Tool {
  id: string;
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  is_server_side?: boolean;  // True for server-side tools (e.g., Gemini's googleSearch)
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
  type: 'unchanged' | 'added' | 'deleted';
  oldMessage?: Message;  // unchanged/deleted
  newMessage?: Message;  // unchanged/added
}

export interface DiffResult {
  items: DiffItem[];
  summary: { unchanged: number; added: number; deleted: number };
}

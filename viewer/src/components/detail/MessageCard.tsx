import type { Message } from '../../types';

interface MessageCardProps {
  message: Message;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

export const MESSAGE_MAX_LINES = 8;
export const MESSAGE_MAX_CHARS = 500;
const LINE_HEIGHT = 1.5; // matches leading-relaxed

export function getMessageLineCount(message: Message): number {
  if (!message.content) return 0;
  return message.content.split('\n').length;
}

export function getMessageCharCount(message: Message): number {
  if (!message.content) return 0;
  return message.content.length;
}

export function shouldTruncateMessage(message: Message): boolean {
  return getMessageLineCount(message) > MESSAGE_MAX_LINES ||
         getMessageCharCount(message) > MESSAGE_MAX_CHARS;
}

const roleConfig: Record<Message['role'], { label: string; colorClass: string; bgClass: string; bgSolidClass: string }> = {
  system: {
    label: 'system',
    colorClass: 'text-role-system',
    bgClass: 'bg-role-system/10 border-role-system/30',
    bgSolidClass: 'bg-[color-mix(in_srgb,var(--color-role-system)_10%,var(--color-bg-primary))]',
  },
  user: {
    label: 'user',
    colorClass: 'text-role-user',
    bgClass: 'bg-role-user/10 border-role-user/30',
    bgSolidClass: 'bg-[color-mix(in_srgb,var(--color-role-user)_10%,var(--color-bg-primary))]',
  },
  assistant: {
    label: 'assistant',
    colorClass: 'text-role-assistant',
    bgClass: 'bg-role-assistant/10 border-role-assistant/30',
    bgSolidClass: 'bg-[color-mix(in_srgb,var(--color-role-assistant)_10%,var(--color-bg-primary))]',
  },
  tool_use: {
    label: 'tool_use',
    colorClass: 'text-role-tool-use',
    bgClass: 'bg-role-tool-use/10 border-role-tool-use/30',
    bgSolidClass: 'bg-[color-mix(in_srgb,var(--color-role-tool-use)_10%,var(--color-bg-primary))]',
  },
  tool_result: {
    label: 'tool_result',
    colorClass: 'text-role-tool-result',
    bgClass: 'bg-role-tool-result/10 border-role-tool-result/30',
    bgSolidClass: 'bg-[color-mix(in_srgb,var(--color-role-tool-result)_10%,var(--color-bg-primary))]',
  },
  thinking: {
    label: 'thinking',
    colorClass: 'text-role-thinking',
    bgClass: 'bg-role-thinking/10 border-role-thinking/30',
    bgSolidClass: 'bg-[color-mix(in_srgb,var(--color-role-thinking)_10%,var(--color-bg-primary))]',
  },
};

export function MessageCard({ message, isExpanded = false, onToggleExpand }: MessageCardProps) {
  const config = roleConfig[message.role];
  const contentLineCount = getMessageLineCount(message);
  const shouldTruncate = shouldTruncateMessage(message);

  return (
    <div className={`rounded-lg border ${config.bgClass}`}>
      {/* Header */}
      <div className="px-4 py-2 border-b border-inherit flex items-center gap-2">
        <span className={`text-xs font-mono font-medium uppercase ${config.colorClass}`}>
          {config.label}
        </span>
      </div>

      {/* Content */}
      <div className="px-4 py-3">
        {message.content && (
          <div className="relative">
            <div
              className={`text-sm text-text-primary whitespace-pre-wrap break-words leading-relaxed ${
                shouldTruncate && !isExpanded ? 'overflow-hidden' : ''
              }`}
              style={
                shouldTruncate && !isExpanded
                  ? {
                      maxHeight: `${MESSAGE_MAX_LINES * LINE_HEIGHT}em`,
                      maskImage: 'linear-gradient(to bottom, black 80%, transparent 100%)',
                      WebkitMaskImage: 'linear-gradient(to bottom, black 80%, transparent 100%)',
                    }
                  : undefined
              }
            >
              {message.content}
            </div>
            {shouldTruncate && !isExpanded && onToggleExpand && (
              <button
                onClick={onToggleExpand}
                className="mt-1 text-xs font-medium text-text-muted hover:text-text-primary transition-colors"
              >
                展开 ({contentLineCount} 行)
              </button>
            )}
          </div>
        )}

        {/* Tool Calls */}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className="mt-3 space-y-2">
            {message.tool_calls.map((call, idx) => (
              <div
                key={idx}
                className="rounded bg-bg-primary/50 border border-border-muted overflow-hidden"
              >
                <div className="px-3 py-1.5 bg-bg-tertiary border-b border-border-muted">
                  <span className="font-mono text-xs text-role-tool-use font-medium">
                    {call.name}
                  </span>
                </div>
                <pre className="px-3 py-2 text-xs font-mono text-text-secondary overflow-x-auto">
                  {JSON.stringify(call.arguments, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Sticky collapse button when expanded */}
      {shouldTruncate && isExpanded && onToggleExpand && (
        <div className={`sticky bottom-0 px-4 py-2 border-t border-inherit rounded-b-lg ${config.bgSolidClass}`}>
          <button
            onClick={onToggleExpand}
            className="text-xs font-medium text-text-muted hover:text-text-primary transition-colors"
          >
            收起
          </button>
        </div>
      )}
    </div>
  );
}

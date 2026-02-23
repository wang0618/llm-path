import { useState, useMemo } from 'react';
import type { Tool } from '../../types';

interface ToolCardProps {
  tool: Tool;
}

const MAX_DESCRIPTION_LINES = 10;

export function ToolCard({ tool }: ToolCardProps) {
  const [schemaExpanded, setSchemaExpanded] = useState(false);
  const [descExpanded, setDescExpanded] = useState(false);

  const { truncatedDesc, fullDesc, needsTruncation } = useMemo(() => {
    if (!tool.description) {
      return { truncatedDesc: '', fullDesc: '', needsTruncation: false };
    }
    const lines = tool.description.split('\n');
    const needsTruncation = lines.length > MAX_DESCRIPTION_LINES;
    const truncatedDesc = needsTruncation
      ? lines.slice(0, MAX_DESCRIPTION_LINES).join('\n')
      : tool.description;
    return { truncatedDesc, fullDesc: tool.description, needsTruncation };
  }, [tool.description]);

  return (
    <div className="rounded-lg border border-border-default bg-bg-elevated overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-medium text-text-primary">
            {tool.name}
          </span>
          {tool.is_server_side && (
            <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/20">
              Server side
            </span>
          )}
        </div>
        {tool.description && (
          <div className="mt-2">
            <pre className="text-xs text-text-secondary leading-relaxed whitespace-pre-wrap font-sans overflow-x-auto">
              {descExpanded ? fullDesc : truncatedDesc}
            </pre>
            {needsTruncation && (
              <button
                onClick={() => setDescExpanded(!descExpanded)}
                className="mt-1 text-xs text-text-muted hover:text-text-secondary transition-colors"
              >
                {descExpanded ? '▲ Show less' : '▼ Show more...'}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Parameter Schema Toggle */}
      <button
        onClick={() => setSchemaExpanded(!schemaExpanded)}
        className="w-full px-4 py-2 border-t border-border-muted bg-bg-tertiary/50 flex items-center justify-between text-xs text-text-muted hover:text-text-secondary transition-colors"
      >
        <span>Parameter schema</span>
        <span className={`transition-transform duration-fast ${schemaExpanded ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>

      {/* Parameters */}
      {schemaExpanded && (
        <pre className="px-4 py-3 border-t border-border-muted text-xs font-mono text-text-secondary overflow-x-auto bg-bg-primary/30">
          {JSON.stringify(tool.parameters, null, 2)}
        </pre>
      )}
    </div>
  );
}

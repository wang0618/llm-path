import type { Request } from '../../types';
import { ThemeToggle } from '../ThemeToggle';

interface RequestHeaderProps {
  request: Request;
}

function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp);
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function GitHubIcon() {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="currentColor"
      className="w-5 h-5"
      aria-hidden="true"
    >
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

export function RequestHeader({ request }: RequestHeaderProps) {
  return (
    <div className="px-6 py-4 border-b border-border-default bg-bg-secondary">
      <div className="flex items-center gap-4 flex-wrap">
        {/* Title */}
        <span className="text-sm font-medium text-text-primary uppercase tracking-wide">
          Request Info
        </span>

        {/* Divider */}
        <span className="text-border-default">│</span>

        {/* Model */}
        <span className="text-sm text-text-secondary">
          Model: <span className="text-text-primary font-medium">{request.model}</span>
        </span>

        {/* Divider */}
        <span className="text-border-default">│</span>

        {/* Timestamp */}
        <span className="text-sm font-mono text-text-muted">
          {formatTimestamp(request.timestamp)}
        </span>

        {/* Duration - now after timestamp */}
        <span className="text-xs font-mono px-2 py-1 rounded bg-bg-tertiary text-text-secondary">
          {request.duration_ms}ms
        </span>

        {/* Right side actions */}
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          <a
            href="https://github.com/wang0618/llm-trace"
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 rounded-md text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors"
            title="View on GitHub"
          >
            <GitHubIcon />
          </a>
        </div>
      </div>
    </div>
  );
}

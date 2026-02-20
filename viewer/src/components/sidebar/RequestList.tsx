import type { Request, Message } from '../../types';
import { RequestGraph } from './RequestGraph';

interface RequestListProps {
  requests: Request[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  getMessage: (id: string) => Message | undefined;
}

export function RequestList({ requests, selectedId, onSelect, getMessage }: RequestListProps) {
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border-default">
        <h1 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Trace Requests
        </h1>
        <p className="text-xs text-text-muted mt-1">
          {requests.length} request{requests.length !== 1 ? 's' : ''}
        </p>
      </div>

      {/* Graph */}
      <div className="flex-1 overflow-y-auto">
        {requests.length === 0 ? (
          <div className="px-4 py-8 text-center text-text-muted text-sm">
            No requests found
          </div>
        ) : (
          <RequestGraph
            requests={requests}
            selectedId={selectedId}
            onSelect={onSelect}
            getMessage={getMessage}
          />
        )}
      </div>
    </div>
  );
}

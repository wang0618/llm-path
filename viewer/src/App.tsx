import { useState, useEffect, useMemo, useCallback } from 'react';
import { useTraceData } from './hooks/useTraceData';
import { Layout } from './components/layout/Layout';
import { RequestList } from './components/sidebar/RequestList';
import { RequestDetail } from './components/detail/RequestDetail';

function App() {
  const { data, loading, error, getMessage, getTool, getRequest } = useTraceData();
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);

  // Sort requests by timestamp (same order as RequestGraph displays)
  const sortedRequestIds = useMemo(() => {
    if (!data) return [];
    return [...data.requests]
      .sort((a, b) => a.timestamp - b.timestamp)
      .map((r) => r.id);
  }, [data]);

  // Auto-select first request when data loads
  if (data && !selectedRequestId && sortedRequestIds.length > 0) {
    setSelectedRequestId(sortedRequestIds[0]);
  }

  // Keyboard navigation for up/down arrow keys
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (sortedRequestIds.length === 0 || !selectedRequestId) return;

      // Skip if user is focused on an input/textarea
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

      const currentIndex = sortedRequestIds.indexOf(selectedRequestId);
      if (currentIndex === -1) return;

      if (e.key === 'ArrowDown' || e.key === 'j') {
        e.preventDefault();
        const nextIndex = Math.min(currentIndex + 1, sortedRequestIds.length - 1);
        setSelectedRequestId(sortedRequestIds[nextIndex]);
      } else if (e.key === 'ArrowUp' || e.key === 'k') {
        e.preventDefault();
        const prevIndex = Math.max(currentIndex - 1, 0);
        setSelectedRequestId(sortedRequestIds[prevIndex]);
      } else if (e.key === ' ' && data) {
        // Space: navigate to first child node (leftmost branch = largest subtree)
        e.preventDefault();
        const children = data.requests.filter((r) => r.parent_id === selectedRequestId);
        if (children.length > 0) {
          // Build children map for subtree size calculation
          const childrenMap = new Map<string, string[]>();
          for (const r of data.requests) {
            if (r.parent_id) {
              const siblings = childrenMap.get(r.parent_id) || [];
              siblings.push(r.id);
              childrenMap.set(r.parent_id, siblings);
            }
          }
          // Calculate subtree size recursively
          const getSubtreeSize = (id: string): number => {
            const kids = childrenMap.get(id) || [];
            return 1 + kids.reduce((sum, kid) => sum + getSubtreeSize(kid), 0);
          };
          // Sort by subtree size descending, pick largest (leftmost branch)
          children.sort((a, b) => getSubtreeSize(b.id) - getSubtreeSize(a.id));
          setSelectedRequestId(children[0].id);
        }
      }
    },
    [sortedRequestIds, selectedRequestId, data],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const selectedRequest = selectedRequestId ? getRequest(selectedRequestId) : null;

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-bg-primary">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-2 border-border-accent border-t-transparent rounded-full animate-spin mb-4" />
          <p className="text-text-secondary text-sm">Loading trace data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    const params = new URLSearchParams(window.location.search);
    const localPath = params.get('local');

    return (
      <div className="h-full flex items-center justify-center bg-bg-primary">
        <div className="text-center max-w-md px-6">
          <div className="text-4xl mb-4">⚠</div>
          <h1 className="text-lg font-semibold text-text-primary mb-2">Failed to Load Data</h1>
          <p className="text-text-secondary text-sm mb-4">{error}</p>
          {localPath ? (
            <p className="text-text-muted text-xs">
              File not found: <code className="bg-bg-tertiary px-1.5 py-0.5 rounded">{localPath}</code>
            </p>
          ) : (
            <p className="text-text-muted text-xs">
              Run: <code className="bg-bg-tertiary px-1.5 py-0.5 rounded">llm-path viewer ./traces/trace.jsonl</code>
            </p>
          )}
        </div>
      </div>
    );
  }

  if (!data || data.requests.length === 0) {
    return (
      <div className="h-full flex items-center justify-center bg-bg-primary">
        <div className="text-center max-w-md px-6">
          <div className="text-4xl mb-4 opacity-50">◇</div>
          <h1 className="text-lg font-semibold text-text-primary mb-2">No Requests Found</h1>
          <p className="text-text-secondary text-sm">
            The trace data file is empty or contains no requests.
          </p>
        </div>
      </div>
    );
  }

  return (
    <Layout
      sidebar={
        <RequestList
          requests={data.requests}
          selectedId={selectedRequestId}
          onSelect={setSelectedRequestId}
          getMessage={getMessage}
        />
      }
      main={
        selectedRequest ? (
          <RequestDetail
            request={selectedRequest}
            getMessage={getMessage}
            getTool={getTool}
            getRequest={getRequest}
          />
        ) : (
          <div className="h-full flex items-center justify-center">
            <p className="text-text-muted text-sm">Select a request to view details</p>
          </div>
        )
      }
    />
  );
}

export default App;

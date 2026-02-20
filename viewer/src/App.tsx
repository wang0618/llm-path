import { useState } from 'react';
import { useTraceData } from './hooks/useTraceData';
import { Layout } from './components/layout/Layout';
import { RequestList } from './components/sidebar/RequestList';
import { RequestDetail } from './components/detail/RequestDetail';

function App() {
  const { data, loading, error, getMessage, getTool, getRequest } = useTraceData();
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);

  // Auto-select first request when data loads
  if (data && !selectedRequestId && data.requests.length > 0) {
    setSelectedRequestId(data.requests[0].id);
  }

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
    return (
      <div className="h-full flex items-center justify-center bg-bg-primary">
        <div className="text-center max-w-md px-6">
          <div className="text-4xl mb-4">⚠</div>
          <h1 className="text-lg font-semibold text-text-primary mb-2">Failed to Load Data</h1>
          <p className="text-text-secondary text-sm mb-4">{error}</p>
          <p className="text-text-muted text-xs">
            Make sure <code className="bg-bg-tertiary px-1.5 py-0.5 rounded">/public/data.json</code> exists.
            <br />
            Run: <code className="bg-bg-tertiary px-1.5 py-0.5 rounded">uv run llm-trace cook ./traces/trace.jsonl -o ./viewer/public/data.json</code>
          </p>
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

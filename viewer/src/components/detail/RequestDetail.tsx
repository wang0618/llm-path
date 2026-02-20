import { useState } from 'react';
import type { Request, Message, Tool } from '../../types';
import { RequestHeader } from './RequestHeader';
import { MessageCard } from './MessageCard';
import { ToolCard } from './ToolCard';
import { DiffView } from '../diff/DiffView';
import { useDiff } from '../../hooks/useDiff';

interface RequestDetailProps {
  request: Request;
  getMessage: (id: string) => Message | undefined;
  getTool: (id: string) => Tool | undefined;
  getRequest: (id: string) => Request | undefined;
}

type TabType = 'messages' | 'tools';

export function RequestDetail({ request, getMessage, getTool, getRequest }: RequestDetailProps) {
  const [activeTab, setActiveTab] = useState<TabType>('messages');
  const [expandedMessageId, setExpandedMessageId] = useState<string | null>(null);

  const parentRequest = request.parent_id ? getRequest(request.parent_id) ?? null : null;

  const { diff } = useDiff({
    currentRequest: request,
    parentRequest,
    getMessage,
  });

  const requestMessages = request.request_messages
    .map(id => getMessage(id))
    .filter((m): m is Message => m !== undefined);

  const responseMessages = request.response_messages
    .map(id => getMessage(id))
    .filter((m): m is Message => m !== undefined);

  const tools = request.tools
    .map(id => getTool(id))
    .filter((t): t is Tool => t !== undefined);

  const handleToggleExpand = (messageId: string) => {
    setExpandedMessageId(prev => prev === messageId ? null : messageId);
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <RequestHeader request={request} />

      {/* Request Context Section */}
      <div className="flex-1 min-h-0 flex flex-col">
        {/* Section Header with Tabs */}
        <div className="px-6 py-3 border-b border-border-default bg-bg-primary">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              Request Context
            </h2>

            {/* Tabs */}
            <div className="flex gap-1 bg-bg-tertiary rounded-lg p-1">
              <button
                onClick={() => setActiveTab('messages')}
                className={`
                  px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-fast
                  ${activeTab === 'messages'
                    ? 'bg-bg-elevated text-text-primary shadow-sm'
                    : 'text-text-secondary hover:text-text-primary'
                  }
                `}
              >
                Messages
                <span className="ml-1.5 text-text-muted">
                  ({requestMessages.length})
                </span>
              </button>
              <button
                onClick={() => setActiveTab('tools')}
                className={`
                  px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-fast
                  ${activeTab === 'tools'
                    ? 'bg-bg-elevated text-text-primary shadow-sm'
                    : 'text-text-secondary hover:text-text-primary'
                  }
                `}
              >
                Tools
                <span className="ml-1.5 text-text-muted">
                  ({tools.length})
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto p-6 pb-0">
          {activeTab === 'messages' ? (
            <DiffView
              diff={diff}
              expandedMessageId={expandedMessageId}
              onToggleExpand={handleToggleExpand}
            />
          ) : (
            <div className="space-y-3 pb-6">
              {tools.length === 0 ? (
                <div className="text-center text-text-muted py-8">
                  No tools in this request
                </div>
              ) : (
                tools.map((tool) => (
                  <ToolCard key={tool.id} tool={tool} />
                ))
              )}
            </div>
          )}
        </div>

      </div>

      {/* Response Section */}
      <div className="border-t border-border-default">
        <div className="px-6 py-3 bg-bg-primary border-b border-border-muted">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            Response
          </h2>
        </div>
        <div className="p-6 bg-bg-secondary max-h-[30vh] overflow-y-auto">
          {responseMessages.length > 0 ? (
            <div className="space-y-3">
              {responseMessages.map((message) => (
                <MessageCard
                  key={message.id}
                  message={message}
                  isExpanded={true}
                />
              ))}
            </div>
          ) : (
            <div className="text-center text-text-muted py-4">
              No response message
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

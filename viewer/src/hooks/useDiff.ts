import { useMemo } from 'react';
import type { Request, Message, DiffResult } from '../types';
import { computeMessageDiff, computeFirstRequestDiff } from '../utils/diff';

interface UseDiffParams {
  currentRequest: Request;
  parentRequest: Request | null;
  getMessage: (id: string) => Message | undefined;
}

interface UseDiffResult {
  diff: DiffResult;
  hasParent: boolean;
}

/**
 * Hook to compute the diff between current request messages and parent request messages
 */
export function useDiff({ currentRequest, parentRequest, getMessage }: UseDiffParams): UseDiffResult {
  const hasParent = parentRequest !== null;

  const diff = useMemo(() => {
    // Current request messages (what was sent to the API)
    const currentMessageIds = currentRequest.request_messages;

    if (!hasParent || !parentRequest) {
      // First request: all messages are "added"
      return computeFirstRequestDiff(currentMessageIds, getMessage);
    }

    // Parent messages = parent's request messages + parent's response messages
    const parentMessageIds = [
      ...parentRequest.request_messages,
      ...parentRequest.response_messages,
    ];

    return computeMessageDiff(parentMessageIds, currentMessageIds, getMessage);
  }, [currentRequest, parentRequest, hasParent, getMessage]);

  return { diff, hasParent };
}

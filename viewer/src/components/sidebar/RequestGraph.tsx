import { useMemo, type ReactElement } from 'react';
import type { Request, Message } from '../../types';
import { buildRequestTree, type RequestTreeNode } from '../../utils/treeLayout';

// ─── Constants ────────────────────────────────────────────────────────────────

const ROW_HEIGHT = 48;
const COL_WIDTH = 20;
const NODE_R = 5;
const LEFT_PAD = 14;

// ─── Types ────────────────────────────────────────────────────────────────────

interface FlatNode {
  id: string;
  request: Request;
  column: number;
  branchId: number;
  parentId: string | null;
  isNewBranch: boolean;
  isIsolated: boolean; // Single-node tree (no parent, no children)
}

// ─── Column Assignment (git-style) ────────────────────────────────────────────

// Cache for subtree sizes to avoid recomputation
const subtreeSizeCache = new Map<string, number>();

function getSubtreeSize(node: RequestTreeNode): number {
  const cached = subtreeSizeCache.get(node.request.id);
  if (cached !== undefined) return cached;

  let size = 1; // Current node
  for (const child of node.children) {
    size += getSubtreeSize(child);
  }
  subtreeSizeCache.set(node.request.id, size);
  return size;
}

function assignBranchIds(
  node: RequestTreeNode,
  branchId: number,
  isNewBranch: boolean,
  counter: { value: number },
  parentId: string | null,
  out: FlatNode[],
): void {
  out.push({
    id: node.request.id,
    request: node.request,
    column: -1, // To be assigned later
    branchId,
    parentId,
    isNewBranch,
    isIsolated: false, // Part of a multi-node tree
  });

  if (node.children.length > 0) {
    // Sort children by subtree size (descending) - largest subtree keeps original branch
    const sortedChildren = [...node.children].sort(
      (a, b) => getSubtreeSize(b) - getSubtreeSize(a),
    );

    sortedChildren.forEach((child, i) => {
      if (i === 0) {
        assignBranchIds(child, branchId, false, counter, node.request.id, out);
      } else {
        const newBranchId = counter.value++;
        assignBranchIds(child, newBranchId, true, counter, node.request.id, out);
      }
    });
  }
}

function buildFlatNodes(roots: RequestTreeNode[]): FlatNode[] {
  const out: FlatNode[] = [];

  // Clear subtree size cache for fresh computation
  subtreeSizeCache.clear();

  // Separate single-node trees (roots with no children) from multi-node trees
  const singleNodeRoots = roots.filter((root) => root.children.length === 0);
  const multiNodeRoots = roots.filter((root) => root.children.length > 0);

  // All single-node trees go to column 0 (consolidated)
  for (const root of singleNodeRoots) {
    out.push({
      id: root.request.id,
      request: root.request,
      column: 0,
      branchId: -1,
      parentId: null,
      isNewBranch: false,
      isIsolated: true, // No connections for isolated nodes
    });
  }

  // Multi-node trees get assigned branchIds
  // Start from branchId 1 if there are single-node trees, otherwise from branchId 0
  const startBranchId = singleNodeRoots.length > 0 ? 1 : 0;
  const counter = { value: startBranchId + 1 };

  multiNodeRoots.forEach((root, i) => {
    const branchId = i === 0 ? startBranchId : counter.value++;
    assignBranchIds(root, branchId, i > 0, counter, null, out);
  });

  // Sort by timestamp for strict chronological order
  out.sort((a, b) => a.request.timestamp - b.request.timestamp);

  const rowById = new Map<string, number>(out.map((n, i) => [n.id, i]));
  
  // Greedy Column Allocation
  const branches = new Map<number, { startRow: number; endRow: number; nodes: FlatNode[] }>();
  
  out.forEach((node, rowIdx) => {
    if (node.isIsolated) return;
    
    if (!branches.has(node.branchId)) {
      let startRow = rowIdx;
      if (node.isNewBranch && node.parentId !== null) {
        const parentRow = rowById.get(node.parentId);
        if (parentRow !== undefined) {
          startRow = parentRow; // Branch visually starts at parent row
        }
      }
      branches.set(node.branchId, { startRow, endRow: rowIdx, nodes: [] });
    }
    const b = branches.get(node.branchId)!;
    b.endRow = Math.max(b.endRow, rowIdx);
    b.nodes.push(node);
  });
  
  const sortedBranchIds = Array.from(branches.keys()).sort((a, b) => a - b);
  const minCol = singleNodeRoots.length > 0 ? 1 : 0;
  const colSpans = new Map<number, {start: number, end: number}[]>();
  
  for (const branchId of sortedBranchIds) {
    const b = branches.get(branchId)!;
    
    let col = minCol;
    while (true) {
      const spans = colSpans.get(col) || [];
      const overlap = spans.some(s => Math.max(b.startRow, s.start) <= Math.min(b.endRow, s.end));
      if (!overlap) break;
      col++;
    }
    
    b.nodes.forEach(node => node.column = col);
    
    if (!colSpans.has(col)) {
      colSpans.set(col, []);
    }
    colSpans.get(col)!.push({start: b.startRow, end: b.endRow});
  }

  return out;
}

// ─── Lane Spans ───────────────────────────────────────────────────────────────

interface LaneSpan {
  openY: number;
  endY: number;
  column: number;
}

function curveHeight(dx: number) {
  return Math.max(ROW_HEIGHT, dx * 0.75);
}

function colX(col: number) {
  return LEFT_PAD + col * COL_WIDTH;
}

function rowY(row: number) {
  return row * ROW_HEIGHT + ROW_HEIGHT / 2;
}

function buildLaneSpans(flat: FlatNode[]): Map<number, LaneSpan> {
  const rowById = new Map<string, number>(flat.map((n, i) => [n.id, i]));
  const spans = new Map<number, LaneSpan>();

  flat.forEach((node, rowIdx) => {
    // Skip isolated nodes - they don't contribute to lane spans
    if (node.isIsolated) return;

    const span = spans.get(node.branchId);
    const nodeY = rowY(rowIdx);
    const endY = span ? Math.max(span.endY, nodeY) : nodeY;

    let openY: number;
    if (node.isNewBranch && node.parentId !== null) {
      const parentRowIdx = rowById.get(node.parentId) ?? rowIdx;
      const parentNode = flat[parentRowIdx];
      const dx = Math.abs(colX(node.column) - colX(parentNode.column));
      const preferredOpenY = rowY(parentRowIdx) + curveHeight(dx);
      // Ensure lane doesn't start past the node position
      openY = Math.min(preferredOpenY, nodeY);
    } else {
      openY = span ? Math.min(span.openY, nodeY) : nodeY;
    }

    spans.set(node.branchId, { openY, endY, column: node.column });
  });

  return spans;
}

// ─── SVG Connector Layer ──────────────────────────────────────────────────────

interface ConnectorProps {
  flat: FlatNode[];
  laneSpans: Map<number, LaneSpan>;
  totalRows: number;
  svgWidth: number;
}

function ConnectorLayer({ flat, laneSpans, totalRows, svgWidth }: ConnectorProps) {
  const elems: ReactElement[] = [];
  const rowById = new Map<string, number>(flat.map((n, i) => [n.id, i]));

  // Vertical lane lines
  laneSpans.forEach((span, branchId) => {
    const x = colX(span.column);
    if (span.endY > span.openY) {
      elems.push(
        <line
          key={`lane-${branchId}`}
          x1={x}
          y1={span.openY}
          x2={x}
          y2={span.endY}
          stroke="var(--color-border-default)"
          strokeWidth="1.5"
        />,
      );
    }
  });

  // S-curve connectors for branches
  flat.forEach((node, nodeIdx) => {
    if (!node.isNewBranch || !node.parentId) return;
    const parentRow = rowById.get(node.parentId);
    if (parentRow === undefined) return;

    const parentNode = flat[parentRow];
    const px = colX(parentNode.column);
    const py = rowY(parentRow);
    const cx = colX(node.column);
    const nodeY = rowY(nodeIdx); // Child node's actual Y position
    const dx = Math.abs(cx - px);
    const preferredEndY = py + curveHeight(dx);
    // Ensure curve doesn't extend past the child node
    const endY = Math.min(preferredEndY, nodeY);
    const midY = py + (endY - py) / 2;
    const d = `M ${px} ${py} C ${px} ${midY} ${cx} ${midY} ${cx} ${endY}`;
    elems.push(
      <path
        key={`scurve-${node.id}`}
        d={d}
        fill="none"
        stroke="var(--color-border-default)"
        strokeWidth="1.5"
      />,
    );
  });

  return (
    <svg
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: svgWidth,
        height: totalRows * ROW_HEIGHT,
        pointerEvents: 'none',
        zIndex: 1,
      }}
    >
      {elems}
    </svg>
  );
}

// ─── Formatting Helpers ───────────────────────────────────────────────────────

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function getMessageSummary(message: Message | undefined): string {
  if (!message) return '-';
  const content = message.content || '';
  if (!content) return '-';
  return content.slice(0, 200);
}

function formatRole(role: string): string {
  switch (role) {
    case 'user': return 'user';
    case 'assistant': return 'assistant';
    case 'system': return 'system';
    case 'tool_use': return 'tool_use';
    case 'tool_result': return 'tool_result';
    default: return role;
  }
}

// ─── Single Row ───────────────────────────────────────────────────────────────

interface GraphRowProps {
  node: FlatNode;
  svgWidth: number;
  isSelected: boolean;
  onClick: () => void;
  getMessage: (id: string) => Message | undefined;
}

function GraphRow({ node, svgWidth, isSelected, onClick, getMessage }: GraphRowProps) {
  const cx = colX(node.column);
  const cy = ROW_HEIGHT / 2;
  const { request } = node;

  // Get the last message from request_messages
  const lastMessageId = request.request_messages[request.request_messages.length - 1];
  const lastMessage = lastMessageId ? getMessage(lastMessageId) : undefined;
  const summary = getMessageSummary(lastMessage);
  const messageType = lastMessage ? formatRole(lastMessage.role) : '-';

  return (
    <button
      onClick={onClick}
      className={`graph-row w-full text-left transition-all duration-fast outline-none ${isSelected ? 'graph-row-selected bg-bg-tertiary' : ''
        }`}
      style={{
        display: 'flex',
        alignItems: 'center',
        height: ROW_HEIGHT,
        position: 'relative',
      }}
    >
      {/* Selection indicator */}
      {isSelected && (
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: 2,
            background: 'var(--color-border-accent)',
          }}
        />
      )}

      {/* Graph lane area */}
      <div
        style={{
          position: 'relative',
          width: svgWidth,
          flexShrink: 0,
          height: '100%',
          zIndex: 2,
        }}
      >
        <svg
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: svgWidth,
            height: ROW_HEIGHT,
            pointerEvents: 'none',
          }}
        >
          <circle
            cx={cx}
            cy={cy}
            r={NODE_R}
            fill={isSelected ? 'var(--color-border-accent)' : 'var(--color-bg-primary)'}
            stroke="var(--color-border-accent)"
            strokeWidth="2"
          />
        </svg>
      </div>

      {/* Request info */}
      <div
        className="flex-1 min-w-0"
        style={{
          display: 'flex',
          flexDirection: 'column',
          paddingLeft: 8,
          paddingRight: 12,
          gap: 2,
        }}
      >
        {/* Line 1: Summary */}
        <span className="text-text-secondary text-sm truncate">
          {summary}
        </span>
        {/* Line 2: Type, Model, Duration */}
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <span className="shrink-0">{messageType}</span>
          <span className="text-text-muted/50">|</span>
          <span className="truncate">{request.model}</span>
          <span
            className={`shrink-0 ml-auto ${request.duration_ms > 5000 ? 'text-warning' : ''
              }`}
          >
            {formatDuration(request.duration_ms)}
          </span>
        </div>
      </div>
    </button>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

interface RequestGraphProps {
  requests: Request[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  getMessage: (id: string) => Message | undefined;
}

export function RequestGraph({ requests, selectedId, onSelect, getMessage }: RequestGraphProps) {
  const tree = useMemo(() => buildRequestTree(requests), [requests]);
  const flat = useMemo(() => buildFlatNodes(tree), [tree]);
  const laneSpans = useMemo(() => buildLaneSpans(flat), [flat]);
  const maxCol = useMemo(() => Math.max(...flat.map((n) => n.column), 0), [flat]);
  const svgWidth = LEFT_PAD * 2 + (maxCol + 1) * COL_WIDTH;

  if (flat.length === 0) {
    return null;
  }

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <ConnectorLayer flat={flat} laneSpans={laneSpans} totalRows={flat.length} svgWidth={svgWidth} />
      {flat.map((node) => (
        <GraphRow
          key={node.id}
          node={node}
          svgWidth={svgWidth}
          isSelected={selectedId === node.id}
          onClick={() => onSelect(node.id)}
          getMessage={getMessage}
        />
      ))}
    </div>
  );
}

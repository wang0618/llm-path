import { useMemo, type ReactElement } from 'react';
import type { Request } from '../../types';
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
  parentId: string | null;
  isNewBranch: boolean;
}

// ─── Column Assignment (git-style) ────────────────────────────────────────────

function assignCols(
  node: RequestTreeNode,
  col: number,
  isNewBranch: boolean,
  counter: { value: number },
  parentId: string | null,
  out: FlatNode[],
): void {
  out.push({
    id: node.request.id,
    request: node.request,
    column: col,
    parentId,
    isNewBranch,
  });

  if (node.children.length > 0) {
    node.children.forEach((child, i) => {
      if (i === 0) {
        assignCols(child, col, false, counter, node.request.id, out);
      } else {
        const newCol = counter.value++;
        assignCols(child, newCol, true, counter, node.request.id, out);
      }
    });
  }
}

function buildFlatNodes(roots: RequestTreeNode[]): FlatNode[] {
  const out: FlatNode[] = [];
  const counter = { value: 1 };
  roots.forEach((root, i) => {
    const col = i === 0 ? 0 : counter.value++;
    assignCols(root, col, i > 0, counter, null, out);
  });
  // Sort by timestamp for strict chronological order
  out.sort((a, b) => a.request.timestamp - b.request.timestamp);
  return out;
}

// ─── Lane Spans ───────────────────────────────────────────────────────────────

interface LaneSpan {
  openY: number;
  endY: number;
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
    const span = spans.get(node.column);
    const nodeY = rowY(rowIdx);
    const endY = span ? Math.max(span.endY, nodeY) : nodeY;

    let openY: number;
    if (node.isNewBranch && node.parentId !== null) {
      const parentRowIdx = rowById.get(node.parentId) ?? rowIdx;
      const parentNode = flat[parentRowIdx];
      const dx = Math.abs(colX(node.column) - colX(parentNode.column));
      openY = rowY(parentRowIdx) + curveHeight(dx);
    } else {
      openY = span ? Math.min(span.openY, nodeY) : nodeY;
    }

    spans.set(node.column, { openY, endY });
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
  laneSpans.forEach((span, col) => {
    const x = colX(col);
    if (span.endY > span.openY) {
      elems.push(
        <line
          key={`lane-${col}`}
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
  flat.forEach((node) => {
    if (!node.isNewBranch || !node.parentId) return;
    const parentRow = rowById.get(node.parentId);
    if (parentRow === undefined) return;

    const parentNode = flat[parentRow];
    const px = colX(parentNode.column);
    const py = rowY(parentRow);
    const cx = colX(node.column);
    const dx = Math.abs(cx - px);
    const curveH = curveHeight(dx);
    const endY = py + curveH;
    const midY = py + curveH / 2;
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

function formatTime(timestamp: number): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// ─── Single Row ───────────────────────────────────────────────────────────────

interface GraphRowProps {
  node: FlatNode;
  svgWidth: number;
  isSelected: boolean;
  onClick: () => void;
}

function GraphRow({ node, svgWidth, isSelected, onClick }: GraphRowProps) {
  const cx = colX(node.column);
  const cy = ROW_HEIGHT / 2;
  const { request } = node;

  return (
    <button
      onClick={onClick}
      className={`graph-row w-full text-left transition-all duration-fast ${
        isSelected ? 'graph-row-selected bg-bg-tertiary' : ''
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
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          paddingLeft: 8,
          paddingRight: 12,
          minWidth: 0,
          gap: 2,
        }}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-text-secondary text-sm font-mono truncate">
            {formatTime(request.timestamp)}
          </span>
          <span
            className={`text-xs font-mono px-1.5 py-0.5 rounded shrink-0 ${
              request.duration_ms > 5000
                ? 'bg-warning/20 text-warning'
                : 'bg-bg-primary text-text-muted'
            }`}
          >
            {formatDuration(request.duration_ms)}
          </span>
        </div>
        <span className="text-xs text-text-muted truncate">{request.model}</span>
      </div>
    </button>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

interface RequestGraphProps {
  requests: Request[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function RequestGraph({ requests, selectedId, onSelect }: RequestGraphProps) {
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
        />
      ))}
    </div>
  );
}

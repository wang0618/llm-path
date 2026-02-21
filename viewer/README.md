# LLM Path Viewer

React + TypeScript + Vite frontend for visualizing LLM request traces.

## Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint
```

## URL Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `data` | Path to the data file to load (relative to public directory or full URL). Defaults to `data.json` | `?data=traces/my-trace.json` |
| `local` | Load a file from the local filesystem (via dev server's `/_local` endpoint). When specified, `data` parameter is ignored | `?local=/path/to/trace.json` |

### Examples

```
# Load default data file (public/data.json)
http://localhost:5173/

# Load another file from public directory
http://localhost:5173/?data=other-trace.json

# Load a file from local filesystem
http://localhost:5173/?local=/Users/me/traces/debug.json
```

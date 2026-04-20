# File Explorer Component

## Multi-Root Architecture

The file explorer supports multiple roots, similar to VS Code's multi-root workspaces. Roots are added via CLI and browsed in the UI.

```
┌─────────────────────────────────────┐
│ EXPLORER                    [+ ···] │
├─────────────────────────────────────┤
│ ▼ meridian-cli                      │
│   ▼ src                             │
│     ▼ meridian                      │
│       ▶ lib                         │
│       ▶ spawn                       │
│         __init__.py                 │
│   ▶ frontend                        │
│   ▶ tests                           │
│ ▼ another-project                   │
│   ▶ src                             │
│   ▶ docs                            │
└─────────────────────────────────────┘
```

## Root Management

### Adding Roots

Roots are added via CLI:

```bash
meridian app root add /path/to/project
meridian app root add .  # Current directory
```

This registers the root with the app server. The server maintains a list of roots in `~/.meridian/app/roots.jsonl`.

### Root Registry

```json
{"path": "/home/user/meridian-cli", "added_at": "2026-04-19T10:00:00Z"}
{"path": "/home/user/another-project", "added_at": "2026-04-19T10:05:00Z"}
```

The explorer reads from this registry on load and watches for changes.

### Removing Roots

```bash
meridian app root remove /path/to/project
meridian app root remove --all
```

Or via UI context menu on the root node.

## API Endpoints

### List Roots

`GET /api/explorer/roots`

```json
{
  "roots": [
    {
      "path": "/home/user/meridian-cli",
      "name": "meridian-cli",
      "added_at": "2026-04-19T10:00:00Z"
    }
  ]
}
```

### List Directory

`GET /api/explorer/list?path=/home/user/meridian-cli/src`

```json
{
  "path": "/home/user/meridian-cli/src",
  "entries": [
    {"name": "meridian", "type": "directory"},
    {"name": "__init__.py", "type": "file", "size": 0},
    {"name": "cli.py", "type": "file", "size": 4523}
  ]
}
```

Entries are sorted: directories first (alphabetical), then files (alphabetical).

### Read File

`GET /api/explorer/read?path=/home/user/meridian-cli/src/cli.py`

```json
{
  "path": "/home/user/meridian-cli/src/cli.py",
  "content": "...",
  "encoding": "utf-8",
  "size": 4523
}
```

For large files (> 100KB), content is truncated with a `truncated: true` flag.

### Add Root (from UI)

`POST /api/explorer/roots`

```json
{"path": "/home/user/new-project"}
```

### Remove Root

`DELETE /api/explorer/roots?path=/home/user/old-project`

## Component Structure

```
FileExplorer/
├── FileExplorer.tsx      ← Main container
├── RootNode.tsx          ← Top-level project root
├── TreeNode.tsx          ← Directory or file node
├── FileIcon.tsx          ← Icon based on file type
├── ExplorerHeader.tsx    ← Title bar with actions
└── hooks/
    ├── useExplorerRoots.ts
    ├── useDirectoryListing.ts
    └── useFilePreview.ts
```

### FileExplorer.tsx

```tsx
interface FileExplorerProps {
  onFileSelect?: (path: string) => void
  onFileOpen?: (path: string) => void
}

function FileExplorer({ onFileSelect, onFileOpen }: FileExplorerProps) {
  const { roots, addRoot, removeRoot } = useExplorerRoots()
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set())
  const [selectedPath, setSelectedPath] = useState<string | null>(null)

  return (
    <div className="flex flex-col h-full">
      <ExplorerHeader onAddRoot={handleAddRoot} />
      <ScrollArea className="flex-1">
        {roots.map(root => (
          <RootNode
            key={root.path}
            root={root}
            expanded={expandedPaths}
            selected={selectedPath}
            onToggle={handleToggle}
            onSelect={handleSelect}
            onOpen={onFileOpen}
            onRemove={() => removeRoot(root.path)}
          />
        ))}
      </ScrollArea>
    </div>
  )
}
```

### TreeNode.tsx

```tsx
interface TreeNodeProps {
  entry: DirectoryEntry
  depth: number
  expanded: boolean
  selected: boolean
  onToggle: () => void
  onSelect: () => void
  onOpen?: () => void
}

function TreeNode({ entry, depth, expanded, selected, onToggle, onSelect, onOpen }: TreeNodeProps) {
  const isDirectory = entry.type === 'directory'
  
  return (
    <div
      className={cn(
        "flex items-center h-6 px-2 cursor-pointer hover:bg-bg-2",
        selected && "bg-bg-3"
      )}
      style={{ paddingLeft: depth * 12 + 8 }}
      onClick={isDirectory ? onToggle : onSelect}
      onDoubleClick={!isDirectory ? onOpen : undefined}
    >
      {isDirectory ? (
        <ChevronIcon className={cn("w-4 h-4", expanded && "rotate-90")} />
      ) : (
        <span className="w-4" />
      )}
      <FileIcon type={entry.type} name={entry.name} />
      <span className="ml-1 truncate text-sm">{entry.name}</span>
    </div>
  )
}
```

## Interactions

### Navigation

| Action | Behavior |
|--------|----------|
| Click directory | Toggle expand/collapse |
| Click file | Select file |
| Double-click file | Open file (preview or attach to session) |
| Arrow keys | Navigate tree |
| Enter | Open selected file |
| Space | Toggle directory |

### Context Menu

Right-click on any node:

| Entry Type | Actions |
|------------|---------|
| Root | Remove root, Collapse all, Refresh |
| Directory | New file, New folder, Copy path, Collapse |
| File | Open, Copy path, Attach to session |

### Drag and Drop (Future)

- Reorder roots
- Drag file to composer to attach

## File Icons

Icon mapping by extension and special names:

| Pattern | Icon |
|---------|------|
| `*.py` | Python |
| `*.ts`, `*.tsx` | TypeScript |
| `*.js`, `*.jsx` | JavaScript |
| `*.md` | Markdown |
| `*.json` | JSON |
| `*.toml`, `*.yaml` | Config |
| `Dockerfile` | Docker |
| `.gitignore` | Git |
| Directory | Folder |
| Default | File |

Use Lucide icons for consistency.

## Integration with Sessions

### Attach to Composer

Files can be attached to the composer for reference:

```
┌─────────────────────────────────────────────────────────────────┐
│ [📎 src/auth.py] [📎 tests/test_auth.py]                        │
│                                                                 │
│ Review the auth implementation and ensure...                    │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ [Quick ○ ● Thorough]                   [Advanced ▾]    [Send]   │
└─────────────────────────────────────────────────────────────────┘
```

Attachments are sent as file references in the session creation request.

### Open in Session Context

When viewing a session, the explorer can:
- Show files modified by the session (from tool calls)
- Highlight files mentioned in the thread

## State Management

### Expansion State

Expansion state is stored in localStorage keyed by root path:

```typescript
interface ExplorerState {
  expandedPaths: string[]
  selectedPath: string | null
}

const storageKey = `explorer:${rootPath}`
```

### Lazy Loading

Directories are loaded on expand, not upfront. Large directories (> 500 entries) show a "Load more" button.

### Refresh

- Manual refresh via header button or context menu
- Auto-refresh on window focus (debounced)
- WebSocket file watch events (future)

## Security Considerations

### Path Validation

All paths must:
1. Be absolute paths
2. Fall under a registered root
3. Not contain `..` traversal after normalization

The server validates paths before any file operations.

### Symlink Handling

Symlinks are followed but display with a special indicator. Links pointing outside registered roots return an error.

### Binary Files

Binary files show metadata only, no content preview:

```json
{
  "path": "/home/user/project/image.png",
  "binary": true,
  "size": 123456,
  "mime_type": "image/png"
}
```

## Panel Behavior

The explorer appears as a collapsible side panel:

```
┌────────┬─────────────────────────────────────────────────────────────┐
│ [🏠]   │ ┌──────────────────────┬──────────────────────────────────┐ │
│ [📁]●  │ │ EXPLORER             │ Main Content                     │ │
│ [⚡]   │ │                      │                                  │ │
│        │ │ ▼ meridian-cli       │                                  │ │
│        │ │   ▼ src              │                                  │ │
│        │ │     ...              │                                  │ │
│        │ │                      │                                  │ │
│        │ └──────────────────────┴──────────────────────────────────┘ │
└────────┴─────────────────────────────────────────────────────────────┘
```

- Toggle via activity bar icon
- Resizable width (min 200px, max 400px)
- Remembers width in localStorage

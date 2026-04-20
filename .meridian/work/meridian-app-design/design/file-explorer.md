# File Explorer Component

## Single-Root Architecture

The file explorer is rooted at exactly one project directory: the directory where `meridian app` was started.
This is the Jupyter model: one server, one root, all paths relative to that root.

```
┌─────────────────────────────────────┐
│ EXPLORER                        ··· │
├─────────────────────────────────────┤
│ ▼ meridian-cli (project root)       │
│   ▼ src                             │
│     ▼ meridian                      │
│       ▶ lib                         │
│       ▶ spawn                       │
│         __init__.py                 │
│   ▶ frontend                        │
│   ▶ tests                           │
└─────────────────────────────────────┘
```

## Root Model (No Add/Remove)

- There is no root registry.
- There are no additive roots.
- There is no UI or CLI action for adding/removing roots.
- If you want a different root, start `meridian app` in a different directory.

## API Endpoints

### Get Project Root

`GET /api/files/root`

```json
{
  "project_root": "/home/user/meridian-cli",
  "name": "meridian-cli"
}
```

### List Directory

`GET /api/files/tree?path=src`

`path` is optional and project-root-relative. Empty path means root listing.

```json
{
  "path": "src",
  "entries": [
    {"name": "meridian", "type": "directory"},
    {"name": "__init__.py", "type": "file", "size": 0},
    {"name": "cli.py", "type": "file", "size": 4523}
  ]
}
```

Entries are sorted: directories first (alphabetical), then files (alphabetical).

### Read File

`GET /api/files/read?path=src/cli.py`

```json
{
  "path": "src/cli.py",
  "content": "...",
  "encoding": "utf-8",
  "size": 4523
}
```

For large files (> 100KB), content is truncated with a `truncated: true` flag.

## Component Structure

```
FileExplorer/
├── FileExplorer.tsx      ← Main container
├── ProjectRootNode.tsx   ← Fixed top-level root node
├── TreeNode.tsx          ← Directory or file node
├── FileIcon.tsx          ← Icon based on file type
├── ExplorerHeader.tsx    ← Title bar with root + actions
└── hooks/
    ├── useProjectRoot.ts
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
  const { projectRoot } = useProjectRoot()
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set([""]))
  const [selectedPath, setSelectedPath] = useState<string | null>(null)

  return (
    <div className="flex flex-col h-full">
      <ExplorerHeader projectRoot={projectRoot} />
      <ScrollArea className="flex-1">
        <ProjectRootNode
          rootPath=""
          rootName={projectRoot.name}
          expanded={expandedPaths}
          selected={selectedPath}
          onToggle={handleToggle}
          onSelect={handleSelect}
          onOpen={onFileOpen}
        />
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
| Project root | Refresh, Collapse all |
| Directory | New file, New folder, Copy path, Collapse |
| File | Open, Copy path, Attach to session |

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

### Session Context Signals

When viewing a session, the explorer can:
- Show files modified by the session (from tool calls)
- Highlight files mentioned in the thread

## State Management

### Expansion State

Expansion state is stored in localStorage keyed by project root path:

```typescript
interface ExplorerState {
  expandedPaths: string[]
  selectedPath: string | null
}

const storageKey = `explorer:${projectRootPath}`
```

### Lazy Loading

Directories are loaded on expand, not upfront. Large directories (> 500 entries) show a "Load more" button.

### Refresh

- Manual refresh via header button or context menu
- Auto-refresh on window focus (debounced)
- File watch push events (future)

## Security Considerations

### Path Validation

All paths must:
1. Be project-root-relative
2. Resolve under the bound project root after normalization
3. Not contain traversal that escapes root

The server validates paths before any file operations.

### Symlink Handling

Symlinks are followed but display with a special indicator. Links pointing outside the bound project root return an error.

### Binary Files

Binary files show metadata only, no content preview:

```json
{
  "path": "assets/image.png",
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

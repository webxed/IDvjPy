# IDvjPy_term - Compact Summary

## Project
Terminal TUI app (Textual framework) for running shell commands with tagged history in SQLite.

## Key Features Implemented

### Tab-Completion System
- Dropdown list with arrow key navigation
- Prefix-based suggestions from database
- Path-aware file/directory suggestions from current working directory
- Includes hidden entries (`.*`) and marks directories with `/`
- Enter inserts command, doesn't execute

### Output Formatting
- Removed CompletedProcess wrapper
- Stderr shown at bottom with red highlight
- Exit code shown only when != 0

### Collapsible Command Blocks
- Space toggles collapse
- Left/Right arrows for navigation
- Mouse click focuses without collapsing

### Kubernetes Ingress Analyzer (`:i`)
- `:i list [-n NAMESPACE]` - List ingresses
- `:i analyze INGRESS_NAME [-n NS]` - Analyze ingress
- `:i ns [NAMESPACE]` - Namespace info in JSON viewer
- Uses crossplane for nginx config parsing
- Shows paths, upstreams, service endpoints

### Help System
- `:?` - Main help with all commands
- Per-command help: `:h`, `:i`, etc.

### Variable Substitution
- `$VAR` pattern in arguments
- Uses vars from `$ VAR=val` command
- Example: `:i list -n $NS`
- JSON Viewer sets `$JSON` on node selection (`Enter`)

### JSON Viewer Improvements
- Full tree expansion on open
- Live text filtering by key/value/jq path
- Next/prev match navigation (`F6`/`Shift+F6`, `n`/`N`)
- Search focus shortcuts (`/`, `Ctrl+F`)
- `Enter` copies jq path and sets `$JSON`

### Performance Optimizations
- Pre-compiled regex patterns at module level
- MAX_DISPLAY_LINES = 50 (truncation)
- Lazy loading for JSON viewer
- F5 copies full output to clipboard

### UI Fixes
- Auto-focus input on keypress
- Mouse scroll on results container
- Less bright selection highlight
- Stable clipboard paste in input (`Shift+Insert`, `Ctrl+V`)

## Files
| File | Purpose |
|------|---------|
| app.py | Main TUI application |
| database.py | SQLite operations |
| ingress_analyzer.py | K8s ingress analysis |
| json_viewer.py | JSON tree viewer modal |
| app.css | Textual styling |
| settings.yml | Configuration |

## Commands
| Prefix | Action |
|--------|--------|
| (none) | Execute shell command |
| `#` | Save to database with tag |
| `?` | Query database |
| `! N` | Execute by ID |
| `:` | App commands (`:q`, `:h`) |
| `:i` | Ingress analyzer |
| `:?` | Main help |
| `|` | Pipe from focused block |
| `$` | Set env variable |

## Session Stats
- 28+ commits
- Version: v1.1.18+
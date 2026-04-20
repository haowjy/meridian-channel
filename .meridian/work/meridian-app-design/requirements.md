# Meridian App — Requirements

## Functional Requirements

### Navigation & Information Architecture
- [ ] Three-mode workspace navigation: Sessions / Chat / Files
- [ ] Work-item-centric organization as the primary structure
- [ ] Dedicated "Quick" section for unattached sessions

### Session Management
- [ ] Create new sessions with harness/model/effort selection
- [ ] List sessions grouped by work item
- [ ] View active session with real-time streaming
- [ ] View completed session metadata
- [ ] Cancel active session

### Mid-Session Controls
- [ ] Model switching (where harness supports)
- [ ] Compact/summarize context
- [ ] Interrupt current turn
- [ ] Skill activation (where harness supports)

### Configuration
- [ ] Default harness/model from user config
- [ ] Effort toggle (Quick/Thorough)
- [ ] Advanced settings for power users

### Mobile & Responsive Behavior
- [ ] Mobile monitoring and light intervention support for v1
- [ ] Mobile supports session monitoring, dashboard glance, and quick chat replies
- [ ] Desktop interactions remain the full-authoring experience

### Server
- [ ] One server per project (`meridian app` serves the current project only)
- [ ] Session persistence across restarts
- [ ] No project keys or multi-repo routing within a single server process

## Non-Functional Requirements

- Simple by default
- Desktop-first, with mobile monitoring supported
- Local-only for MVP (remote access in Phase 3)
- Fast startup, minimal dependencies

### Access Modes
- [ ] Local mode: localhost-only, no auth, chromeless window
- [ ] LAN mode: bind 0.0.0.0, token auth required
- [ ] Tunnel mode: cloudflare tunnel, token auth, HTTPS
- [ ] Token management: generate, persist, reset

### Desktop Experience
- [ ] Open in Chrome/Edge app mode (chromeless)
- [ ] Fallback to default browser if Chrome unavailable
- [ ] Frontend bundled in Python package (no Node at runtime)

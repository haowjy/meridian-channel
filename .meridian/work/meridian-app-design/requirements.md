# Meridian App — Requirements

## Functional Requirements

### Session Management
- [ ] Create new sessions with harness/model/effort selection
- [ ] List sessions grouped by recency
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

### Server
- [ ] One server per machine
- [ ] Session persistence across restarts
- [ ] Multi-repo support via project keys

## Non-Functional Requirements

- Simple by default
- Desktop-first (mobile is out of scope)
- Local-only for MVP (remote access in Phase 3)
- Fast startup, minimal dependencies

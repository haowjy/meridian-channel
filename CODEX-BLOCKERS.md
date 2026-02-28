# Codex & OpenCode Feature Blockers

**Status:** Active (Living Document)

**Last Updated:** 2025-02-28

**Purpose:** Track Codex and OpenCode feature gaps that block full meridian-channel support, with workarounds and links to upstream issues.

This document is maintained across conversations to avoid blocking meridian-channel development on external tooling. Each blocker includes:
- Current status
- Impact on meridian-channel
- Known workarounds
- Upstream issue links
- Timeline estimates

---

## 1. Codex Feature Blockers

### 1.1 System Prompt Customization

| Field | Value |
|-------|-------|
| **Status** | ❌ Not implemented |
| **Blocker** | No `--system-prompt` or `--append-system-prompt` flags |
| **GitHub Issue** | [sst/opencode - Feature request (check for existing)](https://github.com/sst/opencode/issues) |
| **Meridian Impact** | Can't customize system prompts for Codex agents; limits agent personality/behavior |
| **Severity** | Medium (workaround exists) |
| **Timeline** | TBD |

**Current Workaround:**
- Use prompt injection: embed system context in the initial conversation message
- Add to `initial_context` field in agent profile
- Limitation: Can't modify system prompt mid-conversation, only prepend context

**Example Workaround:**
```yaml
# In .meridian/<space-id>/agents/reviewer.md
---
name: reviewer
harness: codex
initial_context: |
  You are a code reviewer. Be critical but constructive.
  Focus on: readability, performance, security.
---
```

**When to Revisit:**
- [ ] If Codex implements native `--system-prompt` flag
- [ ] If community requests this feature
- [ ] Next check: Q2 2025

---

### 1.2 Agent Profiles / Agent Selection

| Field | Value |
|-------|-------|
| **Status** | ❌ Not implemented |
| **Blocker** | No `--agent` flag to select agent profiles at launch |
| **GitHub Issue** | [sst/opencode - Agent selection feature](https://github.com/sst/opencode/issues) |
| **Meridian Impact** | Can't programmatically select which agent profile to use |
| **Severity** | High (blocks agent coordination) |
| **Timeline** | TBD |

**Current Workaround:**
- Pass agent name via initial message/prompt
- Require user to manually select agent from menu (if available)
- Document which agent to use in space README

**Example Workaround:**
```bash
# Instead of: codex --agent reviewer
# Use prompt injection:
codex << 'EOF'
[Internal: Act as the 'reviewer' agent with these traits: ...]
Your task: review this code
EOF
```

**When to Revisit:**
- [ ] If Codex implements agent selection
- [ ] If Claude Code's agent selection becomes more portable
- [ ] Next check: Q2 2025

---

### 1.3 Skills Field in Agent Definitions

| Field | Value |
|-------|-------|
| **Status** | ❌ Not implemented |
| **Blocker** | Agent profiles don't support `skills:` field (like Claude Code) |
| **GitHub Issue** | [sst/opencode#8846 - Skills field feature request](https://github.com/sst/opencode/issues/8846) |
| **Meridian Impact** | Can't declare which skills agent has; breaks introspection |
| **Severity** | Medium (partial workaround via permissions) |
| **Timeline** | TBD (open feature request) |

**Current Workaround:**
- Use permission-based skill access (Codex's alternative model)
- Document skills in agent profile's `description` field
- Let Codex prompt the model to offer available skills

**Example Workaround:**
```yaml
# In .meridian/<space-id>/agents/researcher.md
---
name: researcher
harness: codex
description: |
  ## Available Skills
  - websearch: Search the web for information
  - file-analysis: Analyze document structure
  - code-review: Review code for issues
---
```

**Note:** This is less discoverable than a native `skills:` field, but functional.

**Contribution Opportunity:**
- Codex team indicated openness to this feature (issue #8846)
- Could be a good PR for community contribution
- Pattern already exists in Claude Code, so precedent is clear

**When to Revisit:**
- [ ] If Codex implements `skills:` field
- [ ] If community PRs this feature
- [ ] Next check: Q1 2025 (active discussion on issue)

---

### 1.4 Hooks / Event System

| Field | Value |
|-------|-------|
| **Status** | ⚠️ Partial (basic hooks may exist) |
| **Blocker** | Limited hook support compared to Claude Code |
| **GitHub Issue** | [sst/opencode - Hooks/lifecycle events](https://github.com/sst/opencode/issues) |
| **Meridian Impact** | Can't reliably inject content at conversation start or handle lifecycle events |
| **Severity** | Low (limited impact on current features) |
| **Timeline** | TBD |

**Current Status:**
- Codex may have basic plugin hooks
- Unclear if full lifecycle hooks are supported
- Need to test with actual Codex harness

**Current Workaround:**
- Use prompt injection for content at start
- Manually manage session state via CLI commands
- Document manual steps in space README

**When to Revisit:**
- [ ] Test with actual Codex harness
- [ ] Document findings in "Cursor Feature Gaps" section
- [ ] Next check: When Codex harness is available

---

## 2. OpenCode Feature Blockers

### 2.1 System Prompt Customization

| Field | Value |
|-------|-------|
| **Status** | ⚠️ Partial (hook-based workaround works!) |
| **Blocker** | No `--system-prompt` flag; config-only approach |
| **GitHub Issue** | [anomalyco/opencode#6142 - System prompt feature](https://github.com/anomalyco/opencode/issues/6142) |
| **Meridian Impact** | Can't easily pass system prompts via CLI, but plugin workaround is stable |
| **Severity** | Low (workaround is reliable) |
| **Timeline** | TBD |

**Current Workaround (STABLE):**
- Use OpenCode plugin with `experimental.chat.system.transform` hook
- Plugin injects system prompt at conversation start
- This approach is **reliable and battle-tested**
- Lives in: `meridian-channel/hooks/opencode-system-prompt.ts`

**Example Workaround:**
```typescript
// In OpenCode plugin
hook('experimental.chat.system.transform', (system) => {
  return `${system}\n\n[Meridian Context]\n${injectedContext}`;
});
```

**Status:** ✅ This workaround is stable. Not blocking.

**When to Revisit:**
- [ ] If native flag becomes available, consider switching
- [ ] Keep plugin workaround as fallback
- [ ] Next check: Q2 2025 (low priority)

---

### 2.2 Append System Prompt

| Field | Value |
|-------|-------|
| **Status** | ❌ Not implemented |
| **Blocker** | No `--append-system-prompt` equivalent |
| **GitHub Issue** | [Same as 2.1 - Part of broader system prompt feature](https://github.com/anomalyco/opencode/issues/6142) |
| **Meridian Impact** | Can't add to existing system prompt without overwriting |
| **Severity** | Low (can prepend instead) |
| **Timeline** | TBD |

**Current Workaround:**
- Include agent context in initial system prompt (done once)
- Use plugin hook to inject context (same as 2.1)
- Limitation: Can't dynamically append per-conversation

**When to Revisit:**
- [ ] If native flag becomes available
- [ ] Currently not blocking (prepend strategy works)
- [ ] Next check: Q2 2025

---

### 2.3 Agent Profiles / Skills Field

| Field | Value |
|-------|-------|
| **Status** | ❌ Not implemented |
| **Blocker** | Agent profiles don't support `skills:` field |
| **GitHub Issue** | [anomalyco/opencode#8846 - Skills field feature](https://github.com/anomalyco/opencode/issues/8846) |
| **Meridian Impact** | Can't declare skills in profile; reduces discoverability |
| **Severity** | Medium (workaround via permissions exists) |
| **Timeline** | TBD (open feature request) |

**Current Workaround:**
- Use OpenCode's permission-based skill access model
- Document skills in agent profile description
- Rely on model to infer available tools/skills

**Example:**
```yaml
# In .meridian/<space-id>/agents/researcher.md
---
name: researcher
harness: opencode
permissions:
  skills: "ask"  # Ask before using skills
description: |
  Available skills: websearch, analysis, file-read
---
```

**Contribution Opportunity:**
- OpenCode team receptive to PRs for this feature (issue #8846)
- Pattern well-established in Claude Code
- Could be a good starter PR for contributors
- **Potential impact**: Low risk, high community value

**When to Revisit:**
- [ ] Check issue #8846 for progress
- [ ] Consider submitting PR if not implemented by Q2 2025
- [ ] Next check: Q1 2025 (community contribution potential)

---

### 2.4 Hooks / Event System

| Field | Value |
|-------|-------|
| **Status** | ⚠️ Partial (basic hooks implemented) |
| **Blocker** | Limited scope compared to Claude Code |
| **GitHub Issue** | [anomalyco/opencode - Hooks enhancement](https://github.com/anomalyco/opencode/issues) |
| **Meridian Impact** | Can use `experimental.chat.system.transform` for system prompt injection |
| **Severity** | Low (current hook is sufficient) |
| **Timeline** | TBD |

**Current Status:**
- `experimental.chat.system.transform` hook works well
- No need for additional hooks currently
- Plugin system is stable for our use case

**When to Revisit:**
- [ ] If we need lifecycle hooks (session start/end), revisit
- [ ] Currently not blocking
- [ ] Next check: Q2 2025 (when more complex multi-agent patterns emerge)

---

## 3. Cursor Feature Gaps

| Feature | Status | Last Tested | Notes |
|---------|--------|-------------|-------|
| System prompt support | ❓ Unknown | Never | Need to test |
| Agent profiles | ❓ Unknown | Never | Need to test |
| Skills field | ❓ Unknown | Never | Need to test |
| Hooks/events | ❓ Unknown | Never | Need to test |

**Status:** Need to evaluate when Cursor harness becomes available.

**Test Plan:**
1. Create simple Cursor harness adapter
2. Test each feature listed above
3. Document findings in this section
4. File issues with Cursor team if gaps found
5. Plan integration based on results

**Next Step:** TBD (awaiting Cursor harness availability)

---

## 4. Workarounds & Mitigation Matrix

Summary of all blockers and their mitigations:

| Blocker | Harness | Current Workaround | User Impact | Complexity | Status |
|---------|---------|-------------------|-----------|-----------|--------|
| System prompt | Codex | Prompt injection | Moderate (manual) | Low | ✅ Viable |
| System prompt | OpenCode | Plugin hook | Low (automatic) | Medium | ✅ Stable |
| Agent profiles | Codex | Pass via prompt | Moderate | Low | ⚠️ Limited |
| Agent profiles | OpenCode | Pass via prompt | Moderate | Low | ⚠️ Limited |
| Skills field | Codex | Document in description | Moderate | Low | ⚠️ Degraded UX |
| Skills field | OpenCode | Permissions model | Low | Low | ✅ Acceptable |
| Hooks/events | All | Manual state management | Low | Medium | ⚠️ Workaround |

**Legend:**
- ✅ Viable: Workaround is acceptable, not blocking
- ⚠️ Limited: Workaround has limitations, acceptable for MVP
- ❌ Blocking: No workaround, must implement upstream feature

---

## 5. Feature Request Templates

Use these templates when filing issues with Codex/OpenCode teams:

### Template: System Prompt Customization

```markdown
### Feature Request: System Prompt Customization

**Harness:** [Codex/OpenCode]

**Title:** Add `--system-prompt` and `--append-system-prompt` CLI flags

**Use Case:**
- Allow agents to be launched with custom system context
- Enable persistent system prompts across conversations
- Support multi-agent collaboration with shared instructions

**Example Usage:**
```bash
# Custom system prompt
opencode --system-prompt "You are a code reviewer" --agent reviewer

# Append to existing
opencode --append-system-prompt "Follow the Meridian coding standards"
```

**Precedent:**
- Claude Code supports `--system-prompt` natively
- Improves developer experience significantly
- Essential for agent coordination systems

**Impact:**
- Enables meridian-channel system prompt injection natively
- Removes need for prompt injection workarounds
- Allows per-agent customization at launch time
```

---

### Template: Skills Field in Agent Profiles

```markdown
### Feature Request: Skills Field in Agent Profiles

**Harness:** [Codex/OpenCode]

**Title:** Add `skills:` field to agent profile YAML

**Use Case:**
- Declare which skills an agent has (analogous to Claude Code)
- Enable skill discovery and introspection
- Support multi-agent systems with heterogeneous agents
- Allow agents to advertise their capabilities

**Example Usage:**
```yaml
---
name: researcher
harness: opencode
skills:
  - websearch
  - file-analysis
  - code-review
---
```

**Precedent:**
- Claude Code's agent profiles support this natively
- Consistent with agent definition standards
- Low implementation complexity

**Impact:**
- Enables full agent introspection in meridian-channel
- Replaces need for documentation-based skill lists
- Allows programmatic skill selection

**Implementation Note:**
- Could be part of YAML schema validation
- Doesn't require runtime changes if not used by CLI
- Could inform UI/UX for skill selection
```

---

### Template: Lifecycle Hooks

```markdown
### Feature Request: Lifecycle Hooks / Event System

**Harness:** [Codex/OpenCode]

**Title:** Add lifecycle hooks for session events

**Use Case:**
- Track when agent session starts
- Log when agent completes
- Handle errors with consistent messages
- Inject content at specific lifecycle points

**Example Hooks:**
```
on_session_start()    # Called when session begins
on_agent_spawn()      # Called when agent process starts
on_output()           # Called when output received
on_error()            # Called on error
on_session_end()      # Called when session closes
```

**Precedent:**
- CLI tools commonly support hooks (git, npm, etc.)
- Essential for complex workflows

**Impact:**
- Enables session tracking in meridian-channel
- Allows reliable state management
- Reduces need for polling/workarounds
```

---

## 6. Progress Tracking

### Codex

| Feature | Last Checked | Status | Notes |
|---------|-------------|--------|-------|
| System prompt flags | N/A | ❌ Not implemented | Need to check current status |
| Agent profiles | N/A | ❌ Not implemented | Prompt injection workaround in use |
| Skills field | N/A | ❌ Not implemented | Using description field instead |
| Hooks/events | N/A | ⚠️ Unknown | Need to test when harness available |

**Next Actions:**
- [ ] Verify current Codex API capabilities
- [ ] Test hooks when harness integration begins
- [ ] File feature requests if still missing

---

### OpenCode

| Feature | Last Checked | Status | Notes |
|---------|-------------|--------|-------|
| System prompt hooks | 2025-02-28 | ✅ Working | Plugin hook stable, not blocking |
| Agent profiles | 2025-02-28 | ❌ Not implemented | Pass agent name via prompt |
| Skills field | 2025-02-28 | ❌ Not implemented | Issue #8846 open, contrib opportunity |
| Hooks/events | 2025-02-28 | ⚠️ Partial | System prompt hook works, other hooks TBD |

**Next Actions:**
- [ ] Monitor issue #8846 for skills field implementation
- [ ] Consider submitting PR for skills field by Q2 2025
- [ ] Test additional hooks as needed

---

### Cursor

| Feature | Last Checked | Status | Notes |
|---------|-------------|--------|-------|
| System prompt support | Never | ❓ Unknown | Awaiting harness availability |
| Agent profiles | Never | ❓ Unknown | Awaiting harness availability |
| Skills field | Never | ❓ Unknown | Awaiting harness availability |
| Hooks/events | Never | ❓ Unknown | Awaiting harness availability |

**Next Actions:**
- [ ] Create Cursor harness adapter when available
- [ ] Run evaluation test plan
- [ ] Document findings
- [ ] File issues with Cursor team if needed

---

## 7. Decision Matrix: When to Unblock

Use this matrix to decide when to revisit each blocker:

### Codex System Prompt

**Decision:**
- [ ] **IF** native `--system-prompt` flag implemented
  - **THEN** Update Codex adapter in meridian-channel
  - **Action** Update `src/meridian/lib/harness/codex.py`

- [ ] **IF** never implemented by end of 2025
  - **THEN** Keep prompt injection workaround as permanent solution
  - **Action** Mark as "stable workaround" in docs

- [ ] **IF** community demand is low
  - **THEN** Keep current approach (low priority)
  - **Check** Again in Q4 2025

---

### OpenCode Skills Field

**Decision:**
- [ ] **IF** implemented upstream (check issue #8846)
  - **THEN** Update agent profile loader in meridian-channel
  - **Action** Update `src/meridian/lib/agent/loader.py`

- [ ] **IF** community PR submitted
  - **THEN** Review and potentially contribute tests
  - **Check** GitHub weekly

- [ ] **IF** not implemented by end of Q2 2025
  - **THEN** Consider submitting PR ourselves
  - **Effort** Low (pattern well-understood)

- [ ] **IF** never implemented
  - **THEN** Keep permission-based model as standard
  - **Action** Document in agent profile guidelines

---

### Cursor Integration

**Decision:**
- [ ] **IF** Cursor harness becomes available
  - **THEN** Run full evaluation test plan (see section 3)
  - **Timeline** 1-2 weeks

- [ ] **IF** gaps found
  - **THEN** File issues with Cursor team
  - **Action** Create GitHub issues with templates

- [ ] **IF** multiple blockers found
  - **THEN** Decide: wait for fixes vs. implement workarounds
  - **Decision** Based on severity + community demand

---

## 8. Contributing Back

If meridian-channel's workarounds or patterns inspire improvements to upstream projects, document and credit them:

### Process

1. **Identify Pattern:** Find a workaround that could be a native feature
2. **Validate:** Ensure it works well and has general utility
3. **Document:** Write up the pattern and rationale
4. **Credit:** Link to original Meridian issue/PR
5. **Propose:** Suggest to upstream team (issue or PR)
6. **Acknowledge:** Credit original authors when they implement it

### Examples (TBD)

If we discover a clever pattern for:
- System prompt reinjection (could inform OpenCode's native implementation)
- Agent selection without CLI flags (could inform Codex's design)
- Skill declaration without YAML field (could show OpenCode a path forward)

We should document and share with upstream teams.

---

## 9. Revision History

| Date | Author | Change | Status |
|------|--------|--------|--------|
| 2025-02-28 | Initial Creation | Created CODEX-BLOCKERS.md | ✅ Active |

---

## Related Documentation

- `_docs/meridian-channel/ARCHITECTURE.md` - Architecture that these blockers affect
- `_docs/meridian-channel/IMPLEMENTATION-GAPS.md` - Internal meridian-channel gaps (separate from harness gaps)
- `_docs/meridian-channel/IMPLEMENTATION-PLAN.md` - Implementation roadmap
- `src/meridian/lib/harness/*.py` - Harness adapters (Codex, OpenCode, Claude)

---

## Maintainer Notes

**How to Update This Document:**

1. **Found a new blocker?**
   - Add under appropriate harness section (1-3)
   - Include all fields from the template structure
   - Set status and severity
   - Add to Progress Tracking section

2. **Blocker resolved?**
   - Update Status to ✅ (e.g., "Implemented in vX.Y.Z")
   - Move to "Resolved Blockers" section (create if needed)
   - Update decision matrix if applicable
   - Bump "Last Updated" date at top

3. **Workaround found?**
   - Add to section 4 (Workarounds & Mitigation Matrix)
   - Link from the blocker description
   - Test before documenting

4. **Testing needed?**
   - Add test result to Progress Tracking
   - Note date and environment
   - Link to any PR/issues filed

**Review Cadence:**
- Check monthly for new upstream issues
- Re-evaluate resolved blockers quarterly
- Update decision matrix if timelines change
- Archive resolved blockers to maintain focus

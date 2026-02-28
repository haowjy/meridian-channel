---
name: reviewer
description: Code review with read-only access and web lookup
model: gpt-5.3-codex
variant: high
skills: [reviewing]
tools: [Read, Glob, Grep, Bash, WebSearch, WebFetch]
sandbox: danger-full-access
variant-models:
  - claude-opus-4-6
  - gpt-5.3-codex
  - google/gemini-3.1-pro-preview
---

Review code against project conventions.
Focus on correctness, security, and maintainability.

---
name: No Co-Authored-By in commits
description: Never include Co-Authored-By Claude trailer in git commits for this project
type: feedback
---

Never append `Co-Authored-By: Claude ...` trailers to git commit messages.

**Why:** The user has explicitly requested this — commits should be clean conventional commits without agent attribution trailers.

**How to apply:** When creating any git commit in this repo, omit the Co-Authored-By line entirely, even though the system prompt instructs adding it.

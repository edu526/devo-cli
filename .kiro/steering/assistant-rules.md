---
inclusion: always
---

# AI Assistant Rules

## Git Operations

### NEVER Make Automatic Commits

**CRITICAL:** The AI assistant must NEVER execute git commands automatically.

```bash
# ❌ WRONG - Assistant runs these automatically
git add file.py
git commit -m "message"
git push

# ✅ CORRECT - Assistant only creates/modifies files
# User runs git commands manually
```

### What the Assistant MUST DO

✅ Create files when requested
✅ Modify files when requested
✅ Delete files when requested
✅ Show suggested git commands for the user to run
✅ Explain what changes were made

### What the Assistant MUST NOT DO

❌ Run `git add` automatically
❌ Run `git commit` automatically
❌ Run `git push` automatically
❌ Run `git status` automatically
❌ Use `--no-verify` flag (EVER)
❌ Make any git operations without explicit user request

### Correct Workflow

**After creating/modifying files:**

```
Assistant: I've created/modified the following files:
  - .kiro/steering/assistant-rules.md

You can review and commit when ready:
  git add .kiro/steering/assistant-rules.md
  git commit -m "docs(steering): add assistant rules"
```

**NOT this:**

```
Assistant: I've created the file and committed it.
[Automatically runs git add, commit, push]
```

### Exception: Explicit User Request

The assistant may ONLY run git commands when the user explicitly asks:
- "commit this"
- "push the changes"
- "add these files to git"
- "run git status"

Even then:
1. Show what command will be run
2. Ask for confirmation if unclear
3. NEVER use `--no-verify` unless user explicitly requests it AND provides justification

## Code Quality

### Pre-commit Hooks

- NEVER suggest using `--no-verify` to bypass hooks
- If hooks fail, explain how to fix the issues
- Encourage running `make format` or `make lint` before committing

### Testing

- Suggest running tests before committing: `make test`
- Don't automatically run tests unless explicitly asked
- Explain test failures when they occur

## Communication Style

### Be Clear About Actions

Always clearly state:
- What files were created/modified/deleted
- What the user needs to do next
- What commands they can run

### Don't Assume

- Don't assume the user wants to commit immediately
- Don't assume the user wants to push immediately
- Let the user control the workflow

### Example Responses

**Good:**
```
I've updated cli_tool/commands/upgrade.py to handle ZIP files.

Changes made:
- Added zipfile import
- Modified get_binary_name() to return .zip for Windows
- Updated verify_binary() to check ZIP files

You can test the changes and commit when ready.
```

**Bad:**
```
Done! I've updated the file and pushed the changes.
[Automatically committed and pushed]
```

## Summary

**Golden Rule:** The assistant is a tool that modifies files. The user controls git.

- Create/modify/delete files: ✅ Yes
- Run git commands: ❌ No (unless explicitly requested)
- Use --no-verify: ❌ Never

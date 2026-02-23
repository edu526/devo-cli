---
inclusion: always
---

# Git Workflow Best Practices

## Commit Guidelines

### NEVER Use `--no-verify`

**CRITICAL:** Do NOT bypass pre-commit hooks with `--no-verify` flag.

```bash
# ❌ WRONG - Bypasses all quality checks
git commit -m "message" --no-verify

# ✅ CORRECT - Runs all pre-commit hooks
git commit -m "message"
```

**Why this matters:**
- Pre-commit hooks run linting, formatting, and validation
- Bypassing hooks leads to CI failures
- Code quality issues slip into the repository
- Other developers waste time fixing formatting issues

### Pre-Commit Hooks

The repository has pre-commit hooks that automatically:
- Format code with `black`
- Sort imports with `isort`
- Check code quality with `flake8`
- Validate branch names
- Check for security issues

**If hooks fail:**
1. Review the error messages
2. Fix the issues manually or let hooks auto-fix
3. Stage the fixed files: `git add .`
4. Commit again (hooks will run again)

### Manual Formatting Before Commit

If you prefer to format before committing:

```bash
# Format all code
make format

# Or manually
black cli_tool/ tests/
isort cli_tool/ tests/

# Verify everything is clean
make lint

# Then commit
git commit -m "message"
```

## Branch Naming

Follow the pattern: `feature/<description>` or `feature/<ticket>-<description>`

```bash
# ✅ Good
feature/windows-onedir-distribution
feature/JIRA-123-add-logging
fix/memory-leak

# ❌ Bad
my-branch
test
```

## Commit Message Format

Follow conventional commits: `<type>(<scope>): <description>`

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `chore` - Maintenance tasks
- `docs` - Documentation changes
- `refactor` - Code refactoring
- `test` - Test changes
- `style` - Code style changes
- `perf` - Performance improvements
- `ci` - CI/CD changes

**Examples:**
```bash
feat(cli): add new command for code generation
fix(upgrade): handle ZIP files for Windows onedir
chore(deps): update dependencies
docs(readme): add installation instructions
```

## Common Mistakes to Avoid

### 1. Using `--no-verify` to Skip Hooks

**Problem:** Bypasses all quality checks
**Solution:** Let hooks run, fix issues they find

### 2. Not Staging Hook Changes

**Problem:** Hooks auto-fix files but they're not staged
**Solution:** After hooks run, check `git status` and stage changes

```bash
git commit -m "message"
# Hook runs and modifies files
git add .  # Stage the hook changes
git commit -m "message"  # Commit again
```

### 3. Committing Without Testing

**Problem:** Broken code gets committed
**Solution:** Run tests before committing

```bash
make test
git commit -m "message"
```

## Workflow Summary

**Standard workflow:**
```bash
# 1. Make changes
vim cli_tool/commands/myfile.py

# 2. Run tests
make test

# 3. Stage changes
git add cli_tool/commands/myfile.py

# 4. Commit (hooks run automatically)
git commit -m "feat(cli): add new feature"

# 5. If hooks modify files, stage and commit again
git add .
git commit -m "feat(cli): add new feature"

# 6. Push
git push
```

## Remember

- Pre-commit hooks are your friends, not obstacles
- They catch issues before CI does
- They save time for everyone on the team
- Never use `--no-verify` unless you have a very specific reason

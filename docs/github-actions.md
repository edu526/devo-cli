# GitHub Actions Setup

Complete guide for GitHub Actions workflows in this project.

## Workflows Overview

### 1. Tests Workflow (`.github/workflows/test.yml`)

**Purpose:** Run tests on every push and pull request

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

**Jobs:**
- Lint code with flake8
- Run pytest test suite
- Test on Python 3.12

**Example:**
```bash
git push origin main
# → Triggers test workflow
```

---

### 2. Build and Release Workflow (`.github/workflows/build-binaries.yml`)

**Purpose:** Build binaries for all platforms and create GitHub Release

**Triggers:**
- Push tags matching `v*` (e.g., `v1.0.0`)
- Manual trigger via GitHub UI

**Jobs:**

1. **Test** - Run full test suite
2. **Build Package** - Build Python wheel and source distribution
3. **Build Binaries** - Build standalone binaries for:
   - Linux amd64
   - macOS Intel (amd64)
   - macOS Apple Silicon (arm64)
   - Windows amd64
4. **Create Release** - Create GitHub Release with all artifacts

**Example:**
```bash
git tag v1.0.0
git push origin v1.0.0
# → Triggers build workflow
# → Creates GitHub Release with all binaries
```

## Build Matrix

The build workflow uses a matrix strategy to build for multiple platforms in parallel:

```yaml
matrix:
  include:
    - os: ubuntu-latest      # Linux amd64
    - os: macos-13           # macOS Intel
    - os: macos-14           # macOS Apple Silicon
    - os: windows-latest     # Windows amd64
```

## Artifacts

Each workflow run produces artifacts:

### Test Workflow
- No artifacts (just test results)

### Build Workflow
- `python-package` - Python wheel and source distribution
- `devo-linux-amd64` - Linux binary
- `devo-darwin-amd64` - macOS Intel binary
- `devo-darwin-arm64` - macOS Apple Silicon binary
- `devo-windows-amd64` - Windows binary

Artifacts are available for 90 days after the workflow run.

## GitHub Release

When a tag is pushed, the workflow automatically:

1. Builds all binaries
2. Generates SHA256 checksums
3. Creates a GitHub Release
4. Uploads all files to the release
5. Generates release notes from commits

**Release includes:**
- All platform binaries
- Python package (wheel + source)
- SHA256SUMS file
- Auto-generated release notes

## Manual Workflow Trigger

You can manually trigger the build workflow:

1. Go to **Actions** tab
2. Select **Build and Release** workflow
3. Click **Run workflow**
4. Select branch/tag
5. Click **Run workflow** button

## Secrets and Permissions

### Required Secrets
- `GITHUB_TOKEN` - Automatically provided by GitHub (no setup needed)
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token (optional, for notifications)

### Required Variables (for Telegram notifications)
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID (optional)

### Required Permissions
The workflow needs:
- `contents: write` - To create releases
- `actions: read` - To download artifacts

These are automatically granted by GitHub.

## Telegram Notifications

The release workflow can send notifications to Telegram when a release completes or fails using the [appleboy/telegram-action](https://github.com/appleboy/telegram-action).

### Setup Instructions

1. **Create a Telegram Bot**
   - Open Telegram and search for `@BotFather`
   - Send `/newbot` command
   - Follow instructions to create your bot
   - Save the bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

2. **Get Your Chat ID**

   Option A - Personal chat:
   - Send a message to your bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your `chat_id` in the response (looks like `123456789`)

   Option B - Group chat:
   - Add bot to your group
   - Send a message in the group
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find the group `chat_id` (negative number like `-987654321`)

3. **Configure GitHub Secrets and Variables**
   - Go to your repository on GitHub
   - Navigate to **Settings** → **Secrets and variables** → **Actions**

   Add a secret:
   - Click on **Secrets** tab
   - Click **New repository secret**
   - Name: `TELEGRAM_BOT_TOKEN`, Value: your bot token

   Add a variable:
   - Click on **Variables** tab
   - Click **New repository variable**
   - Name: `TELEGRAM_CHAT_ID`, Value: your chat ID

4. **Test the Notification**
   - Create a new release to trigger the workflow
   - Check your Telegram for the notification

### Notification Format

**Success notification includes:**
- 🎉 Release status
- 📦 Version number
- 🏷️ Git tag
- 📂 Repository name
- 🔗 Links to release and workflow
- Build results for all jobs (tests, binaries, upload)

**Failure notification includes:**
- 🚨 Error status
- ❌ Failed release tag
- Build results showing which step failed
- 🔗 Link to workflow logs for debugging

**Test failure notification:**
- 🚨 Tests failed status
- ❌ Branch and commit information
- 👤 Author who triggered the workflow
- 🔗 Link to workflow logs
- Note: Sent when tests fail before release is attempted

### Disable Notifications

To disable notifications, simply don't set the `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` variables. The workflow will skip the notification steps automatically.

### Troubleshooting

**"Chat not found" error:**
- Make sure you've sent at least one message to the bot
- Verify the chat ID is correct (use the getUpdates API)
- For groups, ensure the bot is still a member

**No notification received:**
- Check that both variables are set correctly in GitHub
- Verify the bot token is valid
- Check the workflow logs for any errors in the notify-telegram job

## Workflow Status Badges

Add status badges to your README:

```markdown
![Tests](https://github.com/edu526/devo-cli/actions/workflows/test.yml/badge.svg)
![Build](https://github.com/edu526/devo-cli/actions/workflows/build-binaries.yml/badge.svg)
```

## Monitoring Workflows

### View Workflow Runs
1. Go to **Actions** tab
2. See all workflow runs
3. Click on a run to see details

### View Logs
1. Click on a workflow run
2. Click on a job (e.g., "Build linux-amd64")
3. Expand steps to see logs

### Download Artifacts
1. Go to a completed workflow run
2. Scroll to **Artifacts** section
3. Click to download

## Troubleshooting

### Workflow not triggering

**Check:**
- Workflow file is in `.github/workflows/`
- YAML syntax is valid
- Branch/tag matches trigger conditions

### Build fails on specific platform

**Check:**
- Build script works locally on that platform
- Dependencies are correctly installed
- Python version matches (3.12)

### Release not created

**Check:**
- Tag starts with `v` (e.g., `v1.0.0`)
- All build jobs completed successfully
- `GITHUB_TOKEN` has write permissions

### Binary doesn't work

**Check:**
- Downloaded correct platform binary
- Binary has execute permissions (Linux/macOS)
- AWS credentials are configured

## Local Testing

Test workflows locally with [act](https://github.com/nektos/act):

```bash
# Install act
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run test workflow
act push

# Run build workflow
act push --workflows .github/workflows/build-binaries.yml
```

## Optimization Tips

### Speed up builds
- Use caching for dependencies
- Run jobs in parallel
- Use matrix strategy

### Reduce costs (private repos)
- Only run on specific branches
- Skip redundant jobs
- Use self-hosted runners for heavy builds

## Workflow Costs

### Public Repositories
- ✅ Unlimited minutes
- ✅ All features free

### Private Repositories
- 2000 minutes/month free
- ~15 minutes per release
- ~2 minutes per test run
- ~133 releases/month within free tier

## Best Practices

1. **Always run tests before building**
   - Prevents building broken code
   - Saves build time

2. **Use matrix for multi-platform builds**
   - Parallel execution
   - Consistent configuration

3. **Generate checksums**
   - Security verification
   - Integrity checks

4. **Auto-generate release notes**
   - Saves time
   - Consistent format

5. **Keep workflows DRY**
   - Reuse steps
   - Use composite actions

## Next Steps

- [ ] Add code coverage reporting
- [ ] Set up Dependabot for dependency updates
- [ ] Add security scanning (CodeQL)
- [ ] Configure branch protection rules
- [ ] Add performance benchmarks

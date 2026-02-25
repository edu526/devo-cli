# GitHub Actions Workflows

Complete guide for GitHub Actions workflows in this project.

## Workflows Overview

### 1. Test Workflow (`.github/workflows/test.yml`)

**Purpose:** Run tests and build verification on pull requests

**Triggers:**
- Pull requests to `main` branch

**Jobs:**
- **test**: Run pytest test suite with Python 3.12
- **build-test**: Build and test binaries on all platforms (Linux, macOS Intel, macOS ARM, Windows)

**Example:**
```bash
git push origin feature/my-feature
# → Opens PR → Triggers test workflow
```

---

### 2. Release Workflow (`.github/workflows/release.yml`)

**Purpose:** Automated versioning and release creation

**Triggers:**
- Push to `main` branch
- Manual trigger via GitHub UI

**Jobs:**

1. **test** - Run full test suite
2. **check-version** - Analyze commits to determine if release is needed
3. **build-binaries** - Build standalone binaries for all platforms
4. **create-release** - Create GitHub Release with semantic versioning
5. **upload-assets** - Upload binaries and checksums to release
6. **notify-telegram** - Send notification (optional)

**Example:**
```bash
git commit -m "feat: add new feature"
git push origin main
# → Triggers release workflow
# → Creates release v1.1.0 with binaries
```

## Build Matrix

The workflows use a matrix strategy to build for multiple platforms in parallel:

```yaml
matrix:
  include:
    - os: ubuntu-latest      # Linux amd64
    - os: macos-latest       # macOS Intel
    - os: macos-14           # macOS Apple Silicon
    - os: windows-latest     # Windows amd64
```

## Artifacts

### Test Workflow
- Binary artifacts for verification (not published)

### Release Workflow
- `devo-linux-amd64` - Linux binary
- `devo-darwin-amd64` - macOS Intel binary
- `devo-darwin-arm64` - macOS Apple Silicon binary
- `devo-windows-amd64.zip` - Windows binary (ZIP package)
- `SHA256SUMS` - Checksums for all binaries

## GitHub Release

When commits are pushed to main, the workflow:

1. Analyzes commits using python-semantic-release
2. Determines if new release is needed
3. Calculates next version number
4. Builds all binaries
5. Creates git tag and GitHub release
6. Uploads binaries and checksums
7. Updates CHANGELOG.md

**Release includes:**
- All platform binaries
- SHA256SUMS file
- Auto-generated release notes from commits

## Manual Workflow Trigger

You can manually trigger the release workflow:

1. Go to **Actions** tab
2. Select **Release** workflow
3. Click **Run workflow**
4. Select branch (main)
5. Click **Run workflow** button

## Secrets and Permissions

### Required Permissions
The workflow needs:
- `contents: write` - To create releases and push tags
- `issues: write` - For semantic-release
- `pull-requests: write` - For semantic-release

These are automatically granted by GitHub.

### Optional Secrets (for Telegram notifications)
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID (configured as variable)

## Telegram Notifications

The release workflow can send notifications to Telegram when a release completes or fails.

### Setup Instructions

1. **Create a Telegram Bot**
   - Open Telegram and search for `@BotFather`
   - Send `/newbot` command
   - Follow instructions to create your bot
   - Save the bot token

2. **Get Your Chat ID**
   - Send a message to your bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your `chat_id` in the response

3. **Configure GitHub Secrets and Variables**
   - Go to repository **Settings** → **Secrets and variables** → **Actions**
   - Add secret: `TELEGRAM_BOT_TOKEN`
   - Add variable: `TELEGRAM_CHAT_ID`

### Notification Types

- **Success**: Release created successfully with version and links
- **Failure**: Build or release failed with error details
- **No Release**: Tests passed but no new release needed

### Disable Notifications

To disable notifications, simply don't set the `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. The workflow will skip notification steps automatically.

## Workflow Status Badges

Add status badges to your README:

```markdown
![Tests](https://github.com/edu526/devo-cli/actions/workflows/test.yml/badge.svg)
![Release](https://github.com/edu526/devo-cli/actions/workflows/release.yml/badge.svg)
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
- Branch matches trigger conditions

### Build fails on specific platform

**Check:**
- Build script works locally on that platform
- Dependencies are correctly installed
- Python version matches (3.12)

### Release not created

**Check:**
- Commits follow conventional format (feat:, fix:, etc.)
- Commits exist since last release
- `GITHUB_TOKEN` has write permissions

### Binary doesn't work

**Check:**
- Downloaded correct platform binary
- Binary has execute permissions (Linux/macOS)
- AWS credentials are configured

## Best Practices

1. **Always run tests before building** - Prevents building broken code
2. **Use matrix for multi-platform builds** - Parallel execution
3. **Generate checksums** - Security verification
4. **Auto-generate release notes** - Consistent format
5. **Use conventional commits** - Enables automatic versioning

## See Also

- [CI/CD Overview](overview.md) - Workflow strategy
- [Semantic Release](semantic-release.md) - Automated versioning

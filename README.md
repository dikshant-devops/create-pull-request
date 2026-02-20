# Create Pull Request Action (Python)

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-Create%20Pull%20Request%20(Python)-blue?logo=github)](https://github.com/marketplace/actions/create-pull-request-python)
[![Test](https://github.com/dikshant-devops/create-pull-request/actions/workflows/test.yml/badge.svg)](https://github.com/dikshant-devops/create-pull-request/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python port of the popular [create-pull-request](https://github.com/peter-evans/create-pull-request) GitHub Action. Automatically creates pull requests for changes made during workflow execution.

## Features

- **Pure Python** - Easy to understand and contribute to
- **Feature Parity** - All 23 inputs and 6 outputs from the original action
- **Docker-based** - Consistent environment across all runners
- **Well Tested** - Comprehensive unit and integration test coverage
- **PyGithub** - Robust GitHub API integration with retry logic
- **Robust** - Handles rebasing, cherry-picking, and conflict resolution

## Why Python?

This port provides:
- **Accessibility** - More accessible to data scientists and ML engineers
- **Maintainability** - Easier to contribute for Python-first organizations
- **Learning** - Great reference for understanding the original implementation
- **Compatibility** - Drop-in replacement with identical inputs/outputs

## Quick Start

### Basic Usage

```yaml
name: Create Pull Request
on:
  push:
    branches:
      - main

jobs:
  createPullRequest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Make changes
        run: |
          echo "Updated content" > file.txt

      - name: Create Pull Request
        uses: dikshant-devops/create-pull-request@v1
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          commit-message: "Update file.txt"
          branch: update-file
          title: "Automated update to file.txt"
          body: |
            This PR was automatically created by the create-pull-request action.

            ## Changes
            - Updated file.txt with new content
```

### With Labels, Assignees, and Reviewers

```yaml
- name: Create Pull Request
  uses: dikshant-devops/create-pull-request@v1
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
    commit-message: "Update dependencies"
    branch: update-deps
    title: "chore: Update dependencies"
    body: "Automated dependency updates"
    labels: |
      dependencies
      automated
    assignees: username1, username2
    reviewers: reviewer1
    team-reviewers: team-name
    milestone: 1
```

### With Branch Suffix

```yaml
- name: Create Pull Request
  uses: dikshant-devops/create-pull-request@v1
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
    branch: update-
    branch-suffix: timestamp
    # Creates branch like: update-1707825600
```

### Push to Fork

```yaml
- name: Create Pull Request
  uses: dikshant-devops/create-pull-request@v1
  with:
    token: ${{ secrets.PAT_TOKEN }}  # Needs repo scope
    push-to-fork: username/repo-fork
    branch: feature
    title: "Feature from fork"
```

## Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `token` | GitHub token for API operations | `${{ github.token }}` |
| `path` | Repository path relative to $GITHUB_WORKSPACE | `.` |
| `add-paths` | Comma/newline-separated list of file paths to commit | `` (all changes) |
| `commit-message` | Commit message | `[create-pull-request] automated change` |
| `committer` | Committer name and email `Name <email>` | `github-actions[bot] <...>` |
| `author` | Author name and email | `${{ github.actor }} <...>` |
| `signoff` | Add Signed-off-by line | `false` |
| `sign-commits` | Sign commits with GitHub | `false` |
| `branch` | Pull request branch name | `create-pull-request/patch` |
| `delete-branch` | Delete branch when closing PR | `false` |
| `branch-suffix` | Branch suffix type: `none`, `random`, `timestamp`, `short-commit-hash` | `none` |
| `base` | Pull request base branch | (current branch) |
| `push-to-fork` | Fork to push changes to (`owner/repo-fork`) | `` |
| `title` | Pull request title | `Changes by create-pull-request action` |
| `body` | Pull request body | `` |
| `body-path` | Path to file containing PR body | `` |
| `labels` | Comma/newline-separated list of labels | `` |
| `assignees` | Comma/newline-separated list of assignees | `` |
| `reviewers` | Comma/newline-separated list of reviewers | `` |
| `team-reviewers` | Comma/newline-separated list of team reviewers | `` |
| `milestone` | Milestone number | `0` |
| `draft` | Create as draft PR | `false` |
| `maintainer-can-modify` | Allow maintainer modifications | `true` |

## Outputs

| Output | Description |
|--------|-------------|
| `pull-request-number` | Pull request number |
| `pull-request-url` | Pull request URL |
| `pull-request-operation` | Operation performed: `created`, `updated`, or `closed` |
| `pull-request-head-sha` | Head commit SHA |
| `pull-request-branch` | Pull request branch name |
| `pull-request-commits-verified` | Whether commits are verified |

## Examples

### Scheduled Updates

```yaml
name: Update Data
on:
  schedule:
    - cron: '0 0 * * *'  # Daily at midnight

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Fetch latest data
        run: |
          curl -o data.json https://api.example.com/data

      - name: Create PR if data changed
        uses: dikshant-devops/create-pull-request@v1
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          commit-message: "Update data.json"
          branch: data-update
          title: "chore: Update data.json"
          body: |
            Automated data update from scheduled workflow.

            - Source: https://api.example.com/data
            - Date: ${{ github.event.repository.updated_at }}
          labels: automated, data-update
```

### Code Formatting

```yaml
name: Format Code
on:
  pull_request:

jobs:
  format:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.head_ref }}

      - name: Format code
        run: |
          pip install black
          black .

      - name: Create PR for formatting
        uses: dikshant-devops/create-pull-request@v1
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          commit-message: "style: Format code with black"
          branch: auto-format-${{ github.head_ref }}
          title: "Auto-format code in ${{ github.head_ref }}"
          body: |
            Automatically formatted code with black.

            Base PR: #${{ github.event.pull_request.number }}
          labels: formatting
```

### Dependency Updates

```yaml
name: Update Dependencies
on:
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Update pip packages
        run: |
          pip install --upgrade pip
          pip list --outdated --format=freeze | cut -d= -f1 | xargs pip install -U
          pip freeze > requirements.txt

      - name: Create PR
        uses: dikshant-devops/create-pull-request@v1
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          commit-message: "chore: Update dependencies"
          branch: deps-update
          branch-suffix: timestamp
          title: "chore: Update Python dependencies"
          body: |
            Automated dependency updates.

            Please review changes and test before merging.
          labels: dependencies
          reviewers: maintainer-username
```

## Architecture

### Module Structure

```
create-pull-request-python/
├── src/create_pull_request/
│   ├── main.py                 # 10-phase orchestration
│   ├── models.py               # Dataclasses for config/state
│   ├── git_command_manager.py  # Git CLI wrapper
│   ├── git_config_helper.py    # Git config state management
│   ├── github_helper.py        # PyGithub API wrapper
│   ├── branch_manager.py       # Branch creation/update logic
│   ├── utils.py                # Parsing and utilities
│   └── exceptions.py           # Custom exceptions
```

### Workflow Phases

The action executes in 10 phases:

1. **Parse Inputs** - Load configuration from environment
2. **Initialize Git** - Set up git command manager
3. **Save Config** - Backup git configuration
4. **Configure Git** - Set up identity and credentials
5. **Initialize GitHub API** - Connect to GitHub with PyGithub
6. **Determine Base** - Resolve base branch
7. **Create/Update Branch** - Complex branch management logic
8. **Push Branch** - Push to origin or fork
9. **Create/Update PR** - Create or update pull request
10. **Set Outputs** - Write outputs and cleanup

## Comparison with TypeScript Version

| Aspect | TypeScript Original | Python Port |
|--------|-------------------|-------------|
| **Language** | TypeScript/Node.js | Python 3.11 |
| **GitHub API** | Octokit | PyGithub |
| **Git Operations** | @actions/exec | subprocess wrapper |
| **Docker Image** | ~100MB (Node Alpine) | ~150MB (Python slim) |
| **Startup Time** | ~2-3s | ~3-4s |
| **Inputs** | 23 | 23 (identical) |
| **Outputs** | 6 | 6 (identical) |
| **Test Framework** | Jest | pytest |
| **Type Safety** | TypeScript | Python type hints |

**Feature Parity:** ✅ All features from TypeScript version are implemented

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/dikshant-devops/create-pull-request.git
cd create-pull-request-python

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install pytest pytest-cov pytest-mock ruff mypy
```

### Running Tests

```bash
# Unit tests
PYTHONPATH=src pytest tests/unit/ -v

# Integration tests
PYTHONPATH=src pytest tests/integration/ -v

# With coverage
PYTHONPATH=src pytest tests/ -v --cov=src/create_pull_request --cov-report=html

# Linting
ruff check src/

# Type checking
mypy src/create_pull_request
```

### Building Docker Image

```bash
# Build
docker build -t create-pull-request-python .

# Test locally (requires git repo)
docker run --rm -v $(pwd):/workspace \
  -e INPUT_TOKEN=$GITHUB_TOKEN \
  -e GITHUB_REPOSITORY=owner/repo \
  create-pull-request-python
```

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions,
how to run the same checks as CI locally, and the pull request process.

### Recommended Branch Protection

For maintainers, enable these required status checks on `master`:

- `Unit Tests` (all matrix entries)
- `Integration Tests`
- `Docker Build`
- `Lint and Type Check`
- `Analyze Python` (CodeQL)
- `Trivy Image Scan`

## Migration from TypeScript Version

The Python port is a **drop-in replacement** - simply change the action reference:

```yaml
# Before (TypeScript)
- uses: peter-evans/create-pull-request@v6

# After (Python)
- uses: dikshant-devops/create-pull-request@v1
```

All inputs and outputs are identical. No workflow changes required!

## Publishing to GitHub Marketplace

This action is ready for the [GitHub Actions Marketplace](https://github.com/marketplace?type=actions). The `action.yml` already includes the required `branding` configuration.

### Prerequisites

- The repository must be **public**
- Enable **two-factor authentication** on your GitHub account
- Accept the [GitHub Marketplace Developer Agreement](https://docs.github.com/en/apps/github-marketplace/github-marketplace-overview/about-github-marketplace)

### Steps to Publish

1. Go to the repository on GitHub
2. Click **Releases** > **Draft a new release**
3. Check the **Publish this Action to the GitHub Marketplace** checkbox
4. GitHub will validate your `action.yml` -- fix any reported errors
5. Choose a tag (e.g., `v1.0.0`) and create the release
6. Once published, the action will appear at `https://github.com/marketplace/actions/create-pull-request-python`

### Marketplace Metadata (from action.yml)

| Field | Value |
|-------|-------|
| Name | `Create Pull Request (Python)` |
| Icon | `git-pull-request` |
| Color | `blue` |
| Author | `Create Pull Request Action` |

After publishing, users can find and use your action directly from the marketplace.

## License

[MIT](LICENSE)

## Credits

This is a Python port of the excellent [create-pull-request](https://github.com/peter-evans/create-pull-request) action by [Peter Evans](https://github.com/peter-evans). All credit for the original design and implementation goes to the original project.

## Support

- [Report Issues](https://github.com/dikshant-devops/create-pull-request/issues)
- [Discussions](https://github.com/dikshant-devops/create-pull-request/discussions)

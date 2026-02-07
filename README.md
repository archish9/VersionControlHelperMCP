# GitHub MCP Server

A **Model Context Protocol (MCP)** server providing version control operations as tools for AI coding agents. Built specifically for integration with LangChain deepagents and other MCP-compatible LLM workflows.

## What is This?

This MCP server exposes **Git version control operations** as structured tools that Large Language Models (LLMs) and AI agents can invoke programmatically. Instead of executing raw git commands, an AI coding agent can call typed, validated tools like `commit_all_changes`, `rollback_to_commit`, or `compare_commits` through the standardized MCP protocol.

### Why Use This?

| Problem | Solution |
|---------|----------|
| AI agents generate code without version history | Every code change can be committed automatically |
| Bad AI-generated code breaks the project | Rollback to any previous commit instantly |
| No visibility into what the agent changed | Compare any two commits to see exact diffs |
| Risk of losing work during agent iterations | Branching allows safe experimentation |

---

## Installation

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Git installed on system

### Setup

```bash
# Clone the repository
git clone https://github.com/your-repo/github-mcp-small.git
cd github-mcp-small

# Install dependencies with uv
uv sync
```

---

## Running the Server

### STDIO Mode (Default)

For local usage with LangChain or other MCP clients:

```bash
uv run github-mcp
```

### With Default Repository Path

Set `REPO_PATH` to avoid passing `repo_path` in every tool call:

```bash
REPO_PATH=/path/to/your/project uv run github-mcp
```

### Development/Debugging

Use the MCP inspector for testing:

```bash
uv run mcp dev src/github_mcp/server.py
```

---

## Available Tools

This server provides **10 tools** for complete version control workflows.

### 1. `initialize_repo`

**Purpose**: Initialize a new git repository or verify an existing one.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `repo_path` | string | ✅ | - | Absolute path to repository directory |
| `initial_commit` | boolean | ❌ | `true` | Create initial commit with README |

**Returns**: Status message (e.g., "Initialized repository with initial commit: abc1234")

**When to Use**:
- Starting a new project from scratch
- Before any other git operations on a fresh directory
- Safe to call on already-initialized repos (will return "Already initialized")

**Example**:
```json
{
  "tool": "initialize_repo",
  "arguments": {
    "repo_path": "/Users/dev/my-project",
    "initial_commit": true
  }
}
```

---

### 2. `get_repo_status`

**Purpose**: Check the current state of the repository.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `repo_path` | string | ✅ | Absolute path to repository |

**Returns**: JSON object with:
- `is_initialized`: Whether git is set up
- `current_branch`: Active branch name
- `has_changes`: Whether there are uncommitted changes
- `staged_files`: Files ready to commit
- `modified_files`: Changed but unstaged files
- `untracked_files`: New files not yet tracked

**When to Use**:
- Before committing, to see what will be included
- After making changes, to verify modifications
- To check which branch you're on

---

### 3. `commit_all_changes`

**Purpose**: Stage ALL changes and create a commit in one action.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `repo_path` | string | ✅ | Absolute path to repository |
| `message` | string | ✅ | Commit message describing changes |

**Returns**: Commit SHA (40-character hash) or "No changes to commit"

**Behavior**:
- Automatically runs `git add -A` (stages everything)
- Creates commit with provided message
- **Lazy initialization**: If repo isn't initialized, initializes it first

**When to Use**:
- After generating/modifying code, to save a checkpoint
- Before risky operations, to have a rollback point
- At logical milestones during development

**Best Practices for Commit Messages**:
- Use conventional format: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- Be descriptive: "feat: add user authentication with JWT tokens"
- Reference the change: "fix: resolve null pointer in login handler"

---

### 4. `list_commits`

**Purpose**: Retrieve commit history with details.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `repo_path` | string | ✅ | - | Absolute path to repository |
| `branch` | string | ❌ | `"HEAD"` | Branch name or "HEAD" for current |
| `limit` | integer | ❌ | `50` | Maximum commits to return |

**Returns**: JSON with array of commits, each containing:
- `sha`: Full 40-char commit hash
- `short_sha`: 7-char abbreviated hash
- `message`: Commit message
- `author`: Author name
- `author_email`: Author email
- `timestamp`: ISO timestamp

**When to Use**:
- To find a commit SHA for rollback
- To review what changes were made
- To compare two specific commits

---

### 5. `rollback_to_commit`

**Purpose**: Reset the repository to a previous commit.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `repo_path` | string | ✅ | - | Absolute path to repository |
| `commit_sha` | string | ✅ | - | SHA of target commit (full or short) |
| `mode` | string | ❌ | `"soft"` | Reset mode: `soft`, `mixed`, or `hard` |

**Reset Modes Explained**:

| Mode | Staged Changes | Working Directory | Use Case |
|------|---------------|-------------------|----------|
| `soft` | ✅ Preserved | ✅ Preserved | Undo last commit, keep changes staged |
| `mixed` | ❌ Unstaged | ✅ Preserved | Undo commit, keep files but unstage |
| `hard` | ❌ Deleted | ❌ Deleted | **DANGEROUS**: Completely discard all changes |

**Returns**: Message with new HEAD SHA

**⚠️ WARNING**: `hard` mode permanently deletes uncommitted changes!

**When to Use**:
- Agent generated bad code → rollback to last good commit
- Want to redo work differently → soft reset
- Experiment failed → hard reset to clean state

---

### 6. `compare_commits`

**Purpose**: Show detailed diff between any two commits.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `repo_path` | string | ✅ | Absolute path to repository |
| `from_commit` | string | ✅ | Source commit SHA (older) |
| `to_commit` | string | ✅ | Target commit SHA (newer) |

**Returns**: JSON with:
- `from_commit`, `to_commit`: The compared SHAs
- `files`: Array of changed files, each with:
  - `filename`: Path to file
  - `status`: `added`, `modified`, `deleted`, or `renamed`
  - `additions`: Lines added
  - `deletions`: Lines removed
  - `patch`: Unified diff content
- `total_additions`, `total_deletions`: Summary counts
- `summary`: Human-readable summary

**When to Use**:
- Review what an agent changed in last iteration
- Debug regressions by comparing working vs broken states
- Understand evolution of code over time

---

### 7. `create_branch`

**Purpose**: Create a new git branch for isolated work.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `repo_path` | string | ✅ | - | Absolute path to repository |
| `branch_name` | string | ✅ | - | Name for new branch |
| `from_ref` | string | ❌ | Current HEAD | Commit/branch to branch from |

**Returns**: Confirmation message with branch name

**When to Use**:
- Before experimental changes, create a feature branch
- Keep main branch stable while agent experiments
- Work on multiple features in parallel

**Naming Conventions**:
- `feature/add-auth` - New functionality
- `fix/login-bug` - Bug fixes
- `experiment/new-algo` - Experimental work

---

### 8. `switch_branch`

**Purpose**: Switch to a different branch.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `repo_path` | string | ✅ | Absolute path to repository |
| `branch_name` | string | ✅ | Branch to switch to |

**Returns**: Confirmation of current branch after switch

**When to Use**:
- Switch back to main after completing feature
- Move between different work streams
- Test code on different branches

---

### 9. `list_branches`

**Purpose**: Show all branches with current branch indicator.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `repo_path` | string | ✅ | Absolute path to repository |

**Returns**: Formatted list with `*` marking current branch:
```
* main (abc1234): Initial commit
  feature/auth (def5678): Add login page
```

---

### 10. `generate_commit_message`

**Purpose**: Auto-generate a commit message based on staged changes.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `repo_path` | string | ✅ | - | Absolute path to repository |
| `style` | string | ❌ | `"conventional"` | `conventional` or `simple` |

**Returns**: Suggested commit message with change summary

**Styles**:
- `conventional`: Uses prefixes like `feat:`, `fix:`, `docs:`
- `simple`: Plain descriptive message

---

## Workflow Examples

### Basic Agent Workflow

```
1. initialize_repo(repo_path="/project")     # Set up version control
2. [Agent generates code...]
3. commit_all_changes(message="feat: initial implementation")
4. [Agent makes more changes...]
5. commit_all_changes(message="fix: resolve edge case")
6. [Something breaks...]
7. list_commits(limit=5)                     # Find last good commit
8. rollback_to_commit(sha="abc1234")         # Restore working state
```

### Safe Experimentation

```
1. create_branch(branch_name="experiment/new-algo")
2. switch_branch(branch_name="experiment/new-algo")
3. [Agent experiments with risky changes...]
4. commit_all_changes(message="experiment: try new approach")
5. [If successful]
   switch_branch(branch_name="main")
   # Merge logic here
6. [If failed]
   switch_branch(branch_name="main")        # Just abandon the branch
```

### Debugging Workflow

```
1. list_commits(limit=10)                    # See recent history
2. compare_commits(from="abc", to="def")     # What changed?
3. [Identify the breaking commit]
4. rollback_to_commit(sha="abc", mode="soft")  # Go back, keep changes visible
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `mcp` | ≥1.26.0 | MCP Python SDK for server/tools |
| `gitpython` | ≥3.1.46 | Git repository operations |
| `pygithub` | ≥2.8.1 | GitHub API (future remote ops) |
| `pydantic` | ≥2.0.0 | Structured data models |

---

## Architecture

```
github-mcp-small/
├── pyproject.toml           # UV project configuration
├── src/github_mcp/
│   ├── __init__.py
│   ├── server.py            # MCP server entry point
│   ├── tools.py             # Tool implementations
│   ├── git_utils.py         # GitPython wrapper
│   └── models.py            # Pydantic response models
└── README.md
```

---

## Error Handling

All tools return clear error messages:

| Scenario | Error Message |
|----------|---------------|
| Git not initialized | "Git repository not initialized. Call initialize_repo first." |
| Invalid commit SHA | "Invalid commit SHA: [sha]" |
| Branch not found | "Branch '[name]' not found" |
| No changes to commit | "No changes to commit" |

---

## License

MIT

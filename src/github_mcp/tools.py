"""MCP tool implementations for version control operations."""

from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent

from .git_utils import GitManager
from .models import CommitList, CommitDiff, BranchInfo, RepoStatus


def register_tools(mcp: Server, default_repo_path: str | None = None):
    """Register all MCP tools on the server.
    
    Args:
        mcp: MCP server instance
        default_repo_path: Default repository path (can be overridden per-call)
    """
    
    def get_manager(repo_path: str | None = None) -> GitManager:
        """Get GitManager for the specified or default repo path."""
        path = repo_path or default_repo_path
        if not path:
            raise ValueError("repo_path is required (no default configured)")
        return GitManager(path)

    @mcp.tool()
    async def initialize_repo(
        repo_path: str,
        initial_commit: bool = True,
    ) -> str:
        """Initialize a git repository at the specified path.
        
        Creates .git directory and optionally makes an initial commit.
        Safe to call on already-initialized repos.
        
        Args:
            repo_path: Path to the repository directory
            initial_commit: Whether to create an initial commit (default: True)
            
        Returns:
            Status message indicating success
        """
        manager = GitManager(repo_path)
        return manager.initialize(initial_commit=initial_commit)

    @mcp.tool()
    async def get_repo_status(repo_path: str) -> str:
        """Get the current status of a git repository.
        
        Shows initialization state, current branch, and any uncommitted changes.
        
        Args:
            repo_path: Path to the repository directory
            
        Returns:
            JSON representation of repository status
        """
        manager = GitManager(repo_path)
        status = manager.get_status()
        return status.model_dump_json(indent=2)

    @mcp.tool()
    async def commit_all_changes(
        repo_path: str,
        message: str,
    ) -> str:
        """Stage all changes and create a commit.
        
        Automatically stages all modified, deleted, and new files before committing.
        Will initialize the repository if not already initialized.
        
        Args:
            repo_path: Path to the repository directory
            message: Commit message describing the changes
            
        Returns:
            Commit SHA on success, or message if no changes
        """
        manager = GitManager(repo_path)
        
        # Lazy initialization for mutating operations
        if not manager.is_initialized():
            manager.initialize(initial_commit=False)
        
        return manager.commit_all(message)

    @mcp.tool()
    async def list_commits(
        repo_path: str,
        branch: str = "HEAD",
        limit: int = 50,
    ) -> str:
        """List commits on a branch.
        
        Returns commit history with SHA, message, author, and timestamp.
        
        Args:
            repo_path: Path to the repository directory
            branch: Branch name or 'HEAD' for current branch (default: HEAD)
            limit: Maximum number of commits to return (default: 50)
            
        Returns:
            JSON list of commits
        """
        manager = get_manager(repo_path)
        commits = manager.list_commits(branch=branch, limit=limit)
        return commits.model_dump_json(indent=2)

    @mcp.tool()
    async def rollback_to_commit(
        repo_path: str,
        commit_sha: str,
        mode: str = "soft",
    ) -> str:
        """Rollback the repository to a specific commit.
        
        WARNING: 'hard' mode will discard all uncommitted changes!
        
        Modes:
        - soft: Keep changes staged (safe)
        - mixed: Unstage changes but keep in working directory
        - hard: Discard all changes (destructive!)
        
        Args:
            repo_path: Path to the repository directory
            commit_sha: SHA of the commit to rollback to
            mode: Reset mode - 'soft', 'mixed', or 'hard' (default: soft)
            
        Returns:
            New HEAD commit SHA
        """
        manager = get_manager(repo_path)
        new_head = manager.rollback(commit_sha=commit_sha, mode=mode)
        return f"Rolled back to {commit_sha[:7]}. New HEAD: {new_head[:7]} (mode: {mode})"

    @mcp.tool()
    async def compare_commits(
        repo_path: str,
        from_commit: str,
        to_commit: str,
    ) -> str:
        """Compare two commits and show the differences.
        
        Shows files changed, lines added/deleted, and diff patches.
        
        Args:
            repo_path: Path to the repository directory
            from_commit: Source commit SHA (older)
            to_commit: Target commit SHA (newer)
            
        Returns:
            JSON diff showing all file changes
        """
        manager = get_manager(repo_path)
        diff = manager.compare_commits(from_sha=from_commit, to_sha=to_commit)
        return diff.model_dump_json(indent=2)

    @mcp.tool()
    async def create_branch(
        repo_path: str,
        branch_name: str,
        from_ref: str | None = None,
    ) -> str:
        """Create a new git branch.
        
        Creates a branch from the current HEAD or a specified commit/branch.
        Does not switch to the new branch.
        
        Args:
            repo_path: Path to the repository directory
            branch_name: Name for the new branch
            from_ref: Optional commit SHA or branch name to create from
            
        Returns:
            Confirmation message with branch name
        """
        manager = get_manager(repo_path)
        name = manager.create_branch(branch_name=branch_name, from_ref=from_ref)
        return f"Created branch: {name}"

    @mcp.tool()
    async def switch_branch(
        repo_path: str,
        branch_name: str,
    ) -> str:
        """Switch to a different branch.
        
        Checks out the specified branch, updating the working directory.
        
        Args:
            repo_path: Path to the repository directory
            branch_name: Name of the branch to switch to
            
        Returns:
            Confirmation of current branch after switch
        """
        manager = get_manager(repo_path)
        current = manager.switch_branch(branch_name=branch_name)
        return f"Switched to branch: {current}"

    @mcp.tool()
    async def list_branches(repo_path: str) -> str:
        """List all branches in the repository.
        
        Shows all local branches with current branch marked.
        
        Args:
            repo_path: Path to the repository directory
            
        Returns:
            JSON list of branches with current branch indicator
        """
        manager = get_manager(repo_path)
        branches = manager.list_branches()
        return "\n".join([
            f"{'* ' if b.is_current else '  '}{b.name} ({b.last_commit_sha}): {b.last_commit_message}"
            for b in branches
        ])

    @mcp.tool()
    async def generate_commit_message(
        repo_path: str,
        style: str = "conventional",
    ) -> str:
        """Generate a commit message based on staged changes.
        
        Analyzes the current diff and suggests an appropriate commit message.
        
        Styles:
        - conventional: feat/fix/docs/refactor/test/chore format
        - simple: Plain descriptive message
        
        Args:
            repo_path: Path to the repository directory
            style: Message style - 'conventional' or 'simple' (default: conventional)
            
        Returns:
            Suggested commit message based on changes
        """
        manager = get_manager(repo_path)
        status = manager.get_status()
        
        if not status.has_changes:
            return "No changes to describe"
        
        # Build a description of changes
        changes = []
        if status.staged_files:
            changes.append(f"Staged: {', '.join(status.staged_files[:5])}")
            if len(status.staged_files) > 5:
                changes.append(f"  ...and {len(status.staged_files) - 5} more")
        if status.modified_files:
            changes.append(f"Modified: {', '.join(status.modified_files[:5])}")
        if status.untracked_files:
            changes.append(f"New: {', '.join(status.untracked_files[:5])}")
        
        # Simple heuristic-based message generation
        # In a real implementation, this could call an LLM
        file_count = len(status.staged_files) + len(status.modified_files) + len(status.untracked_files)
        
        if style == "conventional":
            if status.untracked_files:
                prefix = "feat"
            elif any("test" in f.lower() for f in status.modified_files + status.staged_files):
                prefix = "test"
            elif any("readme" in f.lower() or "doc" in f.lower() for f in status.modified_files + status.staged_files):
                prefix = "docs"
            else:
                prefix = "chore"
            
            message = f"{prefix}: update {file_count} file(s)"
        else:
            message = f"Update {file_count} file(s)"
        
        return f"Suggested message: {message}\n\nChanges detected:\n" + "\n".join(changes)

"""Git utilities wrapping GitPython for repository operations."""

import os
from pathlib import Path
from datetime import datetime, timezone

from git import Repo, InvalidGitRepositoryError, GitCommandError
from git.exc import BadName

from .models import (
    CommitInfo,
    CommitList,
    CommitDiff,
    FileChange,
    BranchInfo,
    RepoStatus,
)


class GitManager:
    """Manages git operations for a repository with lazy initialization."""

    def __init__(self, repo_path: str | Path):
        """Initialize the git manager.
        
        Args:
            repo_path: Path to the repository directory
        """
        self.repo_path = Path(repo_path).resolve()
        self._repo: Repo | None = None

    @property
    def repo(self) -> Repo:
        """Get the git repository, raising if not initialized."""
        if self._repo is None:
            try:
                self._repo = Repo(self.repo_path)
            except InvalidGitRepositoryError:
                raise ValueError(
                    f"Git repository not initialized at {self.repo_path}. "
                    "Call initialize_repo first."
                )
        return self._repo

    def is_initialized(self) -> bool:
        """Check if git repository is initialized."""
        try:
            Repo(self.repo_path)
            return True
        except InvalidGitRepositoryError:
            return False

    def initialize(self, initial_commit: bool = True) -> str:
        """Initialize git repository if not already initialized.
        
        Args:
            initial_commit: Whether to create an initial commit
            
        Returns:
            Status message
        """
        if not self.repo_path.exists():
            self.repo_path.mkdir(parents=True, exist_ok=True)

        if self.is_initialized():
            return f"Repository already initialized at {self.repo_path}"

        self._repo = Repo.init(self.repo_path)
        
        if initial_commit:
            # Create a README if the repo is empty
            readme_path = self.repo_path / "README.md"
            if not readme_path.exists():
                readme_path.write_text("# Project\n\nInitialized by GitHub MCP Server.\n")
                self._repo.index.add(["README.md"])
            
            # Stage any existing files
            if self._repo.untracked_files:
                self._repo.index.add(self._repo.untracked_files)
            
            # Check if this is a fresh repo (no commits yet)
            try:
                has_commits = bool(list(self._repo.iter_commits()))
            except Exception:
                has_commits = False
            
            # Create initial commit if there are staged files and no commits yet
            if not has_commits:
                try:
                    commit = self._repo.index.commit("Initial commit")
                    return f"Initialized repository with initial commit: {commit.hexsha[:7]}"
                except Exception:
                    # No files to commit
                    pass

        return f"Initialized empty git repository at {self.repo_path}"

    def get_status(self) -> RepoStatus:
        """Get current repository status."""
        if not self.is_initialized():
            return RepoStatus(
                is_initialized=False,
                has_changes=False,
            )

        repo = self.repo
        
        # Get current branch
        try:
            current_branch = repo.active_branch.name
        except TypeError:
            current_branch = "HEAD (detached)"

        # Get file statuses
        staged = [item.a_path for item in repo.index.diff("HEAD")]
        modified = [item.a_path for item in repo.index.diff(None)]
        untracked = repo.untracked_files

        return RepoStatus(
            is_initialized=True,
            current_branch=current_branch,
            has_changes=bool(staged or modified or untracked),
            staged_files=staged,
            modified_files=modified,
            untracked_files=list(untracked),
        )

    def commit_all(self, message: str) -> str:
        """Stage all changes and commit.
        
        Args:
            message: Commit message
            
        Returns:
            Commit SHA
        """
        repo = self.repo

        # Stage all changes
        repo.git.add(A=True)

        # Check if there are changes to commit
        if not repo.index.diff("HEAD") and not repo.untracked_files:
            return "No changes to commit"

        # Commit
        commit = repo.index.commit(message)
        return commit.hexsha

    def list_commits(self, branch: str = "HEAD", limit: int = 50) -> CommitList:
        """List commits on a branch.
        
        Args:
            branch: Branch name or HEAD
            limit: Maximum number of commits to return
            
        Returns:
            CommitList with commit information
        """
        repo = self.repo
        
        try:
            commits = list(repo.iter_commits(branch, max_count=limit))
        except BadName:
            raise ValueError(f"Branch or ref '{branch}' not found")

        commit_infos = []
        for commit in commits:
            commit_infos.append(
                CommitInfo(
                    sha=commit.hexsha,
                    short_sha=commit.hexsha[:7],
                    message=commit.message.strip(),
                    author=commit.author.name,
                    author_email=commit.author.email,
                    timestamp=datetime.fromtimestamp(
                        commit.committed_date, tz=timezone.utc
                    ),
                )
            )

        # Determine branch name
        if branch == "HEAD":
            try:
                branch_name = repo.active_branch.name
            except TypeError:
                branch_name = "HEAD (detached)"
        else:
            branch_name = branch

        return CommitList(
            commits=commit_infos,
            total_count=len(commit_infos),
            branch=branch_name,
        )

    def rollback(self, commit_sha: str, mode: str = "soft") -> str:
        """Rollback to a specific commit.
        
        Args:
            commit_sha: Commit SHA to rollback to
            mode: 'soft', 'mixed', or 'hard'
            
        Returns:
            New HEAD SHA
        """
        repo = self.repo

        valid_modes = ["soft", "mixed", "hard"]
        if mode not in valid_modes:
            raise ValueError(f"Mode must be one of: {valid_modes}")

        try:
            repo.git.reset(f"--{mode}", commit_sha)
        except GitCommandError as e:
            raise ValueError(f"Failed to reset to {commit_sha}: {e}")

        return repo.head.commit.hexsha

    def compare_commits(self, from_sha: str, to_sha: str) -> CommitDiff:
        """Compare two commits and show differences.
        
        Args:
            from_sha: Source commit SHA
            to_sha: Target commit SHA
            
        Returns:
            CommitDiff with file changes
        """
        repo = self.repo

        try:
            from_commit = repo.commit(from_sha)
            to_commit = repo.commit(to_sha)
        except BadName as e:
            raise ValueError(f"Invalid commit SHA: {e}")

        diffs = from_commit.diff(to_commit)
        
        files = []
        total_add = 0
        total_del = 0

        for diff in diffs:
            # Determine status
            if diff.new_file:
                status = "added"
            elif diff.deleted_file:
                status = "deleted"
            elif diff.renamed:
                status = "renamed"
            else:
                status = "modified"

            # Get patch content
            try:
                patch = diff.diff.decode("utf-8", errors="replace") if diff.diff else None
            except Exception:
                patch = None

            # Count additions/deletions from patch
            additions = 0
            deletions = 0
            if patch:
                for line in patch.split("\n"):
                    if line.startswith("+") and not line.startswith("+++"):
                        additions += 1
                    elif line.startswith("-") and not line.startswith("---"):
                        deletions += 1

            total_add += additions
            total_del += deletions

            files.append(
                FileChange(
                    filename=diff.b_path or diff.a_path,
                    status=status,
                    additions=additions,
                    deletions=deletions,
                    patch=patch,
                )
            )

        summary = f"{len(files)} files changed, {total_add} insertions(+), {total_del} deletions(-)"

        return CommitDiff(
            from_commit=from_sha,
            to_commit=to_sha,
            files=files,
            total_additions=total_add,
            total_deletions=total_del,
            summary=summary,
        )

    def create_branch(self, branch_name: str, from_ref: str | None = None) -> str:
        """Create a new branch.
        
        Args:
            branch_name: Name for the new branch
            from_ref: Optional commit/branch to create from
            
        Returns:
            New branch name
        """
        repo = self.repo

        if from_ref:
            try:
                start_point = repo.commit(from_ref)
            except BadName:
                raise ValueError(f"Invalid ref '{from_ref}'")
            repo.create_head(branch_name, start_point)
        else:
            repo.create_head(branch_name)

        return branch_name

    def switch_branch(self, branch_name: str) -> str:
        """Switch to a different branch.
        
        Args:
            branch_name: Branch to switch to
            
        Returns:
            Current branch name after switch
        """
        repo = self.repo

        try:
            branch = repo.heads[branch_name]
        except IndexError:
            raise ValueError(f"Branch '{branch_name}' not found")

        branch.checkout()
        return repo.active_branch.name

    def list_branches(self) -> list[BranchInfo]:
        """List all branches.
        
        Returns:
            List of branch information
        """
        repo = self.repo
        
        try:
            current = repo.active_branch.name
        except TypeError:
            current = None

        branches = []
        for branch in repo.heads:
            branches.append(
                BranchInfo(
                    name=branch.name,
                    is_current=branch.name == current,
                    last_commit_sha=branch.commit.hexsha[:7],
                    last_commit_message=branch.commit.message.strip().split("\n")[0],
                )
            )

        return branches

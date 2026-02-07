"""Pydantic models for structured tool outputs."""

from datetime import datetime
from pydantic import BaseModel, Field


class CommitInfo(BaseModel):
    """Information about a single commit."""
    
    sha: str = Field(description="Full commit SHA hash")
    short_sha: str = Field(description="Short commit SHA (7 chars)")
    message: str = Field(description="Commit message")
    author: str = Field(description="Author name")
    author_email: str = Field(description="Author email")
    timestamp: datetime = Field(description="Commit timestamp")
    

class CommitList(BaseModel):
    """List of commits with metadata."""
    
    commits: list[CommitInfo] = Field(description="List of commits")
    total_count: int = Field(description="Total number of commits returned")
    branch: str = Field(description="Branch name")


class FileChange(BaseModel):
    """Changes to a single file in a diff."""
    
    filename: str = Field(description="Path to the file")
    status: str = Field(description="Change status: added, modified, deleted, renamed")
    additions: int = Field(description="Number of lines added")
    deletions: int = Field(description="Number of lines deleted")
    patch: str | None = Field(default=None, description="Unified diff patch content")


class CommitDiff(BaseModel):
    """Diff between two commits."""
    
    from_commit: str = Field(description="Source commit SHA")
    to_commit: str = Field(description="Target commit SHA")
    files: list[FileChange] = Field(description="List of changed files")
    total_additions: int = Field(description="Total lines added")
    total_deletions: int = Field(description="Total lines deleted")
    summary: str = Field(description="Human-readable summary of changes")


class BranchInfo(BaseModel):
    """Information about a git branch."""
    
    name: str = Field(description="Branch name")
    is_current: bool = Field(description="Whether this is the current branch")
    last_commit_sha: str = Field(description="SHA of the last commit on this branch")
    last_commit_message: str = Field(description="Message of the last commit")


class RepoStatus(BaseModel):
    """Current status of the repository."""
    
    is_initialized: bool = Field(description="Whether git is initialized")
    current_branch: str | None = Field(default=None, description="Current branch name")
    has_changes: bool = Field(description="Whether there are uncommitted changes")
    staged_files: list[str] = Field(default_factory=list, description="Files staged for commit")
    modified_files: list[str] = Field(default_factory=list, description="Modified but unstaged files")
    untracked_files: list[str] = Field(default_factory=list, description="Untracked files")

"""
Git worktrees and automatic merge-back for side tasks.

A side task works in a git worktree on a ``side/<slug>-<short id>`` branch
created from the parent workspace's HEAD. Worktrees live under the CachiBot
data dir (``~/.cachibot/worktrees/<side task id>``), outside the user's
working tree, so they never show up as untracked files in the user's repo.

When the side task's turn finishes, its changes are committed in the
worktree and merged back into the parent workspace's current branch with
``git merge --no-ff``:

- No changes -> nothing to merge (caller marks the side task ``done``).
- Clean merge -> ``merged_commit`` (the merge commit sha) and
  ``merged_files`` (paths changed vs ``base_commit``) are recorded; the
  worktree is removed and the branch deleted with ``git branch -d``.
- Conflict, or git refusing because the parent working tree has local
  changes in the same files -> ``git merge --abort`` (the parent tree ends
  exactly as before), the worktree and branch are kept, and the caller
  marks the side task ``needs_you`` recording ``conflict_files``.

Work is never lost: branches are never force-deleted here, the parent tree
is never reset or cleaned, and a worktree with uncommitted or unmerged
changes is never removed.

All functions are synchronous (subprocess-based); the service runs them
with ``asyncio.to_thread``. Merges are serialized per repo by the service.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from cachibot.models.side_task import SideTask

logger = logging.getLogger(__name__)


class WorktreeError(RuntimeError):
    """A git operation failed in a way the user should see."""


# Fallback commit identity, used via ``git -c`` only when the repo has none
_FALLBACK_NAME = "CachiBot"
_FALLBACK_EMAIL = "cachibot@localhost"


def worktrees_base_dir() -> Path:
    """Directory that holds all side task worktrees (outside user repos)."""
    return Path.home() / ".cachibot" / "worktrees"


def side_branch_name(side_task: SideTask) -> str:
    """Branch name for a side task: side/<slug>-<short id>."""
    slug = re.sub(r"[^a-z0-9]+", "-", side_task.title.lower()).strip("-")
    slug = slug[:30].strip("-") or "task"
    short_id = side_task.id.replace("-", "")[:8]
    return f"side/{slug}-{short_id}"


def worktree_path_for(side_task: SideTask, base_dir: Path | None = None) -> Path:
    """Worktree path for a side task (inside the worktrees base dir)."""
    base = base_dir if base_dir is not None else worktrees_base_dir()
    return base / side_task.id


# ---------------------------------------------------------------------------
# Low-level git runner
# ---------------------------------------------------------------------------


def _git(
    cwd: Path,
    *args: str,
    check: bool = True,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Run a git command, returning the result.

    Raises WorktreeError with the command output when check is True and
    git exits non-zero.
    """
    import os

    env = dict(os.environ)
    env.setdefault("GIT_PAGER", "cat")
    env.setdefault("PAGER", "cat")
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorktreeError(f"git {' '.join(args)} failed to run: {exc}") from exc
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise WorktreeError(f"git {' '.join(args)} failed: {detail}")
    return result


def _identity_args(repo: Path) -> list[str]:
    """-c name/email args when the repo has no commit identity configured."""
    name = _git(repo, "config", "--get", "user.name", check=False).stdout.strip()
    email = _git(repo, "config", "--get", "user.email", check=False).stdout.strip()
    if name and email:
        return []
    return ["-c", f"user.name={_FALLBACK_NAME}", "-c", f"user.email={_FALLBACK_EMAIL}"]


def repo_toplevel(workspace: Path) -> Path:
    """Absolute path of the workspace's repository root (lock key)."""
    out = _git(workspace, "rev-parse", "--show-toplevel").stdout.strip()
    return Path(out).resolve()


def current_branch(workspace: Path) -> str:
    """The branch the parent workspace is on (empty when detached)."""
    return _git(workspace, "branch", "--show-current").stdout.strip()


# ---------------------------------------------------------------------------
# Worktree lifecycle
# ---------------------------------------------------------------------------


def create_worktree(
    workspace: Path,
    side_task: SideTask,
    base_dir: Path | None = None,
) -> tuple[Path, str, str]:
    """Create (or reuse) the side task's worktree.

    Returns (worktree_path, branch, base_commit). On first creation the
    branch ``side/<slug>-<short id>`` is created from the workspace HEAD and
    recorded as base_commit. When the record already has a branch (resume),
    the worktree is recreated from that branch if it is missing; if the
    branch itself is gone the work cannot be recovered and WorktreeError is
    raised.

    Idempotent: an existing on-disk worktree is reused as-is.
    """
    branch = side_task.branch or side_branch_name(side_task)
    path = (
        Path(side_task.worktree_path)
        if side_task.worktree_path
        else worktree_path_for(side_task, base_dir)
    )

    if (path / ".git").exists() or (path / ".git").is_file():
        return (
            path,
            branch,
            side_task.base_commit or _git(workspace, "rev-parse", "HEAD").stdout.strip(),
        )

    path.parent.mkdir(parents=True, exist_ok=True)

    if side_task.branch:
        # Resume: recreate the worktree from the existing branch
        branch_exists = (
            _git(workspace, "rev-parse", "--verify", "--quiet", branch, check=False).returncode == 0
        )
        if not branch_exists:
            raise WorktreeError(
                f"Side task branch {branch} no longer exists; its work cannot be resumed"
            )
        # Drop stale registrations (e.g. the dir was deleted by hand) so the
        # add below cannot fail with "already registered".
        _git(workspace, "worktree", "prune")
        _git(workspace, "worktree", "add", str(path), branch)
        base_commit = (
            side_task.base_commit
            or _git(workspace, "merge-base", branch, "HEAD", check=False).stdout.strip()
        )
    else:
        base_commit = _git(workspace, "rev-parse", "HEAD").stdout.strip()
        _git(workspace, "worktree", "add", "-b", branch, str(path), base_commit)

    logger.info(
        "Side task %s worktree ready at %s (branch %s, base %s)",
        side_task.id,
        path,
        branch,
        base_commit,
    )
    return path, branch, base_commit


def remove_worktree(workspace: Path, path: Path, *, force: bool = False) -> None:
    """Remove a worktree registration and directory.

    Never used on worktrees with uncommitted or unmerged changes unless
    force=True (discard: the user explicitly threw the work away).
    """
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(path))
    result = _git(workspace, *args, check=False)
    if result.returncode != 0:
        if force:
            raise WorktreeError(
                f"Could not remove worktree {path}: {(result.stderr or '').strip()}"
            )
        # Refuse to lose work: report instead of forcing
        raise WorktreeError(
            f"Worktree {path} still has uncommitted or unmerged changes; not removing it"
        )


def delete_branch(workspace: Path, branch: str, *, force: bool = False) -> None:
    """Delete a side branch (-d, or -D only for explicit discard)."""
    _git(workspace, "branch", "-D" if force else "-d", branch)


def worktree_exists(path: Path) -> bool:
    """Whether a worktree directory is still registered/plausible."""
    git_marker = path / ".git"
    return git_marker.exists()


# ---------------------------------------------------------------------------
# Commit + merge back
# ---------------------------------------------------------------------------


def has_uncommitted_changes(worktree: Path) -> bool:
    """Whether the worktree has anything to commit (ignores ignored files)."""
    out = _git(worktree, "status", "--porcelain").stdout
    return bool(out.strip())


def commit_all_changes(worktree: Path, message: str) -> str | None:
    """Stage and commit all changes in the worktree.

    Uses the repo's configured identity, falling back to a local one via
    -c only when none is set. Returns the new commit sha, or None when
    there was nothing to commit.
    """
    if not has_uncommitted_changes(worktree):
        return None
    repo = repo_toplevel(worktree)
    _git(worktree, "add", "-A")
    _git(worktree, *_identity_args(repo), "commit", "-m", message, "--no-verify")
    return _git(worktree, "rev-parse", "HEAD").stdout.strip()


@dataclass
class MergeOutcome:
    """Result of merging a side branch back into the parent workspace."""

    merged: bool
    merged_commit: str | None = None
    merged_files: list[dict[str, str]] = field(default_factory=list)
    conflict_files: list[str] = field(default_factory=list)
    error: str | None = None


_DIFF_STATUS_MAP = {"A": "added", "M": "modified", "D": "deleted", "T": "modified"}


def head_sha(workspace: Path) -> str:
    """Current HEAD sha of the workspace repository."""
    return _git(workspace, "rev-parse", "HEAD").stdout.strip()


def changed_files_vs_base(workspace: Path, base_commit: str, branch: str) -> list[dict[str, str]]:
    """Paths changed on the side branch relative to base_commit."""
    out = _git(workspace, "diff", "--name-status", base_commit, branch).stdout
    files: list[dict[str, str]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = _DIFF_STATUS_MAP.get(parts[0][:1], "modified")
        files.append({"path": parts[-1], "status": status})
    return files


def _conflicted_paths(workspace: Path) -> list[str]:
    """Paths left conflicted by a merge in progress."""
    out = _git(workspace, "diff", "--name-only", "--diff-filter=U").stdout
    return [line for line in out.splitlines() if line.strip()]


def _refusal_paths(stderr: str) -> list[str]:
    """Paths git named in a 'would be overwritten/removed by merge' refusal."""
    paths: list[str] = []
    for line in stderr.splitlines():
        if line.startswith("\t"):
            paths.append(line.strip())
    return paths


def _abort_merge(workspace: Path) -> None:
    """Abort a merge in progress; a no-op when none is in progress."""
    _git(workspace, "merge", "--abort", check=False)


def merge_side_branch(workspace: Path, side_task: SideTask) -> MergeOutcome:
    """Merge the side branch into the parent workspace's current branch.

    On conflict or refusal (parent working tree has local changes in the
    same files) the merge is aborted: the parent tree ends exactly as
    before, and conflict_files lists the paths that need the user.
    """
    branch = side_task.branch
    if not branch:
        return MergeOutcome(merged=False, error="Side task has no branch to merge")

    branch_head = _git(
        workspace, "rev-parse", "--verify", "--quiet", branch, check=False
    ).stdout.strip()
    if not branch_head:
        return MergeOutcome(merged=False, error=f"Side task branch {branch} no longer exists")

    before_head = _git(workspace, "rev-parse", "HEAD").stdout.strip()

    # The merge may create a commit in the parent repo: use its configured
    # identity, falling back to a local one via -c only when none is set.
    result = _git(
        workspace,
        *_identity_args(workspace),
        "merge",
        "--no-ff",
        "--no-edit",
        branch,
        check=False,
        timeout=600,
    )

    if result.returncode == 0:
        merged_commit = _git(workspace, "rev-parse", "HEAD").stdout.strip()
        merged_files: list[dict[str, str]] = []
        if side_task.base_commit:
            merged_files = changed_files_vs_base(workspace, side_task.base_commit, branch)
        return MergeOutcome(
            merged=True,
            merged_commit=merged_commit,
            merged_files=merged_files,
        )

    # Failure: distinguish "needs the user" (conflict / local-changes
    # refusal) from a git error we should surface as a failure.
    stderr = result.stderr or ""
    conflicts = _conflicted_paths(workspace)
    refusals = _refusal_paths(stderr)
    _abort_merge(workspace)

    if conflicts or refusals:
        after_head = _git(workspace, "rev-parse", "HEAD", check=False).stdout.strip()
        if after_head and after_head != before_head:
            # Defensive: a partial merge commit must not stick around
            logger.error(
                "Merge of %s was aborted but HEAD moved (%s -> %s)",
                branch,
                before_head,
                after_head,
            )
        return MergeOutcome(
            merged=False,
            conflict_files=sorted(set(conflicts) | set(refusals)),
        )

    return MergeOutcome(merged=False, error=stderr.strip() or "git merge failed")


def is_branch_merged(workspace: Path, branch: str) -> bool:
    """Whether the side branch is already contained in the parent HEAD.

    Used to recover when a previous run committed and merged but did not
    settle the record (e.g. cancelled mid-merge): the work is in the
    parent already, so the finish is recorded as merged, not done.
    """
    result = _git(workspace, "merge-base", "--is-ancestor", branch, "HEAD", check=False)
    return result.returncode == 0


def branch_sha(workspace: Path, branch: str) -> str | None:
    """The branch tip sha, or None when the branch no longer exists."""
    out = _git(workspace, "rev-parse", "--verify", "--quiet", branch, check=False).stdout.strip()
    return out or None


def cleanup_after_merge(workspace: Path, side_task: SideTask) -> None:
    """Remove the worktree and delete the merged branch (never -D here)."""
    if side_task.worktree_path:
        try:
            remove_worktree(workspace, Path(side_task.worktree_path))
        except WorktreeError:
            logger.warning("Could not remove worktree %s", side_task.worktree_path, exc_info=True)
    if side_task.branch:
        try:
            delete_branch(workspace, side_task.branch)
        except WorktreeError:
            logger.warning("Could not delete branch %s", side_task.branch, exc_info=True)


__all__ = [
    "MergeOutcome",
    "WorktreeError",
    "branch_sha",
    "changed_files_vs_base",
    "cleanup_after_merge",
    "commit_all_changes",
    "create_worktree",
    "current_branch",
    "delete_branch",
    "has_uncommitted_changes",
    "head_sha",
    "is_branch_merged",
    "merge_side_branch",
    "repo_toplevel",
    "remove_worktree",
    "side_branch_name",
    "worktree_exists",
    "worktree_path_for",
    "worktrees_base_dir",
]

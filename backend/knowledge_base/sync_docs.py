"""
Documentation Sync Script

Clones or updates the llHorizonll/docscarmencloud GitHub repository
to maintain a local copy of Carmen Cloud documentation.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DocSyncer:
    """
    Handles cloning and syncing of documentation repositories.
    """

    DEFAULT_REPO_URL = "https://github.com/llHorizonll/docscarmencloud.git"
    DEFAULT_BRANCH = "main"

    def __init__(
        self,
        repo_url: str = DEFAULT_REPO_URL,
        local_path: Optional[str] = None,
        branch: str = DEFAULT_BRANCH,
    ):
        """
        Initialize the DocSyncer.

        Args:
            repo_url: GitHub repository URL to sync from
            local_path: Local directory to store the cloned repo
            branch: Git branch to sync (default: main)
        """
        self.repo_url = repo_url
        self.branch = branch

        if local_path is None:
            # Default to a 'docs_repo' folder in the knowledge_base directory
            base_dir = Path(__file__).parent
            self.local_path = base_dir / "docs_repo"
        else:
            self.local_path = Path(local_path)

    def _run_git_command(self, args: list[str], cwd: Optional[Path] = None) -> tuple[bool, str]:
        """
        Execute a git command and return success status and output.

        Args:
            args: Git command arguments (without 'git' prefix)
            cwd: Working directory for the command

        Returns:
            Tuple of (success: bool, output: str)
        """
        cmd = ["git"] + args
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.local_path,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "Git command timed out"
        except FileNotFoundError:
            return False, "Git is not installed or not in PATH"
        except Exception as e:
            return False, str(e)

    def is_repo_cloned(self) -> bool:
        """Check if the repository is already cloned locally."""
        git_dir = self.local_path / ".git"
        return git_dir.exists() and git_dir.is_dir()

    def clone(self) -> bool:
        """
        Clone the repository to the local path.

        Returns:
            True if clone was successful, False otherwise
        """
        if self.is_repo_cloned():
            logger.info(f"Repository already cloned at {self.local_path}")
            return True

        # Create parent directory if needed
        self.local_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Cloning {self.repo_url} to {self.local_path}")
        success, output = self._run_git_command(
            ["clone", "--branch", self.branch, "--single-branch", self.repo_url, str(self.local_path)],
            cwd=self.local_path.parent,
        )

        if success:
            logger.info("Clone completed successfully")
        else:
            logger.error(f"Clone failed: {output}")

        return success

    def pull(self) -> bool:
        """
        Pull latest changes from the remote repository.

        Returns:
            True if pull was successful, False otherwise
        """
        if not self.is_repo_cloned():
            logger.warning("Repository not cloned yet. Running clone first.")
            return self.clone()

        logger.info(f"Pulling latest changes from {self.branch}")

        # Fetch first
        success, output = self._run_git_command(["fetch", "origin", self.branch])
        if not success:
            logger.error(f"Fetch failed: {output}")
            return False

        # Reset to origin branch (handles any local changes)
        success, output = self._run_git_command(["reset", "--hard", f"origin/{self.branch}"])
        if not success:
            logger.error(f"Reset failed: {output}")
            return False

        logger.info("Pull completed successfully")
        return True

    def sync(self) -> bool:
        """
        Sync the repository - clone if not exists, pull if it does.

        Returns:
            True if sync was successful, False otherwise
        """
        if self.is_repo_cloned():
            return self.pull()
        else:
            return self.clone()

    def get_last_commit_info(self) -> Optional[dict]:
        """
        Get information about the last commit.

        Returns:
            Dictionary with commit info or None if not available
        """
        if not self.is_repo_cloned():
            return None

        success, commit_hash = self._run_git_command(["rev-parse", "HEAD"])
        if not success:
            return None

        success, commit_date = self._run_git_command(
            ["log", "-1", "--format=%ci"]
        )
        if not success:
            commit_date = "Unknown"

        success, commit_message = self._run_git_command(
            ["log", "-1", "--format=%s"]
        )
        if not success:
            commit_message = "Unknown"

        return {
            "hash": commit_hash,
            "date": commit_date,
            "message": commit_message,
        }

    def get_docs_path(self) -> Path:
        """
        Get the path to the documentation files.

        Returns:
            Path to the docs directory
        """
        # Check common documentation directory patterns
        common_dirs = ["docs", "content", "pages", "src/content", "src/docs"]

        for dir_name in common_dirs:
            docs_dir = self.local_path / dir_name
            if docs_dir.exists() and docs_dir.is_dir():
                return docs_dir

        # Fallback to repo root
        return self.local_path


def main():
    """
    Main entry point for syncing documentation.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync Carmen Cloud documentation from GitHub"
    )
    parser.add_argument(
        "--repo-url",
        default=DocSyncer.DEFAULT_REPO_URL,
        help="GitHub repository URL",
    )
    parser.add_argument(
        "--local-path",
        help="Local directory to store the repo",
    )
    parser.add_argument(
        "--branch",
        default=DocSyncer.DEFAULT_BRANCH,
        help="Git branch to sync",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Create syncer and run
    syncer = DocSyncer(
        repo_url=args.repo_url,
        local_path=args.local_path,
        branch=args.branch,
    )

    success = syncer.sync()

    if success:
        commit_info = syncer.get_last_commit_info()
        if commit_info:
            print(f"\nSync completed successfully!")
            print(f"  Commit: {commit_info['hash'][:8]}")
            print(f"  Date: {commit_info['date']}")
            print(f"  Message: {commit_info['message']}")
            print(f"  Docs path: {syncer.get_docs_path()}")
    else:
        print("\nSync failed. Check the logs for details.")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())

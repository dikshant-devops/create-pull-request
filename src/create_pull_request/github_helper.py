"""
GitHub API helper using PyGithub.

Provides high-level interface for GitHub operations including PR creation,
updates, and commit management with retry logic and rate limiting.
"""

import time
from typing import List, Optional, Dict
from github import Github, GithubException, Auth
from github.PullRequest import PullRequest
from github.Repository import Repository
from github.GithubRetry import GithubRetry
import urllib3

from .models import PROperation, CommitMetadata, GitIdentity
from .exceptions import GitHubAPIError, AuthenticationError


class GitHubHelper:
    """
    GitHub API wrapper with retry and rate limiting.
    Mirrors the TypeScript GitHubHelper class.
    """

    def __init__(self, token: str, repo_full_name: str):
        """
        Initialize GitHub API helper.

        Args:
            token: GitHub token for authentication
            repo_full_name: Repository in owner/repo format

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Configure retry logic: 3 retries with exponential backoff
            retry = GithubRetry(
                total=3,
                backoff_factor=2,
                status_forcelist=(500, 502, 503, 504)
            )

            # Initialize GitHub client with auth
            auth = Auth.Token(token)
            self.github = Github(auth=auth, retry=retry)

            # Get repository
            self.repo: Repository = self.github.get_repo(repo_full_name)
            self.repo_full_name = repo_full_name

            # Test authentication by getting repo info
            _ = self.repo.id

        except GithubException as e:
            if e.status == 401:
                raise AuthenticationError("Invalid GitHub token")
            elif e.status == 404:
                raise AuthenticationError(f"Repository not found: {repo_full_name}")
            else:
                raise GitHubAPIError("initialization", str(e))

    def create_or_update_pull_request(
        self,
        branch: str,
        base: str,
        title: str,
        body: str,
        draft: bool = False,
        maintainer_can_modify: bool = True
    ) -> PullRequest:
        """
        Create new pull request or update existing one.

        Args:
            branch: Head branch name
            base: Base branch name
            title: PR title
            body: PR body/description
            draft: Create as draft PR
            maintainer_can_modify: Allow maintainers to modify

        Returns:
            PullRequest object

        Raises:
            GitHubAPIError: If PR creation/update fails
        """
        try:
            # Try to create PR
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=branch,
                base=base,
                draft=draft,
                maintainer_can_modify=maintainer_can_modify
            )
            return pr

        except GithubException as e:
            # Check if PR already exists
            if e.status == 422 and "pull request already exists" in str(e).lower():
                # Find existing PR and update it
                pr = self._find_existing_pr(branch, base)
                if pr:
                    pr.edit(title=title, body=body)
                    return pr
                else:
                    raise GitHubAPIError(
                        "create_pull_request",
                        "PR already exists but couldn't be found"
                    )
            else:
                raise GitHubAPIError("create_pull_request", str(e))

    def _find_existing_pr(self, head: str, base: str) -> Optional[PullRequest]:
        """
        Find existing pull request by head and base branches.

        Args:
            head: Head branch
            base: Base branch

        Returns:
            PullRequest or None if not found
        """
        try:
            # Search for open PRs with matching head
            pulls = self.repo.get_pulls(
                state='open',
                head=f"{self.repo.owner.login}:{head}",
                base=base
            )

            for pr in pulls:
                return pr  # Return first match

            return None

        except GithubException:
            return None

    def get_pull_requests_by_head_branch(self, head_branch: str) -> List[PullRequest]:
        """
        Find all pull requests with given head branch.

        Args:
            head_branch: Head branch name

        Returns:
            List of PullRequest objects
        """
        try:
            pulls = self.repo.get_pulls(
                state='open',
                head=f"{self.repo.owner.login}:{head_branch}"
            )
            return list(pulls)
        except GithubException as e:
            raise GitHubAPIError("get_pull_requests", str(e))

    def update_pull_request_metadata(
        self,
        pr_number: int,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        reviewers: Optional[List[str]] = None,
        team_reviewers: Optional[List[str]] = None,
        milestone: Optional[int] = None
    ) -> None:
        """
        Update pull request metadata (labels, assignees, reviewers, milestone).

        Args:
            pr_number: PR number
            labels: Labels to add
            assignees: Assignees to add
            reviewers: Reviewers to request
            team_reviewers: Team reviewers to request
            milestone: Milestone number

        Raises:
            GitHubAPIError: If update fails
        """
        try:
            pr = self.repo.get_pull(pr_number)

            # Add labels
            if labels:
                issue = self.repo.get_issue(pr_number)
                issue.add_to_labels(*labels)

            # Add assignees
            if assignees:
                issue = self.repo.get_issue(pr_number)
                issue.add_to_assignees(*assignees)

            # Request reviewers
            if reviewers or team_reviewers:
                reviewer_list = reviewers or []
                team_reviewer_list = team_reviewers or []
                pr.create_review_request(
                    reviewers=reviewer_list,
                    team_reviewers=team_reviewer_list
                )

            # Set milestone
            if milestone and milestone > 0:
                issue = self.repo.get_issue(pr_number)
                milestone_obj = self.repo.get_milestone(milestone)
                issue.edit(milestone=milestone_obj)

        except GithubException as e:
            raise GitHubAPIError("update_pull_request_metadata", str(e))

    def convert_to_draft(self, pr_number: int) -> None:
        """
        Convert pull request to draft.
        Uses GraphQL API as REST API doesn't support this.

        Args:
            pr_number: PR number

        Raises:
            GitHubAPIError: If conversion fails
        """
        try:
            # Get PR to get node_id
            pr = self.repo.get_pull(pr_number)
            node_id = pr.raw_data.get('node_id')

            if not node_id:
                raise GitHubAPIError(
                    "convert_to_draft",
                    "Could not get PR node_id"
                )

            # Use GraphQL mutation to convert to draft
            mutation = """
            mutation ConvertPullRequestToDraft($pullRequestId: ID!) {
              convertPullRequestToDraft(input: {pullRequestId: $pullRequestId}) {
                pullRequest {
                  id
                  isDraft
                }
              }
            }
            """

            variables = {"pullRequestId": node_id}

            # Execute GraphQL mutation
            result = self._execute_graphql(mutation, variables)

            if not result or 'data' not in result:
                raise GitHubAPIError(
                    "convert_to_draft",
                    "GraphQL mutation failed"
                )

        except GithubException as e:
            raise GitHubAPIError("convert_to_draft", str(e))

    def _execute_graphql(self, query: str, variables: Dict) -> Dict:
        """
        Execute GraphQL query.

        Args:
            query: GraphQL query/mutation
            variables: Query variables

        Returns:
            Query result
        """
        # PyGithub doesn't have built-in GraphQL support
        # We need to use the underlying requester
        import json

        headers = {
            "Authorization": f"token {self.github._Github__requester.auth.token}",
            "Content-Type": "application/json"
        }

        payload = {
            "query": query,
            "variables": variables
        }

        response = self.github._Github__requester.requestJsonAndCheck(
            "POST",
            "https://api.github.com/graphql",
            input=payload,
            headers=headers
        )

        return response

    def create_signed_commit(
        self,
        tree_sha: str,
        parent_shas: List[str],
        message: str,
        author: GitIdentity,
        committer: Optional[GitIdentity] = None
    ) -> str:
        """
        Create commit via GitHub API (signed by GitHub).

        Args:
            tree_sha: Tree SHA
            parent_shas: Parent commit SHAs
            message: Commit message
            author: Author identity
            committer: Committer identity (defaults to author)

        Returns:
            Created commit SHA

        Raises:
            GitHubAPIError: If commit creation fails
        """
        try:
            from github.InputGitAuthor import InputGitAuthor
            from datetime import datetime

            # Create author object
            git_author = InputGitAuthor(
                name=author.name,
                email=author.email,
                date=datetime.now().isoformat()
            )

            # Create committer object
            if committer:
                git_committer = InputGitAuthor(
                    name=committer.name,
                    email=committer.email,
                    date=datetime.now().isoformat()
                )
            else:
                git_committer = git_author

            # Get tree object
            tree = self.repo.get_git_tree(tree_sha)

            # Get parent commits
            parents = [self.repo.get_git_commit(sha) for sha in parent_shas]

            # Create commit
            commit = self.repo.create_git_commit(
                message=message,
                tree=tree,
                parents=parents,
                author=git_author,
                committer=git_committer
            )

            return commit.sha

        except GithubException as e:
            raise GitHubAPIError("create_signed_commit", str(e))

    def update_branch_reference(
        self,
        ref: str,
        sha: str,
        force: bool = False
    ) -> None:
        """
        Update branch reference to point to commit.

        Args:
            ref: Reference name (e.g., 'heads/branch-name')
            sha: Commit SHA
            force: Force update

        Raises:
            GitHubAPIError: If update fails
        """
        try:
            full_ref = f"refs/{ref}" if not ref.startswith("refs/") else ref

            try:
                # Try to update existing ref
                git_ref = self.repo.get_git_ref(ref)
                git_ref.edit(sha, force=force)
            except GithubException as e:
                if e.status == 404:
                    # Ref doesn't exist, create it
                    self.repo.create_git_ref(full_ref, sha)
                else:
                    raise

        except GithubException as e:
            raise GitHubAPIError("update_branch_reference", str(e))

    def get_repository_parent(self) -> Optional[Repository]:
        """
        Get parent repository if this is a fork.

        Returns:
            Parent Repository or None if not a fork
        """
        try:
            if self.repo.fork and self.repo.parent:
                return self.repo.parent
            return None
        except GithubException:
            return None

    def check_rate_limit(self) -> None:
        """
        Check rate limit and wait if necessary.
        """
        try:
            rate_limit = self.github.get_rate_limit()
            core_limit = rate_limit.core

            if core_limit.remaining < 10:
                # Wait until reset time
                wait_time = (core_limit.reset - time.time()) + 10  # Add 10s buffer
                if wait_time > 0:
                    print(f"Rate limit low, waiting {wait_time:.0f} seconds...")
                    time.sleep(wait_time)

        except GithubException:
            # If we can't check rate limit, continue anyway
            pass

    def delete_branch(self, branch: str) -> None:
        """
        Delete branch from remote.

        Args:
            branch: Branch name to delete

        Raises:
            GitHubAPIError: If deletion fails
        """
        try:
            ref = f"heads/{branch}"
            git_ref = self.repo.get_git_ref(ref)
            git_ref.delete()
        except GithubException as e:
            if e.status != 404:  # Ignore if branch doesn't exist
                raise GitHubAPIError("delete_branch", str(e))

    def close(self) -> None:
        """Close GitHub client connection."""
        self.github.close()

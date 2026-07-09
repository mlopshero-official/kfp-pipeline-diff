"""GitHub module for interacting with the GitHub REST API without third-party dependencies.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


def make_github_request(
    url: str,
    method: str,
    token: str,
    data: Optional[Dict[str, Any]] = None
) -> Any:
    """Helper function to execute REST calls against the GitHub API using urllib.

    Args:
        url: The API endpoint URL.
        method: HTTP method (e.g., 'GET', 'POST', 'PATCH').
        token: GitHub API personal access or Actions runner token.
        data: Optional payload payload for the request.

    Returns:
        The decoded JSON response object, or an empty dict.
    """
    req = urllib.request.Request(
        url,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "kfp-pipeline-diff-action",
            "Content-Type": "application/json",
        },
    )

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    try:
        with urllib.request.urlopen(req, data=body) as response:
            res_data = response.read().decode("utf-8")
            return json.loads(res_data) if res_data else {}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise RuntimeError(f"GitHub API Error ({e.code}): {err_msg}")


def post_or_update_sticky_comment(
    repo: str,
    pr_number: int,
    token: str,
    body: str,
    api_url: str = "https://api.github.com",
    anchor: Optional[str] = None,
) -> None:
    """Finds an existing pipeline diff comment with our anchor and updates it,

    or appends a new one if not found.

    Args:
        repo: Repository identifier, e.g. 'owner/repo'.
        pr_number: The target pull request ID.
        token: GitHub access token.
        body: The markdown/HTML text to write.
        api_url: Base GitHub api endpoint.
        anchor: Unique sticky comment identifier anchor.
    """
    comments_url = f"{api_url}/repos/{repo}/issues/{pr_number}/comments"
    
    # Fallback to the generic anchor if not explicitly specified
    target_anchor = anchor or "<!-- kfp-pipeline-diff-sticky-comment-anchor -->"

    list_url = f"{comments_url}?per_page=100"

    try:
        comments = make_github_request(list_url, "GET", token)
    except Exception as e:
        print(f"⚠️ Warning: Failed to fetch issue comments to search for stickies: {e}")
        comments = []

    existing_comment_id = None
    if isinstance(comments, list):
        for comment in comments:
            comment_body = comment.get("body", "")
            if target_anchor in comment_body:
                existing_comment_id = comment.get("id")
                break

    if existing_comment_id:
        print(f"🔄 Updating existing sticky comment (ID: {existing_comment_id})...")
        update_url = f"{api_url}/repos/{repo}/issues/comments/{existing_comment_id}"
        make_github_request(update_url, "PATCH", token, {"body": body})
    else:
        print("➕ Posting a new sticky comment...")
        make_github_request(comments_url, "POST", token, {"body": body})

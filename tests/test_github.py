import json
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

from kfp_pipeline_diff.github import make_github_request, post_or_update_sticky_comment


def test_make_github_request_success():
    mock_response = MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.read.return_value = b'{"id": 123, "body": "hello"}'
    
    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        res = make_github_request(
            url="https://api.github.com/repos/foo/bar/comments",
            method="POST",
            token="fake-token",
            data={"body": "hello"}
        )
        
        assert res == {"id": 123, "body": "hello"}
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.method == "POST"
        assert req.get_header("Authorization") == "Bearer fake-token"
        assert req.get_header("Content-type") == "application/json"


def test_make_github_request_http_error():
    mock_fp = MagicMock()
    mock_fp.read.return_value = b'{"message": "Not Found"}'
    err = urllib.error.HTTPError(
        url="https://api.github.com",
        code=404,
        msg="Not Found",
        hdrs={},
        fp=mock_fp
    )
    
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RuntimeError) as exc_info:
            make_github_request(
                url="https://api.github.com/repos/foo/bar/comments",
                method="GET",
                token="fake-token"
            )
        assert "GitHub API Error (404):" in str(exc_info.value)
        assert "Not Found" in str(exc_info.value)


def test_post_or_update_sticky_comment_create():
    # 1. Fetch comments returns empty list
    mock_list_response = MagicMock()
    mock_list_response.__enter__.return_value = mock_list_response
    mock_list_response.read.return_value = b"[]"
    
    # 2. Post new comment returns comment dict
    mock_post_response = MagicMock()
    mock_post_response.__enter__.return_value = mock_post_response
    mock_post_response.read.return_value = b'{"id": 999, "body": "new body"}'
    
    # We configure urlopen to return list first, then post
    with patch("urllib.request.urlopen", side_effect=[mock_list_response, mock_post_response]) as mock_urlopen:
        post_or_update_sticky_comment(
            repo="foo/bar",
            pr_number=5,
            token="fake-token",
            body="my new comment body with <!-- my-anchor -->",
            anchor="<!-- my-anchor -->"
        )
        
        assert mock_urlopen.call_count == 2
        # First call: GET list of comments
        req1 = mock_urlopen.call_args_list[0][0][0]
        assert req1.method == "GET"
        assert "issues/5/comments?per_page=100" in req1.full_url
        
        # Second call: POST comment
        req2 = mock_urlopen.call_args_list[1][0][0]
        assert req2.method == "POST"
        assert "issues/5/comments" in req2.full_url


def test_post_or_update_sticky_comment_update():
    # 1. Fetch comments returns a list with an existing sticky comment
    comments_json = json.dumps([
        {"id": 111, "body": "other comment"},
        {"id": 222, "body": "some text\n<!-- my-anchor -->\nold text"}
    ]).encode("utf-8")
    mock_list_response = MagicMock()
    mock_list_response.__enter__.return_value = mock_list_response
    mock_list_response.read.return_value = comments_json
    
    # 2. Update existing comment returns updated comment dict
    mock_patch_response = MagicMock()
    mock_patch_response.__enter__.return_value = mock_patch_response
    mock_patch_response.read.return_value = b'{"id": 222, "body": "patched body"}'
    
    with patch("urllib.request.urlopen", side_effect=[mock_list_response, mock_patch_response]) as mock_urlopen:
        post_or_update_sticky_comment(
            repo="foo/bar",
            pr_number=5,
            token="fake-token",
            body="my updated body with <!-- my-anchor -->",
            anchor="<!-- my-anchor -->"
        )
        
        assert mock_urlopen.call_count == 2
        # First call: GET list
        req1 = mock_urlopen.call_args_list[0][0][0]
        assert req1.method == "GET"
        
        # Second call: PATCH comment
        req2 = mock_urlopen.call_args_list[1][0][0]
        assert req2.method == "PATCH"
        assert "comments/222" in req2.full_url


def test_post_or_update_sticky_comment_fetch_failure_posts_anyway():
    # Simulate fetch failure (e.g., 403 Forbidden on listing comments)
    mock_fp = MagicMock()
    mock_fp.read.return_value = b'{"message": "Forbidden"}'
    err = urllib.error.HTTPError(
        url="https://api.github.com",
        code=403,
        msg="Forbidden",
        hdrs={},
        fp=mock_fp
    )
    
    mock_post_response = MagicMock()
    mock_post_response.__enter__.return_value = mock_post_response
    mock_post_response.read.return_value = b'{"id": 777, "body": "posted anyway"}'
    
    with patch("urllib.request.urlopen", side_effect=[err, mock_post_response]) as mock_urlopen:
        post_or_update_sticky_comment(
            repo="foo/bar",
            pr_number=5,
            token="fake-token",
            body="my comment body with <!-- my-anchor -->",
            anchor="<!-- my-anchor -->"
        )
        
        assert mock_urlopen.call_count == 2
        req1 = mock_urlopen.call_args_list[0][0][0]
        assert req1.method == "GET"
        
        req2 = mock_urlopen.call_args_list[1][0][0]
        assert req2.method == "POST"


def test_post_or_update_sticky_comment_truncation():
    # Construct a payload body exceeding 65000 chars
    large_detailed_section = "<summary><b>🔍 Detailed Task Property Changes</b></summary>\n" + ("x" * 66000)
    body = "header info\n" + large_detailed_section + "\nsignature"
    
    mock_list_response = MagicMock()
    mock_list_response.__enter__.return_value = mock_list_response
    mock_list_response.read.return_value = b"[]"
    
    mock_post_response = MagicMock()
    mock_post_response.__enter__.return_value = mock_post_response
    mock_post_response.read.return_value = b'{"id": 888, "body": "posted"}'
    
    with patch("urllib.request.urlopen", side_effect=[mock_list_response, mock_post_response]) as mock_urlopen:
        post_or_update_sticky_comment(
            repo="foo/bar",
            pr_number=5,
            token="fake-token",
            body=body,
            anchor="<!-- my-anchor -->"
        )
        
        assert mock_urlopen.call_count == 2
        # Check that the second call (POST body) is indeed truncated
        req2 = mock_urlopen.call_args_list[1][0][0]
        assert req2.method == "POST"
        
        # Verify the post data payload
        post_data = mock_urlopen.call_args_list[1][1]["data"]
        # Convert bytes back to string to assert
        post_body_str = json.loads(post_data.decode("utf-8"))["body"]
        
        # The payload size should be significantly smaller than original 66000+
        assert len(post_body_str) < 65000
        assert "Report Truncated" in post_body_str
        assert "detailed changes truncated to fit size limits" in post_body_str

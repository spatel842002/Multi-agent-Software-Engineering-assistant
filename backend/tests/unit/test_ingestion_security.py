from __future__ import annotations

import pytest

from app.core.exceptions import UnprocessableIngestionError
from app.services.ingestion.security import validate_source_url


def test_https_public_host_is_allowed():
    assert validate_source_url("https://github.com/octocat/Hello-World.git")


def test_non_https_scheme_is_rejected():
    with pytest.raises(UnprocessableIngestionError, match="scheme"):
        validate_source_url("git://github.com/octocat/Hello-World.git")


def test_file_scheme_is_rejected():
    with pytest.raises(UnprocessableIngestionError, match="scheme"):
        validate_source_url("file:///etc/passwd")


def test_localhost_hostname_is_rejected():
    with pytest.raises(UnprocessableIngestionError, match="not allowed"):
        validate_source_url("https://localhost/repo.git")


def test_loopback_ip_is_rejected():
    with pytest.raises(UnprocessableIngestionError):
        validate_source_url("https://127.0.0.1/repo.git")


def test_cloud_metadata_ip_is_rejected():
    with pytest.raises(UnprocessableIngestionError):
        validate_source_url("https://169.254.169.254/latest/meta-data/")


def test_private_hosts_allowed_when_explicitly_opted_in():
    # Only used for local fixture-repo tests; production code paths never pass this.
    assert validate_source_url("https://127.0.0.1/repo.git", allow_private_hosts=True)


def test_missing_hostname_is_rejected():
    with pytest.raises(UnprocessableIngestionError, match="hostname"):
        validate_source_url("https:///no-host")

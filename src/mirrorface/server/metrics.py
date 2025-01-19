# TODO: Implement the metrics.

from mirrorface.common.hub import RepositoryRevisionPath


def total_requests_inc(repository_revision_path: RepositoryRevisionPath):
    pass


def cache_hit_inc(repository_revision_path: RepositoryRevisionPath):
    pass


def cache_miss_inc(repository_revision_path: RepositoryRevisionPath):
    pass


def fallback_requests_inc(repository_revision_path: RepositoryRevisionPath):
    pass


def fallback_upstream_error_inc(
    repository_revision_path: RepositoryRevisionPath, status_code: int
):
    pass


def fallback_total_bytes_inc(
    repository_revision_path: RepositoryRevisionPath, total_size: int
):
    pass

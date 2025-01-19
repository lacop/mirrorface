from prometheus_client import Counter

from mirrorface.common.hub import RepositoryRevisionPath

# All metrics have repository label, but not revision (too high cardinality).

total_requests = Counter(
    "mirrorface_total_requests",
    "Total requests per repository",
    ["repository"],
)
cache_hit = Counter(
    "mirrorface_cache_hit",
    "Cache hits per repository",
    ["repository"],
)
cache_miss = Counter(
    "mirrorface_cache_miss",
    "Cache misses per repository",
    ["repository"],
)
cache_total_bytes = Counter(
    "mirrorface_cache_total_bytes",
    "Total bytes served from cache per repository",
    ["repository"],
)
fallback_requests = Counter(
    "mirrorface_fallback_requests",
    "Fallback requests per repository",
    ["repository"],
)
fallback_upstream_error = Counter(
    "mirrorface_fallback_upstream_error",
    "Fallback upstream errors per repository and status code",
    ["repository", "status_code"],
)
fallback_total_bytes = Counter(
    "mirrorface_fallback_total_bytes",
    "Total bytes proxied upstream per repository",
    ["repository"],
)


def get_repo(repository_revision_path: RepositoryRevisionPath):
    return repository_revision_path.repository_revision.repository


def total_requests_inc(repository_revision_path: RepositoryRevisionPath):
    total_requests.labels(repository=get_repo(repository_revision_path)).inc()


def cache_hit_inc(repository_revision_path: RepositoryRevisionPath):
    cache_hit.labels(repository=get_repo(repository_revision_path)).inc()


def cache_miss_inc(repository_revision_path: RepositoryRevisionPath):
    cache_miss.labels(repository=get_repo(repository_revision_path)).inc()


def cache_total_bytes_inc(
    repository_revision_path: RepositoryRevisionPath, total_size: int
):
    cache_total_bytes.labels(repository=get_repo(repository_revision_path)).inc(
        total_size
    )


def fallback_requests_inc(repository_revision_path: RepositoryRevisionPath):
    fallback_requests.labels(repository=get_repo(repository_revision_path)).inc()


def fallback_upstream_error_inc(
    repository_revision_path: RepositoryRevisionPath, status_code: int
):
    fallback_upstream_error.labels(
        repository=get_repo(repository_revision_path), status_code=status_code
    ).inc()


def fallback_total_bytes_inc(
    repository_revision_path: RepositoryRevisionPath, total_size: int
):
    fallback_total_bytes.labels(repository=get_repo(repository_revision_path)).inc(
        total_size
    )

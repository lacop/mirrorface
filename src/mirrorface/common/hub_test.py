from mirrorface.common.hub import RepositoryRevision, RepositoryRevisionPath


def test_path_parsing():
    assert RepositoryRevisionPath.from_url_path(
        "user/repo/resolve/branch/path"
    ) == RepositoryRevisionPath(
        repository_revision=RepositoryRevision(
            repository="user/repo", revision="branch"
        ),
        path="path",
    )
    assert RepositoryRevisionPath.from_url_path(
        "user/repo/resolve/v1.2.3/path/can/be/nested.txt"
    ) == RepositoryRevisionPath(
        repository_revision=RepositoryRevision(
            repository="user/repo", revision="v1.2.3"
        ),
        path="path/can/be/nested.txt",
    )
    assert RepositoryRevisionPath.from_url_path(
        "user/repo/resolve/0123456abcdef/path"
    ) == RepositoryRevisionPath(
        repository_revision=RepositoryRevision(
            repository="user/repo", revision="0123456abcdef"
        ),
        path="path",
    )

    assert RepositoryRevisionPath.from_url_path("user/repo/resolve/branch") is None
    assert RepositoryRevisionPath.from_url_path("user/repo/resolve/branch/") is None
    assert (
        RepositoryRevisionPath.from_url_path("user/repo/not-resolve/branch/path")
        is None
    )

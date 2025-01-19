import os

import pytest

from mirrorface.common.hub import RepositoryRevision
from mirrorface.common.storage import (
    FullManifest,
    Manifest,
    RedirectManifest,
    blob_path,
    load_full_manifest,
    manifest_path,
)


@pytest.fixture()
def temp_storage_root(tmp_path_factory):
    temp_dir = tmp_path_factory.mktemp("mirrorface")
    # Make sure the directories exist.
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "blob"), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "manifest"), exist_ok=True)
    return temp_dir


def test_blob_path():
    assert blob_path("/root", "0123abcd") == "/root/blob/0123abcd"


def test_manifest_path():
    assert (
        manifest_path(
            "/root", RepositoryRevision(repository="user/repo", revision="main")
        )
        == "/root/manifest/user--repo__main.json"
    )
    assert (
        manifest_path(
            "/root",
            RepositoryRevision(repository="user/repo--invalid", revision="main"),
        )
        is None
    )
    assert (
        manifest_path(
            "/root",
            RepositoryRevision(repository="user--invalid/repo", revision="main"),
        )
        is None
    )
    assert (
        manifest_path(
            "/root",
            RepositoryRevision(repository="user/repo", revision="main--invalid"),
        )
        is None
    )
    assert (
        manifest_path(
            "/root", RepositoryRevision(repository="user/repo", revision="some/branch")
        )
        == "/root/manifest/user--repo__some--branch.json"
    )


def test_load_full_manifest_full(temp_storage_root):
    full_manifest = FullManifest(
        revision_hash="hash1", files={"file1": "filehash1", "file2": "filehash2"}
    )

    hash1 = RepositoryRevision(repository="user/repo", revision="hash1")
    hash1_path = manifest_path(temp_storage_root, hash1)
    assert hash1_path is not None
    with open(hash1_path, "w") as f:
        f.write(Manifest(manifest=full_manifest).model_dump_json())

    m = load_full_manifest(temp_storage_root, hash1)
    assert m == full_manifest


def test_load_full_manifest_redirect(temp_storage_root):
    full_manifest = FullManifest(
        revision_hash="hash1", files={"file1": "filehash1", "file2": "filehash2"}
    )
    redirect_manifest = RedirectManifest(revision_hash="hash1")

    hash1 = RepositoryRevision(repository="user/repo", revision="hash1")
    hash1_path = manifest_path(temp_storage_root, hash1)
    assert hash1_path is not None
    with open(hash1_path, "w") as f:
        f.write(Manifest(manifest=full_manifest).model_dump_json())
    main = RepositoryRevision(repository="user/repo", revision="main")
    main_path = manifest_path(temp_storage_root, main)
    assert main_path is not None
    with open(main_path, "w") as f:
        f.write(Manifest(manifest=redirect_manifest).model_dump_json())

    m = load_full_manifest(temp_storage_root, main)
    assert m == full_manifest


def test_load_full_manifest_unexpected_hash(temp_storage_root):
    full_manifest = FullManifest(
        revision_hash="hash1", files={"file1": "filehash1", "file2": "filehash2"}
    )

    hash2 = RepositoryRevision(repository="user/repo", revision="hash2")
    hash2_path = manifest_path(temp_storage_root, hash2)
    assert hash2_path is not None
    with open(hash2_path, "w") as f:
        f.write(Manifest(manifest=full_manifest).model_dump_json())

    with pytest.raises(Exception):
        load_full_manifest(temp_storage_root, hash2)


def test_load_full_manifest_redirect_missing(temp_storage_root):
    redirect_manifest = RedirectManifest(revision_hash="hash1")

    main = RepositoryRevision(repository="user/repo", revision="main")
    main_path = manifest_path(temp_storage_root, main)
    assert main_path is not None
    with open(main_path, "w") as f:
        f.write(Manifest(manifest=redirect_manifest).model_dump_json())

    with pytest.raises(FileNotFoundError):
        load_full_manifest(temp_storage_root, main)


def test_load_full_manifest_redirect_to_redirect(temp_storage_root):
    redirect_manifest = RedirectManifest(revision_hash="hash1")

    main = RepositoryRevision(repository="user/repo", revision="main")
    main_path = manifest_path(temp_storage_root, main)
    assert main_path is not None
    with open(main_path, "w") as f:
        f.write(Manifest(manifest=redirect_manifest).model_dump_json())
    hash1 = RepositoryRevision(repository="user/repo", revision="hash1")
    hash1_path = manifest_path(temp_storage_root, hash1)
    assert hash1_path is not None
    with open(hash1_path, "w") as f:
        f.write(Manifest(manifest=redirect_manifest).model_dump_json())

    with pytest.raises(Exception):
        load_full_manifest(temp_storage_root, main)

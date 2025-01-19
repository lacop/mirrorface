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
    move_local_blobs,
    write_local_manifests,
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


def test_move_local_blobs(tmp_path_factory):
    snapshot_dir = tmp_path_factory.mktemp("snapshot")
    target_dir = tmp_path_factory.mktemp("target")

    os.makedirs(snapshot_dir, exist_ok=True)
    with open(snapshot_dir / "file1", "w") as f:
        f.write("file1")
    with open(snapshot_dir / "file2", "w") as f:
        f.write("file2")
    os.makedirs(snapshot_dir / "subdir", exist_ok=True)
    with open(snapshot_dir / "subdir/file1", "w") as f:
        f.write("file1")
    with open(snapshot_dir / "subdir/file3", "w") as f:
        f.write("file3")
    os.makedirs(snapshot_dir / ".cache/huggingface", exist_ok=True)
    with open(snapshot_dir / ".cache/huggingface/foo", "w") as f:
        f.write("should be skipped")

    file_hashes = move_local_blobs(snapshot_dir, target_dir)

    # Check the returned hashes / paths are ok.
    file1hash = "119c19f868a33109852c09d66f6a5c73a7cd52f38325020a461cd94a74edef88709fcbc547d96d0ad9da671260fc42322d177378bad7a285f5df03f8e28f8565"
    file2hash = "eb827f1c183373d14958e0253e58496455821fa747996f09d2670cb9f9ff17b5ef3346ffb9d122bf537fcc3bd6480fb916ed3e906763f3bc98b520626ef86329"
    file3hash = "b10ff867df18165a0e100d99cd3d27f845f7ef9ad84eeb627a53aabaea04805940c3693154b8a32541a31887dda9fb1e667e93307473b1c581021714768bd032"
    assert file_hashes == {
        "file1": file1hash,
        "file2": file2hash,
        "subdir/file1": file1hash,
        "subdir/file3": file3hash,
    }

    # Check the blobs were moved correctly.
    def assert_file_content(file_path, content):
        assert os.path.exists(file_path)
        with open(file_path, "r") as f:
            assert f.read() == content

    assert_file_content(target_dir / "blob" / file1hash, "file1")
    assert_file_content(target_dir / "blob" / file2hash, "file2")
    assert_file_content(target_dir / "blob" / file3hash, "file3")


def test_write_local_manifests(tmp_path_factory):
    target_dir = tmp_path_factory.mktemp("target")

    revision = RepositoryRevision(repository="user/repo", revision="hash1")
    original_revision = RepositoryRevision(repository="user/repo", revision="main")
    files = {
        "file1": "filehash1",
        "file2": "filehash2",
        "subdir/file1": "filehash1",
        "subdir/file3": "filehash3",
    }

    write_local_manifests(revision, original_revision, files, target_dir)

    manifest = load_full_manifest(target_dir, revision)
    assert manifest == FullManifest(revision_hash="hash1", files=files)
    assert manifest == load_full_manifest(target_dir, original_revision)

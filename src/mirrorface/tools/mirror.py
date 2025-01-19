# Mirrors a given HuggingFace repository.
#
# Usage:
#
#     uv run mirror \
#       --repository=prajjwal1/bert-tiny \
#       --revision=commit_hash \
#       --local_directory=/tmp/mirrorface \
#       --gcs_bucket=mirrorface-bucket-name
#
# The `revision` flag is optional and defaults to "main".
#
# Both `local_directory` and `gcs_bucket` are optional. If `local_directory` is
# not set a temporary directory will be used. This mostly makes sense when
# using gcs_bucket and don't care about the local files.
#
# When setting `gcs_bucket` you must have the `gcloud` CLI tool installed
# and authenticated so it has write access to the bucket.


import os
import subprocess
import tempfile
from typing import Optional

import huggingface_hub
from pydantic import Field
from pydantic_settings import BaseSettings

from mirrorface.common.hub import RepositoryRevision
from mirrorface.common.storage import (
    blob_path,
    manifest_path,
    move_local_blobs,
    write_local_manifests,
)


class Settings(BaseSettings, cli_parse_args=True):
    repository: str
    revision: str = Field(default="main")

    local_directory: Optional[str] = None
    gcs_bucket: Optional[str] = None


def normalize_repository_revision(
    repository_revision: RepositoryRevision,
) -> RepositoryRevision:
    repo_refs = huggingface_hub.list_repo_refs(repository_revision.repository)
    for branch in repo_refs.branches:
        if branch.name == repository_revision.revision:
            print(f"Resolved '{repository_revision}' to hash {branch.target_commit}")
            return RepositoryRevision(
                repository=repository_revision.repository, revision=branch.target_commit
            )
    print(
        f"Could not resolve '{repository_revision}' to a hash, assuming it already is one."
    )
    if len(repository_revision.revision) != 40:
        raise ValueError(
            f"Revision '{repository_revision.revision}' is not a 40-character hash."
        )
    if not all(c in "0123456789abcdef" for c in repository_revision.revision):
        raise ValueError(
            f"Revision '{repository_revision.revision}' contains invalid characters."
        )
    return repository_revision


def download_repo(repository_revision: RepositoryRevision) -> str:
    # Create temporary target directory.
    target_dir = tempfile.mkdtemp()
    print(f"Downloading {repository_revision} to {target_dir}...")
    huggingface_hub.snapshot_download(
        repo_id=repository_revision.repository,
        revision=repository_revision.revision,
        local_dir=target_dir,
    )
    print("Download complete.")
    return target_dir


# Note: Using `gcloud storage cp` via subprocess rather than the Python client
# library because that one doesn't have a progress bar which is useful for the
# large files.
def upload_many_files_to_gcs(files: list[str], gcs_target_directory: str):
    # Don't do too many at once, to avoid long command lines.
    FILES_PER_BATCH = 20
    for i in range(0, len(files), FILES_PER_BATCH):
        batch = files[i : i + FILES_PER_BATCH]
        print(f"Uploading {i}..{i + len(batch)} / {len(files)}:")
        subprocess.run(
            [
                "gcloud",
                "storage",
                "cp",
                # Content-addressed, if it exists it is the same, don't overwrite.
                "--no-clobber",
            ]
            + batch
            + [gcs_target_directory],
        )


# Upload files to GCS.
# Important: upload in the right order, all blobs before manifests, and
# full manifests before redirects. Otherwise the server might try to
# read blobs that are not yet uploaded or follow an invalid redirect.
def upload_to_gcs(
    gcs_bucket: str,
    local_directory: str,
    files: dict[str, str],
    repository_revision: RepositoryRevision,
    original_repository_revision: RepositoryRevision,
):
    def manifest_path_not_none(
        storage_root: str, repository_revision: RepositoryRevision
    ) -> str:
        s = manifest_path(storage_root, repository_revision)
        assert s is not None
        return s

    print(f"Uploading to GCS bucket {gcs_bucket}...")
    gcs_root = f"gs://{gcs_bucket}"
    # Upload blobs.
    upload_many_files_to_gcs(
        list(set(blob_path(local_directory, hash) for hash in files.values())),
        os.path.dirname(blob_path(gcs_root, "dummy")),
    )
    # Main manifest.
    upload_many_files_to_gcs(
        [manifest_path_not_none(local_directory, repository_revision)],
        manifest_path_not_none(gcs_root, repository_revision),
    )
    # Redirect manifest.
    if repository_revision != original_repository_revision:
        upload_many_files_to_gcs(
            [manifest_path_not_none(local_directory, original_repository_revision)],
            manifest_path_not_none(gcs_root, original_repository_revision),
        )
    print("GCS upload complete!")


def main():
    settings = Settings()  # pyright: ignore[reportCallIssue], pydantic-settings will initialize or throw

    original_repository_revision = RepositoryRevision(
        repository=settings.repository, revision=settings.revision
    )
    repository_revision = normalize_repository_revision(original_repository_revision)

    # Download the raw repository.
    local_snapshot = download_repo(repository_revision)

    # Convert to mirrorable format - blobs and manifests.
    local_directory = settings.local_directory or tempfile.mkdtemp()
    print(f"Converting to mirrorable format in {local_directory}...")
    files = move_local_blobs(local_snapshot, local_directory)
    write_local_manifests(
        repository_revision, original_repository_revision, files, local_directory
    )

    # Upload to GCS if requested.
    if settings.gcs_bucket:
        upload_to_gcs(
            settings.gcs_bucket,
            local_directory,
            files,
            repository_revision,
            original_repository_revision,
        )


if __name__ == "__main__":
    main()

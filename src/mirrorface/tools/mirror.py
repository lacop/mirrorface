# Mirrors a given HuggingFace repository.
#
# Usage:
#
#     uv run mirror \
#       --repository=prajjwal1/bert-tiny \
#       --local_directory=/tmp/mirrorface
#
# You can also set --revision=commit_hash, defaults to "main".
#
# TODO: Support GCS upload in the tool itself (order is important).


import tempfile
from typing import Optional

import huggingface_hub
from pydantic import Field
from pydantic_settings import BaseSettings

from mirrorface.common.hub import RepositoryRevision
from mirrorface.common.storage import (
    move_local_blobs,
    write_local_manifests,
)


class Settings(BaseSettings, cli_parse_args=True):
    repository: str
    revision: str = Field(default="main")

    local_directory: Optional[str] = None
    # TODO: Add & document.
    # gcs_bucket: Optional[str] = None


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


def main():
    settings = Settings()  # pyright: ignore (pydantic will initialize or throw)

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


if __name__ == "__main__":
    main()

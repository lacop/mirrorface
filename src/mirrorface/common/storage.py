# Local storage for mirrored models.
#
# We store the models in two types of files:
#   - The actual models files from HF Hub. These are stored as
#     content-addressed blobs (filename is SHA-512 hash of contents).
#   - Manifest files which contain the contents of the repository,
#     as a mapping from original paths to content hashes.

import hashlib
import logging
import os
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

from mirrorface.common.hub import RepositoryRevision

BLOB_DIRECTORY = "blob"
MANIFEST_DIRECTORY = "manifest"


def blob_path(storage_root: str, hash: str) -> str:
    return os.path.join(storage_root, BLOB_DIRECTORY, hash)


def manifest_path(
    storage_root: str, repository_revision: RepositoryRevision
) -> Optional[str]:
    repository_revision_string = repository_revision.path_safe_string()
    if repository_revision_string is None:
        return None
    return os.path.join(
        storage_root, MANIFEST_DIRECTORY, f"{repository_revision_string}.json"
    )


def get_file_hash(path: str) -> str:
    hash = hashlib.sha512()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hash.update(chunk)
    return hash.hexdigest()


# Manifest files are of two types:
#   - A full manifest, which contains the actual contents of the repository.
#   - A redirect manifest (used for non-hash revisions like "main" or "v1.0.0"),
#     which contains a reference to the full manifest.


class FullManifest(BaseModel):
    manifest_type: Literal["full"] = "full"
    # This is the hash of the manifest itself. It should match the filename,
    # we store it here because we return FullManifest to the caller and they
    # should not need to know the filename.
    revision_hash: str
    files: dict[str, str]


class RedirectManifest(BaseModel):
    manifest_type: Literal["redirect"] = "redirect"
    revision_hash: str


class Manifest(BaseModel):
    manifest: Union[FullManifest, RedirectManifest] = Field(
        discriminator="manifest_type",
    )


def load_full_manifest(
    storage_root: str,
    repository_revision: RepositoryRevision,
) -> Optional[FullManifest]:
    manifest_file = manifest_path(storage_root, repository_revision)
    if manifest_file is None:
        return None
    try:
        with open(manifest_file, "r") as f:
            manifest = Manifest.model_validate_json(f.read())
    except FileNotFoundError:
        # It's OK if we don't have the manifest, might not be mirrored yet.
        return None
    except Exception:
        logging.error(f"Error loading manifest {manifest_file}", exc_info=True)
        raise

    if manifest.manifest.manifest_type == "full":
        if manifest.manifest.revision_hash != repository_revision.revision:
            raise Exception(
                f"Full manifest points to invalid revision: {manifest.manifest.revision_hash}"
            )
        return manifest.manifest

    # Follow redirect.
    manifest_file = manifest_path(
        storage_root,
        RepositoryRevision(
            repository=repository_revision.repository,
            revision=manifest.manifest.revision_hash,
        ),
    )
    if manifest_file is None:
        # Repository name is valid (passed first check) so the hash must be invalid.
        raise Exception(
            f"Redirect manifest points to invalid revision: {manifest.manifest.revision_hash}"
        )
    try:
        with open(manifest_file, "r") as f:
            manifest = Manifest.model_validate_json(f.read())
    except Exception:
        # If we have redirect the hash it points to must be valid.
        logging.error(f"Error loading redirect manifest {manifest_file}", exc_info=True)
        raise

    if manifest.manifest.manifest_type != "full":
        raise Exception(
            f"Redirect manifest points to another redirect: {manifest_file}"
        )
    if manifest.manifest.revision_hash != manifest.manifest.revision_hash:
        raise Exception(
            f"Full manifest points to invalid revision: {manifest.manifest.revision_hash}"
        )
    return manifest.manifest


def move_local_blobs(local_snapshot: str, local_directory: str) -> dict[str, str]:
    # Move all files into local_directory/blobs/hash and return a mapping from original path to the hash.
    file_hashes = {}
    os.makedirs(
        os.path.dirname(blob_path(local_directory, "")),
        exist_ok=True,
    )
    for root, _, files in os.walk(local_snapshot):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, local_snapshot)

            # This has timestamps / changes on every run, and is not needed, just skip it
            # so we don't have to re-upload and overwrite manifests each time.
            print(relative_path)
            if relative_path.startswith(".cache/huggingface/"):
                continue

            file_hash = get_file_hash(file_path)
            blob_file_path = blob_path(local_directory, file_hash)
            if not os.path.exists(blob_file_path):
                os.rename(file_path, blob_file_path)
            file_hashes[relative_path] = file_hash
    return file_hashes


def write_local_manifests(
    repository_revision: RepositoryRevision,
    original_repository_revision: RepositoryRevision,
    files: dict[str, str],
    local_directory: str,
):
    # Full manifest.
    manifest = FullManifest(revision_hash=repository_revision.revision, files=files)
    full_manifest_path = manifest_path(local_directory, repository_revision)
    if full_manifest_path is None:
        raise ValueError(f"Invalid repository revision: {repository_revision}")
    os.makedirs(os.path.dirname(full_manifest_path), exist_ok=True)
    with open(full_manifest_path, "w") as f:
        f.write(Manifest(manifest=manifest).model_dump_json())

    if repository_revision.revision != original_repository_revision.revision:
        # Redirect manifest.
        redirect_manifest = RedirectManifest(revision_hash=repository_revision.revision)
        redirect_manifest_path = manifest_path(
            local_directory, original_repository_revision
        )
        if redirect_manifest_path is None:
            raise ValueError(
                f"Invalid original repository revision: {original_repository_revision}"
            )
        with open(redirect_manifest_path, "w") as f:
            f.write(Manifest(manifest=redirect_manifest).model_dump_json())

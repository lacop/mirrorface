import logging
from typing import Optional

from pydantic import BaseModel


class RepositoryRevision(BaseModel):
    """Identifier for HF Hub repository (user/repo_name) and revision (branch, tag or commit hash)."""

    repository: str
    revision: str

    def path_safe_string(self) -> Optional[str]:
        # Note: We could allow "--" in repository or revision if needed, would
        # just need to escape those somehow to avoid collisions.
        if "--" in self.repository or "--" in self.revision:
            logging.warning(
                f"Unexpected repository or revision: {self.repository}, {self.revision}"
            )
            return None
        repository = self.repository.replace("/", "--")
        revision = self.revision.replace("/", "--")
        return f"{repository}__{revision}"


class RepositoryRevisionPath(BaseModel):
    """Identifier for a file in a HF Hub repository: the repository, revision and path."""

    repository_revision: RepositoryRevision
    path: str

    @classmethod
    def from_url_path(cls, url_path: str) -> Optional["RepositoryRevisionPath"]:
        # Expected format is "<user>/<repo>/resolve/<revision>/<path>"
        parts = url_path.split("/", maxsplit=4)
        if len(parts) != 5 or parts[2] != "resolve":
            return None
        user, repo, _, revision, path = parts
        if not path:
            return None
        return cls(
            repository_revision=RepositoryRevision(
                repository=f"{user}/{repo}", revision=revision
            ),
            path=path,
        )

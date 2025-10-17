from __future__ import annotations

from dataclasses import dataclass

from src.domain.entities.image import ImageEntity
from src.infrastructure.database.repositories.history_repository import HistoryRepository
from src.infrastructure.database.repositories.image_repository import ImageRepository
from src.infrastructure.storage.supabase_storage import SupabaseStorage


@dataclass
class RevertImageUseCase:
    """
    Use case for reverting an image to a previous version.

    This doesn't actually delete any versions - it creates a new version
    that is a copy of the target version, maintaining the complete history.
    """

    storage: SupabaseStorage
    image_repo: ImageRepository
    history_repo: HistoryRepository

    def execute(self, user_id: str, target_version_id: str) -> ImageEntity:
        """
        Revert to a specific version by creating a new version with that image's content.

        Args:
            user_id: The user performing the revert
            target_version_id: The image ID of the version to revert to

        Returns:
            The new ImageEntity representing the reverted version

        Raises:
            ValueError: If the target version doesn't exist or user doesn't have access
        """
        # Get the target version
        target = self.image_repo.get(target_version_id)
        if target is None or target.user_id != user_id:
            raise ValueError("Target version not found or access denied")

        # Determine the root image
        root_id = target.root_image_id if target.root_image_id else target.id

        # Get current max version number for this root
        version_chain = self.image_repo.get_version_chain(root_id, user_id)
        next_version = max((v.version_number for v in version_chain), default=0) + 1

        # Download the target version's image data
        image_data = self.storage.download_to_numpy(target.path)

        # Upload as a new version (creates a copy)
        # Extract extension from target path
        ext = target.path.split(".")[-1] if "." in target.path else "png"
        stored = self.storage.upload_numpy(user_id=user_id, array=image_data, ext=ext)

        # Create new version entry
        entity = self.image_repo.create(
            user_id=user_id,
            path=stored.path,
            width=stored.width,
            height=stored.height,
            mime_type=stored.content_type,
            original_id=target_version_id,  # Parent is the version we're reverting to
            original_filename=target.original_filename,
            file_size=stored.size,
            root_image_id=root_id,
            parent_version_id=target_version_id,
            version_number=next_version,
            is_root=False,
        )

        # Record the revert operation in history
        self.history_repo.create(
            user_id=user_id,
            image_id=entity.id,
            operation_type="revert",
            parameters={
                "target_version_id": target_version_id,
                "target_version": target.version_number,
            },
            result_storage_path=entity.path,
            source_image_id=target_version_id,
            root_image_id=root_id,
        )

        return entity

    def get_version_history(self, user_id: str, root_image_id: str) -> list[dict]:
        """
        Get the complete version history for an image chain.

        Returns a list of version info with metadata useful for UI display.
        """
        # Verify user has access to this root image
        root = self.image_repo.get(root_image_id)
        if root is None or root.user_id != user_id:
            raise ValueError("Image not found or access denied")

        # Get all versions
        versions = self.image_repo.get_version_chain(root_image_id, user_id)

        # Get all edit history for this chain
        history = self.history_repo.list_by_root_image(root_image_id, user_id)
        history_by_image: dict[str, list] = {}
        for h in history:
            if h.image_id not in history_by_image:
                history_by_image[h.image_id] = []
            history_by_image[h.image_id].append(h)

        # Build response
        result = []
        for version in versions:
            edits = history_by_image.get(version.id, [])
            result.append(
                {
                    "id": version.id,
                    "version_number": version.version_number,
                    "is_root": version.is_root,
                    "created_at": version.created_at.isoformat(),
                    "width": version.width,
                    "height": version.height,
                    "file_size": version.file_size,
                    "parent_version_id": version.parent_version_id,
                    "operations": [
                        {
                            "operation_type": edit.operation_type,
                            "parameters": edit.parameters,
                            "created_at": edit.created_at.isoformat(),
                        }
                        for edit in edits
                    ],
                }
            )

        return result

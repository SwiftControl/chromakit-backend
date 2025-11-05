"""
Tests for the batch processing endpoint and use case.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.application.use_cases.batch_process_image import BatchProcessImageUseCase


class TestBatchProcessImageUseCase:
    """Test the batch processing use case."""

    def test_single_operation(self, mock_dependencies):
        """Test batch processing with a single operation."""
        storage, image_repo, history_repo, processing = mock_dependencies
        
        # Create a simple test image (100x100 white image)
        test_array = np.ones((100, 100, 3), dtype=np.float32)
        
        # Mock the repository and storage responses
        image_repo.get.return_value = self._create_mock_image("img_123", "user_1")
        storage.download_to_numpy.return_value = test_array
        storage.upload_numpy.return_value = self._create_mock_storage_result()
        image_repo.get_version_chain.return_value = []
        
        # Create use case and execute
        uc = BatchProcessImageUseCase(storage, image_repo, history_repo, processing)
        operations = [
            {"operation": "brightness", "params": {"factor": 1.2}}
        ]
        
        result = uc.execute("user_1", "img_123", operations)
        
        # Verify the operation was applied
        assert result is not None
        assert storage.download_to_numpy.call_count == 1
        assert storage.upload_numpy.call_count == 1
        assert history_repo.create.call_count == 1

    def test_multiple_operations(self, mock_dependencies):
        """Test batch processing with multiple operations."""
        storage, image_repo, history_repo, processing = mock_dependencies
        
        # Create a test image
        test_array = np.ones((100, 100, 3), dtype=np.float32) * 0.5
        
        image_repo.get.return_value = self._create_mock_image("img_123", "user_1")
        storage.download_to_numpy.return_value = test_array
        storage.upload_numpy.return_value = self._create_mock_storage_result()
        image_repo.get_version_chain.return_value = []
        
        uc = BatchProcessImageUseCase(storage, image_repo, history_repo, processing)
        operations = [
            {"operation": "brightness", "params": {"factor": 1.1}},
            {"operation": "log_contrast", "params": {"k": 1.5}},
            {"operation": "grayscale_luminosity", "params": {}},
        ]
        
        result = uc.execute("user_1", "img_123", operations)
        
        # Verify all operations were recorded
        assert result is not None
        assert storage.download_to_numpy.call_count == 1  # Only load root image once
        assert storage.upload_numpy.call_count == 1  # Only save final result
        
        # Verify history was recorded with all operations
        history_call = history_repo.create.call_args
        assert history_call[1]["operation_type"] == "batch_process"
        assert len(history_call[1]["parameters"]["operations"]) == 3

    def test_uses_root_image(self, mock_dependencies):
        """Test that batch processing always uses the root image."""
        storage, image_repo, history_repo, processing = mock_dependencies
        
        test_array = np.ones((100, 100, 3), dtype=np.float32)
        
        # Create a mock image that has a root_image_id (not the root itself)
        mock_image = self._create_mock_image("img_456", "user_1", root_id="img_123")
        mock_root = self._create_mock_image("img_123", "user_1")
        
        # Setup repository to return different images
        image_repo.get.side_effect = lambda id: mock_image if id == "img_456" else mock_root
        storage.download_to_numpy.return_value = test_array
        storage.upload_numpy.return_value = self._create_mock_storage_result()
        image_repo.get_version_chain.return_value = []
        
        uc = BatchProcessImageUseCase(storage, image_repo, history_repo, processing)
        operations = [{"operation": "brightness", "params": {"factor": 1.1}}]
        
        result = uc.execute("user_1", "img_456", operations)
        
        # Verify we fetched both the current image and the root
        assert image_repo.get.call_count >= 2
        # Verify the history records the root as source
        history_call = history_repo.create.call_args
        assert history_call[1]["source_image_id"] == "img_123"
        assert history_call[1]["root_image_id"] == "img_123"

    def test_invalid_operation(self, mock_dependencies):
        """Test that invalid operations raise ValueError."""
        storage, image_repo, history_repo, processing = mock_dependencies
        
        image_repo.get.return_value = self._create_mock_image("img_123", "user_1")
        storage.download_to_numpy.return_value = np.ones((100, 100, 3), dtype=np.float32)
        
        uc = BatchProcessImageUseCase(storage, image_repo, history_repo, processing)
        operations = [{"operation": "invalid_operation", "params": {}}]
        
        with pytest.raises(ValueError, match="Unsupported operation"):
            uc.execute("user_1", "img_123", operations)

    def test_unauthorized_access(self, mock_dependencies):
        """Test that users can't process images they don't own."""
        storage, image_repo, history_repo, processing = mock_dependencies
        
        # Image belongs to user_2, but user_1 tries to process it
        image_repo.get.return_value = self._create_mock_image("img_123", "user_2")
        
        uc = BatchProcessImageUseCase(storage, image_repo, history_repo, processing)
        operations = [{"operation": "brightness", "params": {"factor": 1.1}}]
        
        with pytest.raises(ValueError, match="Image not found"):
            uc.execute("user_1", "img_123", operations)

    def test_channel_operations(self, mock_dependencies):
        """Test channel manipulation operations."""
        storage, image_repo, history_repo, processing = mock_dependencies
        
        test_array = np.ones((100, 100, 3), dtype=np.float32) * 0.5
        
        image_repo.get.return_value = self._create_mock_image("img_123", "user_1")
        storage.download_to_numpy.return_value = test_array
        storage.upload_numpy.return_value = self._create_mock_storage_result()
        image_repo.get_version_chain.return_value = []
        
        uc = BatchProcessImageUseCase(storage, image_repo, history_repo, processing)
        operations = [
            {"operation": "channel_red", "params": {"enabled": True}},
            {"operation": "brightness", "params": {"factor": 1.2}},
        ]
        
        result = uc.execute("user_1", "img_123", operations)
        
        assert result is not None
        assert storage.upload_numpy.call_count == 1

    # Helper methods
    def _create_mock_image(self, img_id: str, user_id: str, root_id: str | None = None):
        """Create a mock image entity."""
        from unittest.mock import Mock
        
        img = Mock()
        img.id = img_id
        img.user_id = user_id
        img.root_image_id = root_id
        img.original_filename = "test.png"
        img.path = f"images/{img_id}.png"
        img.width = 100
        img.height = 100
        img.mime_type = "image/png"
        img.file_size = 10000
        img.version_number = 1
        img.is_root = root_id is None
        img.base_image_id = None
        return img

    def _create_mock_storage_result(self):
        """Create a mock storage upload result."""
        from unittest.mock import Mock
        
        result = Mock()
        result.path = "images/processed.png"
        result.width = 100
        result.height = 100
        result.content_type = "image/png"
        result.size = 10000
        return result


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for testing."""
    from unittest.mock import Mock
    
    storage = Mock()
    image_repo = Mock()
    history_repo = Mock()
    
    # Create a real ProcessingService instance for testing
    from src.domain.services.processing_service import ProcessingService
    processing = ProcessingService()
    
    # Mock the create methods to return mock entities
    from datetime import datetime
    
    def create_image_mock(**kwargs):
        mock = Mock()
        mock.id = "img_new"
        mock.user_id = kwargs.get("user_id")
        mock.path = kwargs.get("path")
        mock.width = kwargs.get("width")
        mock.height = kwargs.get("height")
        mock.mime_type = kwargs.get("mime_type")
        mock.created_at = datetime.now()
        mock.original_id = kwargs.get("original_id")
        mock.original_filename = kwargs.get("original_filename")
        mock.file_size = kwargs.get("file_size")
        mock.root_image_id = kwargs.get("root_image_id")
        mock.parent_version_id = kwargs.get("parent_version_id")
        mock.version_number = kwargs.get("version_number")
        mock.is_root = kwargs.get("is_root")
        mock.base_image_id = kwargs.get("base_image_id")
        return mock
    
    image_repo.create.side_effect = create_image_mock
    
    def create_history_mock(**kwargs):
        mock = Mock()
        mock.id = "hist_new"
        return mock
    
    history_repo.create.side_effect = create_history_mock
    
    return storage, image_repo, history_repo, processing

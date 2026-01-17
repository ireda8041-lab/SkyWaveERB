
from unittest.mock import patch

import pytest

from services.client_service import ClientService


class TestClientService:
    @pytest.fixture
    def service(self, mock_repo):
        return ClientService(mock_repo)

    def test_create_client(self, service, mock_repo, sample_client_data):
        # Setup
        mock_repo.create_client.return_value = sample_client_data

        # Action
        result = service.create_client(sample_client_data)

        # Assert
        assert result.name == "Test Client"
        mock_repo.create_client.assert_called_once_with(sample_client_data)

    def test_get_client_by_id(self, service, mock_repo, sample_client_data):
        # Setup
        client_id = "client_123"
        mock_repo.get_client_by_id.return_value = sample_client_data

        # Action
        result = service.get_client_by_id(client_id)

        # Assert
        assert result == sample_client_data
        mock_repo.get_client_by_id.assert_called_once_with(client_id)

    def test_update_client(self, service, mock_repo, sample_client_data):
        # Setup
        client_id = "client_123"
        update_data = {"phone": "01111111111"}
        mock_repo.get_client_by_id.return_value = sample_client_data

        mock_repo.update_client.return_value = sample_client_data.model_copy(update=update_data)

        # Action (mocking app_signals to avoid emission errors during test)
        with patch('services.client_service.app_signals'):
            result = service.update_client(client_id, update_data)

        # Assert
        assert result.phone == "01111111111"
        assert result.name == "Test Client"  # unchanged
        mock_repo.update_client.assert_called_once()

    def test_delete_client(self, service, mock_repo):
        # Setup
        client_id = "client_123"
        mock_repo.delete_client_permanently.return_value = True

        # Action
        with patch('services.client_service.app_signals'):
            result = service.delete_client(client_id)

        # Assert
        assert result is True
        mock_repo.delete_client_permanently.assert_called_once_with(client_id)

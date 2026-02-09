from unittest.mock import patch

import pytest

from core import schemas
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
        with patch("services.client_service.app_signals"):
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
        with patch("services.client_service.app_signals"):
            result = service.delete_client(client_id)

        # Assert
        assert result is True
        mock_repo.delete_client_permanently.assert_called_once_with(client_id)

    def test_update_client_keeps_existing_logo_when_not_explicitly_deleted(
        self, service, mock_repo
    ):
        existing = schemas.Client(
            name="Client With Logo",
            logo_data="OLD_LOGO",
            has_logo=True,
            logo_last_synced="2026-02-01T10:00:00",
        )
        mock_repo.get_client_by_id.return_value = existing
        mock_repo.update_client.side_effect = lambda _cid, payload: payload

        with (
            patch("services.client_service.app_signals"),
            patch("services.client_service.notify_operation"),
        ):
            updated = service.update_client("client_1", {"phone": "01010101010", "logo_data": ""})

        assert updated is not None
        assert updated.logo_data == "OLD_LOGO"
        assert updated.has_logo is True
        assert updated.logo_last_synced == "2026-02-01T10:00:00"

    def test_update_client_deletes_logo_only_with_explicit_sentinel(self, service, mock_repo):
        existing = schemas.Client(
            name="Client Delete Logo",
            logo_data="OLD_LOGO",
            has_logo=True,
            logo_last_synced="2026-02-01T10:00:00",
        )
        mock_repo.get_client_by_id.return_value = existing
        mock_repo.update_client.side_effect = lambda _cid, payload: payload

        with (
            patch("services.client_service.app_signals"),
            patch("services.client_service.notify_operation"),
        ):
            updated = service.update_client("client_1", {"logo_data": "__DELETE__"})

        assert updated is not None
        assert updated.logo_data == ""
        assert updated.has_logo is False

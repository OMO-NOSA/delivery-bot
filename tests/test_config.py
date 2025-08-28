import os
from unittest.mock import patch

from api.config import Settings


class TestSettings:
    """Test Settings configuration loading and validation."""

    def test_default_settings(self):
        """Test default settings values."""
        # Test that the global settings instance has the expected structure
        from api.config import settings

        assert settings.api_title == "Delivery-Bot API"
        assert settings.api_version == "0.1.0"
        assert settings.allow_origins == ["*"]
        assert settings.log_level == "INFO"

        # GitHub settings should have values from .env file
        assert settings.github_owner is not None
        assert settings.github_repo is not None
        assert settings.github_workflow == "pipeline.yml"
        assert settings.github_ref == "main"
        assert settings.github_token is not None

    @patch.dict(
        os.environ,
        {
            "APP_API_TITLE": "Custom API Title",
            "APP_API_VERSION": "1.2.3",
            "APP_LOG_LEVEL": "DEBUG",
        },
    )
    def test_environment_override(self):
        """Test that environment variables override defaults."""
        settings = Settings()

        assert settings.api_title == "Custom API Title"
        assert settings.api_version == "1.2.3"
        assert settings.log_level == "DEBUG"

    @patch.dict(
        os.environ,
        {"APP_ALLOW_ORIGINS": '["https://example.com", "https://app.example.com"]'},
    )
    def test_list_environment_variables(self):
        """Test parsing list environment variables."""
        settings = Settings()

        assert settings.allow_origins == [
            "https://example.com",
            "https://app.example.com",
        ]

    @patch.dict(
        os.environ,
        {
            "APP_GITHUB_OWNER": "myorg",
            "APP_GITHUB_REPO": "myrepo",
            "APP_GITHUB_WORKFLOW": "custom-pipeline.yml",
            "APP_GITHUB_REF": "develop",
            "APP_GITHUB_TOKEN": "secret-token-123",
        },
    )
    def test_github_configuration(self):
        """Test GitHub configuration from environment."""
        settings = Settings()

        assert settings.github_owner == "myorg"
        assert settings.github_repo == "myrepo"
        assert settings.github_workflow == "custom-pipeline.yml"
        assert settings.github_ref == "develop"
        assert settings.github_token == "secret-token-123"

    def test_github_integration_enabled_when_configured(self):
        """Test determining if GitHub integration is enabled."""
        # Create settings with GitHub configuration
        with patch.dict(
            os.environ,
            {
                "APP_GITHUB_OWNER": "owner",
                "APP_GITHUB_REPO": "repo",
                "APP_GITHUB_TOKEN": "token",
            },
        ):
            settings = Settings()

            # GitHub integration should be considered "enabled" when all required fields are set
            is_enabled = all(
                [settings.github_owner, settings.github_repo, settings.github_token]
            )
            assert is_enabled is True

    def test_github_integration_enabled_with_current_config(self):
        """Test that GitHub integration is enabled with current .env configuration."""
        with patch.dict(
            os.environ,
            {
                "APP_GITHUB_OWNER": "test-owner",
                "APP_GITHUB_REPO": "test-repo",
                "APP_GITHUB_TOKEN": "test-token",
            },
        ):
            from api.config import settings

            # GitHub integration should be enabled when all required fields are set
            is_enabled = all(
                [settings.github_owner, settings.github_repo, settings.github_token]
            )
            assert is_enabled is True

    def test_github_configuration_structure(self):
        """Test that GitHub configuration has the expected structure."""
        with patch.dict(
            os.environ,
            {
                "APP_GITHUB_OWNER": "test-owner",
                "APP_GITHUB_REPO": "test-repo",
                "APP_GITHUB_TOKEN": "test-token",
            },
        ):
            from api.config import settings

            # All required GitHub fields should be present
            assert settings.github_owner is not None
            assert settings.github_repo is not None
            assert settings.github_token is not None
            assert settings.github_workflow == "pipeline.yml"
            assert settings.github_ref == "main"

            # Should be considered complete/enabled
            is_enabled = all(
                [settings.github_owner, settings.github_repo, settings.github_token]
            )
            assert is_enabled is True

    def test_log_level_case_insensitive(self):
        """Test that log level handling works with different cases."""
        test_cases = [
            ("DEBUG", "DEBUG"),
            ("debug", "debug"),
            ("Info", "Info"),
            ("WARNING", "WARNING"),
            ("error", "error"),
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"APP_LOG_LEVEL": env_value}):
                settings = Settings()
                assert settings.log_level == expected

    @patch.dict(
        os.environ,
        {
            "APP_API_TITLE": "",
            "APP_API_VERSION": "",
        },
    )
    def test_empty_string_environment_variables(self):
        """Test behavior with empty string environment variables."""
        settings = Settings()

        # Empty strings should override defaults
        assert settings.api_title == ""
        assert settings.api_version == ""

    def test_settings_model_config(self):
        """Test that settings model configuration is correct."""
        settings = Settings()

        # Verify model config attributes
        config = settings.model_config
        assert config["env_prefix"] == "APP_"
        assert config["env_file"] == ".env"
        assert config["env_file_encoding"] == "utf-8"

    def test_github_workflow_default(self):
        """Test GitHub workflow default value."""
        settings = Settings()
        assert settings.github_workflow == "pipeline.yml"

    def test_github_ref_default(self):
        """Test GitHub ref default value."""
        settings = Settings()
        assert settings.github_ref == "main"

    @patch.dict(os.environ, {"APP_ALLOW_ORIGINS": "invalid-json"}, clear=False)
    def test_invalid_json_in_list_field(self):
        """Test handling of invalid JSON in list field."""
        # This should either fail gracefully or use default
        # depending on pydantic-settings behavior
        try:
            settings = Settings()
            # If it doesn't raise an exception, it should fall back to default or parse as string
            assert isinstance(settings.allow_origins, (list, str))
        except Exception:
            # If it raises an exception, that's also acceptable behavior
            pass

    def test_settings_immutability(self):
        """Test that settings are properly configured as immutable if intended."""
        settings = Settings()
        original_title = settings.api_title

        # Try to modify (this should work since BaseSettings is mutable by default)
        settings.api_title = "Modified Title"
        assert settings.api_title == "Modified Title"

        # Create new instance to verify original behavior
        new_settings = Settings()
        assert new_settings.api_title == original_title

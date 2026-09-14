import os
from unittest.mock import patch

from django.test import SimpleTestCase

from tutoring.strands_runtime import (
    CONNECT_TIMEOUT_SECONDS,
    MAX_MODEL_TOKENS,
    MAX_RETRY_ATTEMPTS,
    READ_TIMEOUT_SECONDS,
    create_bedrock_model,
)


class StrandsRuntimeTests(SimpleTestCase):
    @patch("boto3.Session")
    @patch("strands.models.BedrockModel")
    def test_missing_configuration_fails_before_construction(self, model_mock, session_mock):
        with patch.dict(os.environ, {"AWS_REGION": "", "BEDROCK_MODEL_ID": ""}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "AWS_REGION and BEDROCK_MODEL_ID"):
                create_bedrock_model(max_tokens=128, temperature=0.2)
        session_mock.assert_not_called()
        model_mock.assert_not_called()

    @patch("boto3.Session")
    @patch("strands.models.BedrockModel")
    def test_configuration_is_forwarded_to_strands(self, model_mock, session_mock):
        fake_session = object()
        session_mock.return_value = fake_session
        with patch.dict(
            os.environ,
            {
                "AWS_REGION": "eu-west-1",
                "BEDROCK_MODEL_ID": "custom.model.v1",
                "aws_access_key_id": "",
                "aws_secret_access_key": "",
                "aws_session_token": "",
            },
            clear=False,
        ):
            create_bedrock_model(max_tokens=512, temperature=0.35)

        session_mock.assert_called_once_with(region_name="eu-west-1")
        model_mock.assert_called_once()
        kwargs = model_mock.call_args.kwargs
        assert kwargs["boto_session"] is fake_session
        assert kwargs["region_name"] == "eu-west-1"
        assert kwargs["model_id"] == "custom.model.v1"
        assert kwargs["max_tokens"] == 512
        assert kwargs["temperature"] == 0.35
        assert kwargs["streaming"] is False
        config = kwargs["boto_client_config"]
        assert config.connect_timeout == CONNECT_TIMEOUT_SECONDS
        assert config.read_timeout == READ_TIMEOUT_SECONDS
        assert config.retries == {"max_attempts": MAX_RETRY_ATTEMPTS, "mode": "standard"}

    def test_invalid_output_limits_fail_before_sdk_construction(self):
        with patch.dict(
            os.environ,
            {"AWS_REGION": "us-east-1", "BEDROCK_MODEL_ID": "model"},
            clear=False,
        ), patch("boto3.Session") as session_mock, patch("strands.models.BedrockModel") as model_mock:
            for value in (0, -1, MAX_MODEL_TOKENS + 1, True, 1.5):
                with self.assertRaises(ValueError):
                    create_bedrock_model(max_tokens=value, temperature=0.2)
        session_mock.assert_not_called()
        model_mock.assert_not_called()

    @patch("boto3.Session")
    @patch("strands.models.BedrockModel")
    def test_explicit_credentials_are_forwarded(self, model_mock, session_mock):
        with patch.dict(
            os.environ,
            {
                "AWS_REGION": "us-east-1",
                "BEDROCK_MODEL_ID": "model",
                "aws_access_key_id": "test-access",
                "aws_secret_access_key": "test-secret",
                "aws_session_token": "test-session",
            },
            clear=False,
        ):
            create_bedrock_model(max_tokens=128, temperature=0)
        session_mock.assert_called_once_with(
            aws_access_key_id="test-access",
            aws_secret_access_key="test-secret",
            aws_session_token="test-session",
            region_name="us-east-1",
        )
        model_mock.assert_called_once()

    @patch("boto3.Session")
    @patch("strands.models.BedrockModel")
    def test_without_overrides_uses_default_boto_chain(self, model_mock, session_mock):
        with patch.dict(
            os.environ,
            {"AWS_REGION": "us-east-1", "BEDROCK_MODEL_ID": "model"},
            clear=True,
        ):
            create_bedrock_model(max_tokens=128, temperature=0)
        session_mock.assert_called_once_with(region_name="us-east-1")
        model_mock.assert_called_once()

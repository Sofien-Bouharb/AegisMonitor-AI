"""Tests for the Ollama text-generation client."""

import unittest
from unittest.mock import Mock, patch

import httpx

from ml.api.ollama_client import OllamaError, generate_text


class OllamaClientTests(unittest.TestCase):
    @patch("ml.api.ollama_client.httpx.post")
    def test_generate_text_success(self, mock_post):
        response = Mock()
        response.json.return_value = {"response": "Check CPU and memory."}
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        result = generate_text(
            "Analyze these metrics.",
            base_url="http://ollama:11434/",
            model="llama3.1:8b",
        )

        self.assertEqual(result, "Check CPU and memory.")
        mock_post.assert_called_once_with(
            "http://ollama:11434/api/generate",
            json={
                "model": "llama3.1:8b",
                "prompt": "Analyze these metrics.",
                "stream": False,
            },
            timeout=120.0,
        )

    def test_rejects_blank_prompt(self):
        with self.assertRaises(ValueError):
            generate_text("  ")

    def test_rejects_nonpositive_timeout(self):
        with self.assertRaises(ValueError):
            generate_text("Analyze metrics.", timeout=0)

    @patch("ml.api.ollama_client.httpx.post")
    def test_http_failure_raises_ollama_error(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("connection refused")

        with self.assertRaises(OllamaError):
            generate_text("Analyze metrics.")

    @patch("ml.api.ollama_client.httpx.post")
    def test_invalid_json_raises_ollama_error(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.side_effect = ValueError("invalid JSON")
        mock_post.return_value = response

        with self.assertRaises(OllamaError):
            generate_text("Analyze metrics.")

    @patch("ml.api.ollama_client.httpx.post")
    def test_missing_generated_text_raises_ollama_error(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"response": ""}
        mock_post.return_value = response

        with self.assertRaises(OllamaError):
            generate_text("Analyze metrics.")


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

import requests

from app import normatividad_client, worker


def _response(status, *, json_body=None, text=""):
    response = requests.Response()
    response.status_code = status
    if json_body is not None:
        import json

        response._content = json.dumps(json_body).encode()
    else:
        response._content = text.encode()
    return response


class ResponseMessageTest(unittest.TestCase):
    def test_validation_error_message_is_extracted(self):
        response = _response(422, json_body={
            "message": "The given data was invalid.",
            "errors": {"artifacts": ["No existe el artefacto esperado md en 2026/1/x.md."]},
        })
        self.assertEqual(
            normatividad_client._response_message(response),
            "No existe el artefacto esperado md en 2026/1/x.md.",
        )

    def test_message_is_single_line_and_bounded(self):
        response = _response(400, text="línea uno\nlínea dos " + "x" * 900)
        message = normatividad_client._response_message(response)
        self.assertTrue(message.startswith("línea uno línea dos x"))
        self.assertEqual(len(message), normatividad_client.LOGGED_MESSAGE_MAX_LENGTH)

    def test_client_error_is_logged_with_its_message(self):
        response = _response(422, json_body={"errors": {"artifacts": ["No existe el artefacto"]}})
        with self.assertLogs(normatividad_client.logger, level="WARNING") as captured:
            result = normatividad_client._request_with_retry(
                lambda: response, method="POST", url="https://x/queue/1/artifacts",
                timeout_label="callback",
            )
        self.assertIs(result, response)
        self.assertIn("devolvio 422: No existe el artefacto", captured.output[0])


class CapabilityLoggingTest(unittest.TestCase):
    def test_capabilities_are_logged_once_per_change(self):
        meta = {"release_id": "ocr-core-v0.5.1", "version": "0.5.1",
                "capabilities": {"document_title": True}}
        with (
            patch.object(worker, "CORE_CAPABILITIES_REQUIRED", True),
            patch.object(worker, "_last_capabilities_logged", None),
            patch.object(worker.ocr_core_client, "get_meta", side_effect=lambda: dict(meta)),
            patch.object(worker.logger, "info") as info,
        ):
            worker._validate_core_capabilities(set())
            worker._validate_core_capabilities(set())
            meta["release_id"] = "ocr-core-v0.5.2"
            worker._validate_core_capabilities(set())
        self.assertEqual(info.call_count, 2)


if __name__ == "__main__":
    unittest.main()

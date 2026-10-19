from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import shadow_core_client
from app import worker
from app.worker import _submit_shadow_job


class ShadowCoreClientTest(unittest.TestCase):
    def test_build_request_reuses_source_and_isolates_outputs(self) -> None:
        with patch.object(
            shadow_core_client,
            "OCR_SHADOW_OUTPUT_ROOT",
            "/shadow-cache/review",
        ):
            body = shadow_core_client.build_request(
                Path("/nfs-cache/_inbox/normatividad_42.pdf"),
                queue_id=42,
                artifacts={"pdf", "text"},
            )

        self.assertEqual(
            body["source"]["path"],
            "/nfs-cache/_inbox/normatividad_42.pdf",
        )
        for spec in body["artifacts"].values():
            self.assertTrue(spec["path"].startswith("/shadow-cache/review/queue-42-"))
            self.assertTrue(spec["overwrite"])
            self.assertNotIn("/nfs-cache", spec["path"])
        self.assertEqual(
            body["options"]["metadata"]["integration_mode"],
            "production-shadow",
        )

    def test_output_outside_shadow_cache_is_rejected(self) -> None:
        with patch.object(
            shadow_core_client,
            "OCR_SHADOW_OUTPUT_ROOT",
            "/nfs-cache/official",
        ):
            with self.assertRaises(ValueError):
                shadow_core_client.build_request(
                    Path("/nfs-cache/_inbox/document.pdf"),
                    queue_id=1,
                    artifacts={"pdf"},
                )

    def test_submit_uses_post_jobs_contract(self) -> None:
        response = Mock()
        response.json.return_value = {
            "job_id": "shadow-job",
            "status": "queued",
            "idempotent_reuse": False,
        }
        with (
            patch.object(shadow_core_client, "OCR_SHADOW_CORE_URL", "http://core-ocr:8000"),
            patch.object(shadow_core_client.requests, "post", return_value=response) as post,
        ):
            result = shadow_core_client.submit_job(
                Path("/nfs-cache/_inbox/document.pdf"),
                queue_id=7,
                artifacts={"text"},
            )

        self.assertEqual(result["job_id"], "shadow-job")
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], "http://core-ocr:8000/jobs")
        self.assertEqual(
            post.call_args.kwargs["json"]["source"]["path"],
            "/nfs-cache/_inbox/document.pdf",
        )

    def test_shadow_failure_never_escapes_to_official_flow(self) -> None:
        logger = Mock(spec=logging.Logger)
        with (
            patch.object(shadow_core_client, "enabled", return_value=True),
            patch.object(
                shadow_core_client,
                "submit_job",
                side_effect=RuntimeError("shadow unavailable"),
            ),
        ):
            result = _submit_shadow_job(
                Path("/nfs-cache/_inbox/document.pdf"),
                queue_id=9,
                needs_pdf=True,
                needs_text=True,
                worker_logger=logger,
            )

        self.assertIsNone(result)
        logger.warning.assert_called_once()

    def test_disabled_shadow_does_not_submit(self) -> None:
        logger = Mock(spec=logging.Logger)
        with (
            patch.object(shadow_core_client, "enabled", return_value=False),
            patch.object(shadow_core_client, "submit_job") as submit,
        ):
            result = _submit_shadow_job(
                Path("/nfs-cache/_inbox/document.pdf"),
                queue_id=10,
                needs_pdf=True,
                needs_text=True,
                worker_logger=logger,
            )

        self.assertIsNone(result)
        submit.assert_not_called()

    def test_shadow_failure_does_not_prevent_official_report(self) -> None:
        logger = Mock(spec=logging.Logger)
        item = {
            "queue_id": 77,
            "artifacts": {
                "requested": {"pdf": True, "text": False, "md": False},
                "expected": {"pdf_path": "review/official.pdf"},
            },
            "has_pdf": False,
        }

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)

            def download_source(_queue_id, destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"%PDF-1.4\n%%EOF\n")

            official_result = {
                "job_id": "official-job",
                "status": "done",
                "preflight": {"decision": "process"},
                "artifacts": {"pdf": {"written": True}},
            }
            with (
                patch.object(worker, "SHARED_CACHE_DIR", cache),
                patch.object(worker, "INBOX_DIR", cache / "_inbox"),
                patch.object(worker.normatividad_client, "mark_processing", return_value={}),
                patch.object(
                    worker.normatividad_client,
                    "download_source",
                    side_effect=download_source,
                ),
                patch.object(worker.normatividad_client, "report_artifacts") as report,
                patch.object(worker.normatividad_client, "fail") as fail,
                patch.object(worker.normatividad_client, "block") as block,
                patch.object(worker.normatividad_client, "skip") as skip,
                patch.object(worker.ocr_core_client, "submit_job", return_value="official-job"),
                patch.object(
                    worker.ocr_core_client,
                    "wait_for_job",
                    return_value=official_result,
                ),
                patch.object(shadow_core_client, "enabled", return_value=True),
                patch.object(
                    shadow_core_client,
                    "submit_job",
                    side_effect=RuntimeError("shadow unavailable"),
                ),
            ):
                worker._process_item(item, "test-worker", logger)

        report.assert_called_once()
        fail.assert_not_called()
        block.assert_not_called()
        skip.assert_not_called()


if __name__ == "__main__":
    unittest.main()

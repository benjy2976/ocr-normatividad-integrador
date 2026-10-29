import json
import logging
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from app import worker

CORE_META = {
    "release_id": "ocr-core-v0.5.0",
    "version": "0.5.0",
    "capabilities": {
        "artifact_schemas": {
            "text": "ocr.text.document.v1",
            "md": "ocr.markdown.document.v1",
        }
    },
}


class WorkerMarkdownTest(unittest.TestCase):
    def _item(self, *, pdf=True, text=True, md=True, has_md=False, md_path=True, force_md=False):
        requested = {"pdf": pdf, "text": text, "md": md}
        expected = {
            "pdf_path": "2026/41/source.pdf",
            "text_path": "2026/41/source.jsonl",
        }
        if md_path:
            expected["md_path"] = "2026/41/source.md"
        item = {
            "queue_id": 41,
            "status": "leased",
            "source": {"md5": "a" * 32},
            "artifacts": {"requested": requested, "expected": expected},
            "has_pdf": False,
            "has_text": False,
            "has_md": has_md,
        }
        if force_md:
            item["execution_request"] = {
                "attempt": 2,
                "requested_artifacts": requested,
                "reprocess_artifacts": {"pdf": False, "text": False, "md": True},
                "pdf_on_skip": "copy",
                "telemetry_level": "none",
            }
        return item

    def _run(self, item, *, result=None, meta=CORE_META, existing=()):
        logger = Mock(spec=logging.Logger)
        calls = {}
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            cache = Path(directory)
            for relative in existing:
                path = cache / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("previo")

            def download_source(_queue_id, destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"%PDF-1.4\n%%EOF\n")

            job = result or {
                "job_id": "core-job",
                "status": "done",
                "preflight": {"decision": "process"},
                "artifacts": {
                    name: {"written": True} for name in ("pdf", "text", "md")
                },
            }
            for target, value in (
                ("SHARED_CACHE_DIR", cache),
                ("INBOX_DIR", cache / "_inbox"),
                ("FORCE_REPROCESS_ENABLED", True),
                ("SOURCE_REUSE_ENABLED", False),
                ("TELEMETRY_FORWARD_ENABLED", False),
                ("CORE_CAPABILITIES_REQUIRED", False),
            ):
                stack.enter_context(patch.object(worker, target, value))
            calls["mark"] = stack.enter_context(patch.object(
                worker.normatividad_client, "mark_processing",
                return_value={"data": {**item, "status": "processing"}},
            ))
            stack.enter_context(patch.object(
                worker.normatividad_client, "download_source", side_effect=download_source
            ))
            calls["report"] = stack.enter_context(
                patch.object(worker.normatividad_client, "report_artifacts")
            )
            calls["skip"] = stack.enter_context(patch.object(worker.normatividad_client, "skip"))
            calls["submit"] = stack.enter_context(
                patch.object(worker.ocr_core_client, "submit_job", return_value="core-job")
            )
            stack.enter_context(
                patch.object(worker.ocr_core_client, "wait_for_job", return_value=job)
            )
            calls["meta"] = stack.enter_context(
                patch.object(worker.ocr_core_client, "get_meta", return_value=meta)
            )
            stack.enter_context(
                patch.object(worker.shadow_core_client, "enabled", return_value=False)
            )
            calls["cache"] = cache
            worker._process_item(item, "worker-1", logger)
            inbox = cache / "_inbox"
            calls["inbox_left"] = sorted(inbox.iterdir()) if inbox.exists() else []
        return calls

    def test_queue_without_markdown_keeps_the_current_behavior(self):
        calls = self._run(self._item(md=False))

        artifacts = calls["submit"].call_args.kwargs["artifacts"]
        self.assertEqual(set(artifacts), {"pdf", "text"})
        options = calls["submit"].call_args.kwargs["options"]
        self.assertNotIn("md_path", options["metadata"])
        callback = calls["report"].call_args.kwargs
        self.assertNotIn("md", callback["artifacts"])
        self.assertTrue(callback["finalize_queue"])
        self.assertEqual(callback["response_payload_json"]["unsupported_artifacts"], {})
        calls["meta"].assert_not_called()

    def test_enabled_markdown_is_requested_written_and_reported(self):
        calls = self._run(self._item())

        artifacts = calls["submit"].call_args.kwargs["artifacts"]
        md_path = calls["cache"] / "2026/41/source.md"
        self.assertEqual(artifacts["md"], {"path": str(md_path), "overwrite": False})
        options = calls["submit"].call_args.kwargs["options"]
        self.assertEqual(options["metadata"]["md_path"], "2026/41/source.md")
        callback = calls["report"].call_args.kwargs
        self.assertTrue(callback["artifacts"]["md"])
        self.assertTrue(callback["finalize_queue"])
        payload = callback["response_payload_json"]
        self.assertTrue(payload["produced_artifacts"]["md"])
        self.assertEqual(payload["storage"]["resolved_md_path"], str(md_path))
        self.assertFalse(payload["reprocessed_artifacts"]["md"])

    def test_forced_markdown_overwrites_and_is_reported_as_reprocessed(self):
        calls = self._run(
            self._item(pdf=False, text=False, has_md=True, force_md=True),
            existing=("2026/41/source.md",),
        )

        artifacts = calls["submit"].call_args.kwargs["artifacts"]
        self.assertEqual(set(artifacts), {"md"})
        self.assertTrue(artifacts["md"]["overwrite"])
        payload = calls["report"].call_args.kwargs["response_payload_json"]
        self.assertTrue(payload["reprocessed_artifacts"]["md"])

    def test_core_without_markdown_schema_stops_before_touching_the_queue(self):
        meta = {"capabilities": {"artifact_schemas": {"text": "ocr.text.document.v1"}}}
        with self.assertRaises(worker.CoreCapabilityError):
            self._run(self._item(), meta=meta)

    def test_cached_markdown_is_not_requested_again(self):
        calls = self._run(
            self._item(pdf=False, text=False, has_md=True),
            existing=("2026/41/source.md",),
        )

        calls["submit"].assert_not_called()
        callback = calls["report"].call_args.kwargs
        self.assertTrue(callback["artifacts"]["md"])
        self.assertTrue(callback["finalize_queue"])

    def test_native_text_document_is_not_skipped_when_markdown_is_requested(self):
        result = {
            "job_id": "core-job",
            "status": "done",
            "preflight": {"decision": "skip"},
            "artifacts": {"pdf": {"written": True}, "md": {"written": True}},
        }
        calls = self._run(self._item(text=False), result=result)

        calls["skip"].assert_not_called()
        self.assertTrue(calls["report"].call_args.kwargs["artifacts"]["md"])

    def test_markdown_not_written_by_core_does_not_finalize_the_queue(self):
        result = {
            "job_id": "core-job",
            "status": "done",
            "preflight": {"decision": "process"},
            "artifacts": {"pdf": {"written": True}, "text": {"written": True}},
        }
        calls = self._run(self._item(), result=result)

        callback = calls["report"].call_args.kwargs
        self.assertNotIn("md", callback["artifacts"])
        self.assertFalse(callback["finalize_queue"])

    def test_markdown_without_expected_path_fails_clearly(self):
        with self.assertRaisesRegex(RuntimeError, "artifacts.expected.md_path"):
            self._run(self._item(md_path=False))

    def _real_like_item(self, **document):
        item = self._item()
        # Forma tomada de la metadata real de producción (2026-10-29).
        item["regulation_file_id"] = 124200
        item["document"] = {"regulation_id": 132744, **document}
        item["queue"] = {"regulation_file": {
            "id": 124200, "file_idregulation": 132744, "file_name": "212000003462026.pdf",
            "regulation": {"id": 132744, "reg_title": " 000346-2026-GRH-ORA"},
        }}
        return item

    def test_explicit_markdown_title_is_forwarded_to_the_core(self):
        calls = self._run(self._real_like_item(
            markdown_title="Resolución 000346-2026-GRH-ORA - Tomo 1"
        ))

        options = calls["submit"].call_args.kwargs["options"]
        self.assertEqual(options["document_title"], "Resolución 000346-2026-GRH-ORA - Tomo 1")

    def test_title_fallback_uses_regulation_file_and_title(self):
        calls = self._run(self._real_like_item())

        options = calls["submit"].call_args.kwargs["options"]
        self.assertEqual(options["document_title"], "132744 - 124200 - 000346-2026-GRH-ORA")

    def test_title_is_single_line_and_bounded(self):
        item = self._real_like_item(markdown_title="Línea uno\n\tlínea dos  " + "x" * 600)
        title = worker._markdown_title(item, worker._text_artifact_metadata(item, None, None))
        self.assertTrue(title.startswith("Línea uno línea dos x"))
        self.assertEqual(len(title), worker.MARKDOWN_TITLE_MAX_LENGTH)
        self.assertTrue(title.isprintable())

    def test_without_data_no_title_is_sent_and_core_uses_the_file_name(self):
        calls = self._run(self._item())

        self.assertNotIn("document_title", calls["submit"].call_args.kwargs["options"])

    def test_jobs_without_markdown_do_not_send_a_title(self):
        item = self._real_like_item(markdown_title="Título")
        item["artifacts"]["requested"]["md"] = False
        calls = self._run(item)

        self.assertNotIn("document_title", calls["submit"].call_args.kwargs["options"])

    def test_inbox_uses_a_technical_name_and_is_cleaned(self):
        calls = self._run(self._real_like_item())

        source = calls["submit"].call_args.args[0]
        self.assertEqual(source.parent, calls["cache"] / "_inbox")
        self.assertRegex(source.name, r"^normatividad_41_[0-9a-f]{12}\.pdf$")
        self.assertEqual(calls["inbox_left"], [])

    def test_markdown_contract_fixtures_are_understood(self):
        fixture_path = (
            Path(__file__).parents[2]
            / "docs/contracts/normatividad-ocr-markdown/fixtures.json"
        )
        fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
        queue = fixtures["queue_with_markdown"]
        reprocess = fixtures["queue_reprocess_markdown"]

        self.assertTrue(worker._requested_artifacts(queue)["md"])
        self.assertTrue(worker._reprocess_artifacts(reprocess)["md"])
        with tempfile.TemporaryDirectory() as directory, patch.object(
            worker, "SHARED_CACHE_DIR", Path(directory)
        ):
            md_path = worker._resolve_expected_artifact_path(queue, "md")
            pdf_path = worker._resolve_expected_artifact_path(queue, "pdf")
        self.assertEqual(md_path.parent, pdf_path.parent)
        self.assertEqual(md_path.stem, queue["source"]["md5"])
        self.assertEqual(md_path.suffix, ".md")
        self.assertFalse(fixtures["callback_markdown_missing"]["finalize_queue"])
        metadata = worker._text_artifact_metadata(queue, None, None)
        self.assertEqual(worker._markdown_title(queue, metadata),
                         queue["document"]["markdown_title"])

    def test_jobs_without_markdown_keep_their_metadata_and_idempotency(self):
        item = self._item(md=False)
        base = worker._text_artifact_metadata(item, None, None)
        self.assertNotIn("md_path", base)
        with_md = worker._text_artifact_metadata(item, None, None, Path("/nfs-cache/x.md"))
        self.assertIn("md_path", with_md)


if __name__ == "__main__":
    unittest.main()

import logging
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from app import ocr_core_client, worker


class WorkerReprocessTest(unittest.TestCase):
    def test_shared_contract_fixtures_are_understood(self):
        fixture_path = (
            Path(__file__).parents[2]
            / "docs/contracts/normatividad-ocr-reproceso/fixtures.json"
        )
        fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))

        legacy = worker._requested_artifacts(fixtures["queue_basic"])
        forced_text = worker._reprocess_artifacts(fixtures["queue_reprocess_text"])

        self.assertEqual(legacy, {"pdf": True, "text": False, "md": False})
        self.assertEqual(forced_text, {"pdf": False, "text": True, "md": False})

    def _item(self, *, reprocess=None):
        requested = {"pdf": True, "text": True, "md": False}
        return {
            "queue_id": 41,
            "status": "leased",
            "source": {"md5": "a" * 32},
            "artifacts": {
                "requested": requested,
                "expected": {
                    "pdf_path": "2026/41/source.pdf",
                    "text_path": "2026/41/source.jsonl",
                },
            },
            "execution_request": {
                "attempt": 2,
                "requested_artifacts": requested,
                "reprocess_artifacts": reprocess
                or {"pdf": False, "text": False, "md": False},
                "pdf_on_skip": "reuse",
                "telemetry_level": "summary_and_pages",
            },
            "has_pdf": True,
            "has_text": True,
        }

    def test_idempotency_changes_with_attempt_and_request(self):
        item = self._item()
        first = worker._idempotency_key(item, {"metadata": {}})
        same = worker._idempotency_key(item, {"metadata": {}})
        item["execution_request"]["attempt"] = 3
        later = worker._idempotency_key(item, {"metadata": {}})

        self.assertEqual(first, same)
        self.assertNotEqual(first, later)
        self.assertLessEqual(len(first), 128)

    def test_force_pdf_bypasses_cache_and_sets_only_pdf_overwrite(self):
        item = self._item(
            reprocess={"pdf": True, "text": False, "md": False}
        )
        logger = Mock(spec=logging.Logger)

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            pdf = cache / "2026/41/source.pdf"
            text = cache / "2026/41/source.jsonl"
            pdf.parent.mkdir(parents=True)
            pdf.write_bytes(b"old-pdf")
            text.write_text("old-text")

            def download_source(_queue_id, destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"%PDF-1.4\n%%EOF\n")

            result = {
                "job_id": "core-job",
                "status": "done",
                "preflight": {"decision": "process"},
                "artifacts": {"pdf": {"written": True}},
            }
            with (
                patch.object(worker, "SHARED_CACHE_DIR", cache),
                patch.object(worker, "INBOX_DIR", cache / "_inbox"),
                patch.object(worker, "FORCE_REPROCESS_ENABLED", True),
                patch.object(worker, "SOURCE_REUSE_ENABLED", False),
                patch.object(worker, "TELEMETRY_FORWARD_ENABLED", False),
                patch.object(worker.normatividad_client, "mark_processing", return_value={
                    "data": {**item, "status": "processing"}
                }),
                patch.object(worker.normatividad_client, "download_source", side_effect=download_source),
                patch.object(worker.normatividad_client, "report_artifacts") as report,
                patch.object(worker.ocr_core_client, "submit_job", return_value="core-job") as submit,
                patch.object(worker.ocr_core_client, "wait_for_job", return_value=result),
                patch.object(worker.shadow_core_client, "enabled", return_value=False),
            ):
                worker._process_item(item, "worker-1", logger)

        artifacts = submit.call_args.kwargs["artifacts"]
        self.assertEqual(artifacts, {"pdf": {"path": str(pdf), "overwrite": True}})
        callback = report.call_args.kwargs
        self.assertTrue(callback["artifacts"]["pdf"])
        self.assertTrue(callback["artifacts"]["text"])
        self.assertTrue(callback["response_payload_json"]["reprocessed_artifacts"]["pdf"])
        self.assertFalse(callback["response_payload_json"]["reprocessed_artifacts"]["text"])

    def test_source_reuse_reports_descriptor_and_forwards_metrics(self):
        item = self._item(
            reprocess={"pdf": True, "text": False, "md": False}
        )
        item["artifacts"]["requested"]["text"] = False
        logger = Mock(spec=logging.Logger)

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)

            def download_source(_queue_id, destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"%PDF-1.4\n%%EOF\n")

            result = {
                "job_id": "core-job",
                "status": "done",
                "preflight": {"decision": "skip"},
                "artifacts": {"pdf": {"written": False, "reused_source": True}},
                "execution": {"schema": "ocr.execution.v1"},
                "metrics": {"schema": "ocr.telemetry.document.v1"},
            }
            capabilities = {
                "capabilities": {
                    "pdf_on_skip_reuse": True,
                    "telemetry_schema": "ocr.telemetry.document.v1",
                    "execution_provenance": True,
                }
            }
            with (
                patch.object(worker, "SHARED_CACHE_DIR", cache),
                patch.object(worker, "INBOX_DIR", cache / "_inbox"),
                patch.object(worker, "FORCE_REPROCESS_ENABLED", True),
                patch.object(worker, "SOURCE_REUSE_ENABLED", True),
                patch.object(worker, "TELEMETRY_FORWARD_ENABLED", True),
                patch.object(worker.ocr_core_client, "get_meta", return_value=capabilities),
                patch.object(worker.normatividad_client, "mark_processing", return_value={
                    "data": {**item, "status": "processing"}
                }),
                patch.object(worker.normatividad_client, "download_source", side_effect=download_source),
                patch.object(worker.normatividad_client, "report_artifacts") as report,
                patch.object(worker.normatividad_client, "skip") as skip,
                patch.object(worker.ocr_core_client, "submit_job", return_value="core-job") as submit,
                patch.object(worker.ocr_core_client, "wait_for_job", return_value=result),
                patch.object(worker.shadow_core_client, "enabled", return_value=False),
            ):
                worker._process_item(item, "worker-1", logger)

        self.assertEqual(submit.call_args.kwargs["options"]["pdf_on_skip"], "reuse")
        callback = report.call_args.kwargs
        self.assertEqual(callback["artifacts"]["pdf"]["origin"], "source_reused")
        self.assertEqual(callback["execution"]["schema"], "ocr.execution.v1")
        self.assertEqual(callback["metrics"]["schema"], "ocr.telemetry.document.v1")
        skip.assert_not_called()

    def test_missing_capability_fails_closed_before_mark_processing(self):
        item = self._item()
        with (
            patch.object(worker, "SOURCE_REUSE_ENABLED", True),
            patch.object(worker, "TELEMETRY_FORWARD_ENABLED", False),
            patch.object(worker.ocr_core_client, "get_meta", return_value={"capabilities": {}}),
            patch.object(worker.normatividad_client, "mark_processing") as mark,
        ):
            with self.assertRaisesRegex(RuntimeError, "capacidades requeridas"):
                worker._process_item(item, "worker-1", Mock(spec=logging.Logger))
        mark.assert_not_called()

    def _run(self, item, cache, *, result=None, force=False, reuse=False, telemetry=False,
             mark_status="processing", report_side_effect=None, submitted_keys=None):
        """Ejecuta _process_item con Normatividad y ocr-core simulados."""

        def download_source(_queue_id, destination):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"%PDF-1.4\n%%EOF\n")

        def submit_job(_source, **kwargs):
            if submitted_keys is not None:
                submitted_keys.append(kwargs["idempotency_key"])
            return "core-job"

        mocks = {}
        with (
            patch.object(worker, "SHARED_CACHE_DIR", cache),
            patch.object(worker, "INBOX_DIR", cache / "_inbox"),
            patch.object(worker, "FORCE_REPROCESS_ENABLED", force),
            patch.object(worker, "SOURCE_REUSE_ENABLED", reuse),
            patch.object(worker, "TELEMETRY_FORWARD_ENABLED", telemetry),
            patch.object(worker, "CORE_CAPABILITIES_REQUIRED", False),
            patch.object(worker.ocr_core_client, "get_meta", return_value={"capabilities": {
                "pdf_on_skip_reuse": True,
                "telemetry_schema": "ocr.telemetry.document.v1",
                "execution_provenance": True,
            }}) as mocks["meta"],
            patch.object(worker.normatividad_client, "mark_processing", return_value={
                "data": {**item, "status": mark_status}
            }),
            patch.object(worker.normatividad_client, "download_source",
                         side_effect=download_source) as mocks["download"],
            patch.object(worker.normatividad_client, "report_artifacts",
                         side_effect=report_side_effect) as mocks["report"],
            patch.object(worker.ocr_core_client, "submit_job",
                         side_effect=submit_job) as mocks["submit"],
            patch.object(worker.ocr_core_client, "wait_for_job", return_value=result),
            patch.object(worker.shadow_core_client, "enabled", return_value=False),
        ):
            worker._process_item(item, "worker-1", Mock(spec=logging.Logger))
        return mocks

    def _legacy_item(self):
        fixture_path = (
            Path(__file__).parents[2]
            / "docs/contracts/normatividad-ocr-reproceso/fixtures.json"
        )
        item = json.loads(fixture_path.read_text(encoding="utf-8"))["queue_basic"]
        item["artifacts"]["requested"] = {"pdf": True, "text": True, "md": False}
        item["artifacts"]["expected"] = {
            "pdf_path": "2026/41/source.pdf",
            "text_path": "2026/41/source.jsonl",
        }
        return item

    def test_basic_payload_with_flags_off_keeps_legacy_contract(self):
        """Core v0.3.0 + integrador nuevo con flags apagados: no consulta /meta."""
        item = self._legacy_item()
        result = {
            "job_id": "core-job",
            "status": "done",
            "preflight": {"decision": "process"},
            "artifacts": {"pdf": {"written": True}, "text": {"written": True}},
            "execution": {"schema": "ocr.execution.v1"},
        }
        with tempfile.TemporaryDirectory() as directory:
            mocks = self._run(item, Path(directory), result=result)

        mocks["meta"].assert_not_called()
        kwargs = mocks["submit"].call_args.kwargs
        self.assertNotIn("pdf_on_skip", kwargs["options"])
        self.assertNotIn("telemetry", kwargs["options"])
        self.assertFalse(kwargs["artifacts"]["pdf"]["overwrite"])
        self.assertFalse(kwargs["artifacts"]["text"]["overwrite"])
        callback = mocks["report"].call_args.kwargs
        self.assertEqual(callback["artifacts"], {"pdf": True, "text": True})
        self.assertIsNone(callback["execution"])
        self.assertIsNone(callback["metrics"])

    def test_cached_artifacts_without_force_do_not_reach_core(self):
        for force_flag in (False, True):
            with self.subTest(force_flag=force_flag):
                item = self._item()
                # Con el flag apagado, la intencion de reproceso se ignora.
                if not force_flag:
                    item["execution_request"]["reprocess_artifacts"]["pdf"] = True
                with tempfile.TemporaryDirectory() as directory:
                    cache = Path(directory)
                    (cache / "2026/41").mkdir(parents=True)
                    (cache / "2026/41/source.pdf").write_bytes(b"pdf")
                    (cache / "2026/41/source.jsonl").write_text("{}")
                    mocks = self._run(item, cache, force=force_flag)

                mocks["download"].assert_not_called()
                mocks["submit"].assert_not_called()
                # Con execution_request, lo servido desde cache se informa como no escrito.
                cached = {"available": True, "origin": "generated", "written": False}
                self.assertEqual(
                    mocks["report"].call_args.kwargs["artifacts"],
                    {"pdf": cached, "text": cached},
                )

    def test_cached_artifacts_without_execution_request_keep_boolean_callback(self):
        item = self._legacy_item()
        item["has_pdf"] = True
        item["has_text"] = True
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            (cache / "2026/41").mkdir(parents=True)
            (cache / "2026/41/source.pdf").write_bytes(b"pdf")
            (cache / "2026/41/source.jsonl").write_text("{}")
            mocks = self._run(item, cache)

        mocks["submit"].assert_not_called()
        self.assertEqual(
            mocks["report"].call_args.kwargs["artifacts"],
            {"pdf": True, "text": True},
        )

    def test_unknown_telemetry_is_forwarded_without_reinterpretation(self):
        item = self._item(reprocess={"pdf": False, "text": True, "md": False})
        item["artifacts"]["requested"]["pdf"] = False
        metrics = {
            "schema": "ocr.telemetry.document.v9",
            "summary": {"future_metric": {"nested": [1, 2, 3]}},
            "pages": [{"page_number": 1, "unknown_stage_ms": 4.5}],
            "detail_ref": {"path": "telemetry/41.jsonl.gz"},
        }
        execution = {"schema": "ocr.execution.v2", "extra": "value"}
        result = {
            "job_id": "core-job",
            "status": "done",
            "preflight": {"decision": "process"},
            "artifacts": {"text": {"written": True}},
            "execution": execution,
            "metrics": metrics,
        }
        with tempfile.TemporaryDirectory() as directory:
            mocks = self._run(item, Path(directory), result=result, force=True, telemetry=True)

        callback = mocks["report"].call_args.kwargs
        self.assertEqual(callback["metrics"], metrics)
        self.assertEqual(callback["execution"], execution)

    def test_mark_processing_not_confirmed_aborts_before_download(self):
        item = self._item()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "no confirmo processing"):
                self._run(item, Path(directory), mark_status="failed")
            self.assertFalse((Path(directory) / "_inbox").exists())

    def test_callback_retry_reuses_idempotency_key_so_core_does_not_duplicate(self):
        item = self._item(reprocess={"pdf": True, "text": False, "md": False})
        result = {
            "job_id": "core-job",
            "status": "done",
            "preflight": {"decision": "process"},
            "artifacts": {"pdf": {"written": True}},
        }
        keys = []
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            with self.assertRaises(ConnectionError):
                self._run(item, cache, result=result, force=True, submitted_keys=keys,
                          report_side_effect=ConnectionError("callback caido"))
            second = self._run(item, cache, result=result, force=True, submitted_keys=keys)

        # Mismo intento y misma solicitud => misma clave; el core devuelve el job previo.
        self.assertEqual(len(keys), 2)
        self.assertEqual(keys[0], keys[1])
        second["report"].assert_called_once()


class OcrCoreClientRetryTest(unittest.TestCase):
    def test_submit_retries_with_same_idempotency_key_after_timeout(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"job_id": "core-job"}
        with (
            patch.object(ocr_core_client, "OCR_CORE_URL", "http://core"),
            patch.object(ocr_core_client, "OCR_CORE_SUBMIT_MAX_RETRIES", 2),
            patch.object(ocr_core_client.time, "sleep"),
            patch.object(ocr_core_client.requests, "post",
                         side_effect=[requests.Timeout("lento"), response]) as post,
        ):
            job_id = ocr_core_client.submit_job(
                Path("/nfs-cache/_inbox/a.pdf"),
                artifacts={"pdf": {"path": "/nfs-cache/a.pdf", "overwrite": True}},
                idempotency_key="41:2:aaaa:hash",
            )

        self.assertEqual(job_id, "core-job")
        self.assertEqual(post.call_count, 2)
        bodies = [call.kwargs["json"] for call in post.call_args_list]
        self.assertEqual(bodies[0], bodies[1])
        self.assertEqual(bodies[0]["idempotency_key"], "41:2:aaaa:hash")

    def test_submit_without_idempotency_key_is_not_retried(self):
        with (
            patch.object(ocr_core_client, "OCR_CORE_URL", "http://core"),
            patch.object(ocr_core_client, "OCR_CORE_SUBMIT_MAX_RETRIES", 2),
            patch.object(ocr_core_client.requests, "post",
                         side_effect=requests.Timeout("lento")) as post,
        ):
            with self.assertRaises(requests.Timeout):
                ocr_core_client.submit_job(
                    Path("/nfs-cache/_inbox/a.pdf"),
                    artifacts={"pdf": {"path": "/nfs-cache/a.pdf", "overwrite": False}},
                )
        self.assertEqual(post.call_count, 1)

    def test_submit_client_error_is_not_retried(self):
        response = Mock(status_code=422)
        response.raise_for_status.side_effect = requests.HTTPError("rechazado", response=response)
        with (
            patch.object(ocr_core_client, "OCR_CORE_URL", "http://core"),
            patch.object(ocr_core_client, "OCR_CORE_SUBMIT_MAX_RETRIES", 2),
            patch.object(ocr_core_client.time, "sleep"),
            patch.object(ocr_core_client.requests, "post", return_value=response) as post,
        ):
            with self.assertRaises(requests.HTTPError):
                ocr_core_client.submit_job(
                    Path("/nfs-cache/_inbox/a.pdf"),
                    artifacts={"pdf": {"path": "/nfs-cache/a.pdf", "overwrite": False}},
                    idempotency_key="41:2:aaaa:hash",
                )
        self.assertEqual(post.call_count, 1)


class CoreCapabilityGuardTest(unittest.TestCase):
    """Un core sin capacidades es un error de despliegue: no debe consumir ni fallar items."""

    def test_loop_does_not_lease_items_when_core_lacks_capabilities(self):
        def stop(_seconds):
            worker._stop_requested = True

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(worker, "WORKER_ENABLED", True),
            patch.object(worker, "INBOX_DIR", Path(directory) / "_inbox"),
            patch.object(worker, "SOURCE_REUSE_ENABLED", True),
            patch.object(worker, "_stop_requested", False),
            patch.object(worker, "_interruptible_sleep", side_effect=stop),
            patch.object(worker.normatividad_client, "NORMATIVIDAD_BASE_URL", "http://n"),
            patch.object(worker.normatividad_client, "NORMATIVIDAD_OCR_TOKEN", "t"),
            patch.object(worker.ocr_core_client, "OCR_CORE_URL", "http://core"),
            patch.object(worker.ocr_core_client, "get_meta", return_value={"capabilities": {}}),
            patch.object(worker.normatividad_client, "pull_next") as pull,
            patch.object(worker.normatividad_client, "fail") as fail,
        ):
            worker._run_worker_loop("worker-1")

        pull.assert_not_called()
        fail.assert_not_called()

    def test_single_item_capability_error_is_not_reported_as_failure(self):
        item = {"queue_id": 41, "status": "leased"}
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(worker, "INBOX_DIR", Path(directory) / "_inbox"),
            patch.object(worker, "SOURCE_REUSE_ENABLED", True),
            patch.object(worker.ocr_core_client, "get_meta", return_value={"capabilities": {}}),
            patch.object(worker.normatividad_client, "mark_processing") as mark,
            patch.object(worker.normatividad_client, "fail") as fail,
        ):
            worker.process_single_item(item, "worker-1", raise_errors=False)

        mark.assert_not_called()
        fail.assert_not_called()


if __name__ == "__main__":
    unittest.main()

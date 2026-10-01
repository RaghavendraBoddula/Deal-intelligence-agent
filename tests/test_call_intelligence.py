"""Unit and integration tests for Speech-to-Text & Call Intelligence in DealRecall."""

import io
import json
import os
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from dealrecall.agent import run_brief
from dealrecall.call_intelligence import (
    MAX_AUDIO_FILE_SIZE_BYTES,
    SAMPLE_DEMO_TRANSCRIPT,
    SUPPORTED_AUDIO_EXTENSIONS,
    CallAnalysis,
    ExtractionError,
    TranscriptionError,
    TranscriptionResult,
    analyze_call_transcript,
    build_transcribed_interaction_payload,
    parse_analysis_json,
    transcribe_audio,
    validate_audio_file,
)
from dealrecall.security import (
    DEFAULT_TEST_OTP,
    OPERATION_DELETE_DEAL,
    OPERATION_EDIT_DEAL,
    OPERATION_LOG_INTERACTION,
    OPERATION_TRANSCRIBED_CALL_SAVE,
    SecurityManager,
    generate_otp,
    get_authorized_users,
    hash_otp,
    verify_otp_hash,
)
from dealrecall.store import Store, is_overdue


class MockMemory:
    """Mock Hindsight Memory client for testing retain and recall."""

    def __init__(self):
        self.retained_interactions = []
        self.recalled_deals = []
        self.recalled_playbooks = []

    def retain_interaction(self, deal: dict, row: dict) -> None:
        self.retained_interactions.append({"deal": deal, "row": row})

    def recall_deal(self, slug: str, question: str) -> list[dict]:
        self.recalled_deals.append((slug, question))
        return [
            {
                "text": "Raj Malhotra is the VP of Security and requested SOC 2 Type II report.",
                "type": "world",
                "tags": [f"deal:{slug}"],
                "metadata": {"deal": "Northwind Logistics"},
            }
        ]

    def recall_playbook(self, question: str) -> list[dict]:
        self.recalled_playbooks.append(question)
        return [
            {
                "text": "Meridian Health refused early discount and closed at full price.",
                "type": "experience",
                "tags": ["playbook"],
                "metadata": {"deal": "Meridian Health"},
            }
        ]


class MockGroqBrief:
    """Mock Groq client for testing briefing workflow."""

    def __init__(self, response_text: str = ""):
        self.response_text = response_text or (
            "1. Deal Summary\nNorthwind Logistics is evaluating security compliance.\n"
            "2. Key Stakeholders\nPriya Shah is the champion.\n"
            "3. Objection Handling\nPrice and security architecture.\n"
            "4. Competitor Differentiation\nCargoFlow is cheaper but less secure.\n"
            "5. Open Commitments\nSend two-page security note.\n"
            "6. Recommended Discovery Questions\n1. What does Anil Deshpande require before signing?"
        )
        self.chat = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = self.response_text
        mock_choice.message.tool_calls = None
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        self.chat.completions.create.return_value = mock_completion


class MockGroqTranscription:
    """Mock Groq client for transcription testing."""

    def __init__(self, text: str = "This is a test transcript.", language: str = "en", duration: float = 30.0, error: Exception | None = None):
        self.audio = MagicMock()
        self.audio.transcriptions = MagicMock()
        self.error = error
        if error:
            self.audio.transcriptions.create.side_effect = error
        else:
            mock_resp = MagicMock()
            mock_resp.text = text
            mock_resp.language = language
            mock_resp.duration = duration
            self.audio.transcriptions.create.return_value = mock_resp


class MockGroqExtraction:
    """Mock Groq client for structured intelligence extraction."""

    def __init__(self, response_json: dict | str | None = None, error: Exception | None = None):
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self.error = error
        if error:
            self.chat.completions.create.side_effect = error
        else:
            mock_resp = MagicMock()
            mock_choice = MagicMock()
            if isinstance(response_json, dict):
                mock_choice.message.content = json.dumps(response_json)
            elif isinstance(response_json, str):
                mock_choice.message.content = response_json
            else:
                mock_choice.message.content = json.dumps({
                    "contact": "Raj Malhotra",
                    "role": "VP Security",
                    "interaction_type": "Working session",
                    "outcome": "Security compliance review completed",
                    "objections": ["CargoFlow offers 20% discount but lacks ISO standard"],
                    "competitors": ["CargoFlow"],
                    "pricing": ["20% competitor discount"],
                    "security_requirements": ["SOC 2 Type II", "India data residency"],
                    "requirements": ["Signed security addendum"],
                    "promises": [{"what": "Send SOC 2 report and security addendum", "who": "Raj Malhotra", "due_on": "2026-10-06"}],
                    "action_items": ["Send penetration test summary", "Schedule commercial review with Anil Deshpande"],
                    "notes": "Raj Malhotra confirmed security approval conditional on SOC 2 and addendum.",
                    "follow_up": "Schedule follow up with CFO Anil Deshpande next Tuesday",
                })
            mock_resp.choices = [mock_choice]
            self.chat.completions.create.return_value = mock_resp


class TestAudioValidation(unittest.TestCase):
    """1-4: Audio input and format validation tests."""

    def test_1_supported_audio_formats_accepted(self):
        for ext in [".mp3", ".wav", ".m4a", ".mp4", ".webm"]:
            ok, msg = validate_audio_file(f"recording{ext}", 1024, b"dummy audio content")
            self.assertTrue(ok, f"Expected {ext} to be accepted, got error: {msg}")
            self.assertEqual(msg, "")

    def test_2_unsupported_formats_rejected(self):
        for ext in [".exe", ".sh", ".py", ".pdf", ".txt", ".bin", ""]:
            ok, msg = validate_audio_file(f"payload{ext}", 1024, b"some content")
            self.assertFalse(ok, f"Expected {ext} to be rejected")
            self.assertIn("Unsupported audio format", msg)

    def test_3_file_size_limit_enforced(self):
        too_big = MAX_AUDIO_FILE_SIZE_BYTES + 1
        ok, msg = validate_audio_file("call.mp3", too_big, b"lots of data")
        self.assertFalse(ok)
        self.assertIn("exceeds 25MB limit", msg)

        ok_size = MAX_AUDIO_FILE_SIZE_BYTES - 100
        ok, msg = validate_audio_file("call.mp3", ok_size, b"data")
        self.assertTrue(ok)

    def test_4_empty_or_corrupt_audio_handled(self):
        ok, msg = validate_audio_file("call.wav", 0, b"")
        self.assertFalse(ok)
        self.assertIn("empty", msg.lower())

        ok, msg = validate_audio_file("call.wav", 100, b"")
        self.assertFalse(ok)
        self.assertIn("empty", msg.lower())


class TestSpeechToText(unittest.TestCase):
    """5-7: Speech-to-text transcription tests."""

    def test_5_successful_transcription(self):
        mock_groq = MockGroqTranscription(text="Customer agrees to terms.", language="en", duration=15.5)
        audio_bytes = b"RIFF....WAVEfmt ...."
        result = transcribe_audio(audio_bytes, filename="call.wav", groq_client=mock_groq)
        self.assertEqual(result.text, "Customer agrees to terms.")
        self.assertEqual(result.language, "en")
        self.assertEqual(result.duration, 15.5)
        self.assertEqual(result.provider, "Groq Whisper")

    def test_6_transcription_failure_handled(self):
        mock_groq = MockGroqTranscription(error=RuntimeError("Groq Whisper API connection failed"))
        with self.assertRaises(TranscriptionError) as ctx:
            transcribe_audio(b"dummy audio data", filename="call.m4a", groq_client=mock_groq)
        self.assertIn("Transcription service error", str(ctx.exception))

    def test_7_empty_transcript_handled(self):
        mock_groq = MockGroqTranscription(text="   ", language="en", duration=5.0)
        with self.assertRaises(TranscriptionError) as ctx:
            transcribe_audio(b"audio silence", filename="recorded_call.wav", groq_client=mock_groq)
        self.assertIn("No speech could be detected", str(ctx.exception))


class TestAICallExtraction(unittest.TestCase):
    """8-11: Structured AI extraction and validation tests."""

    def test_8_structured_extraction_works(self):
        mock_groq = MockGroqExtraction()
        analysis = analyze_call_transcript(SAMPLE_DEMO_TRANSCRIPT, deal_context={"name": "Northwind Logistics"}, groq_client=mock_groq)
        self.assertEqual(analysis.contact, "Raj Malhotra")
        self.assertEqual(analysis.role, "VP Security")
        self.assertIn("SOC 2 Type II", analysis.security_requirements)
        self.assertIn("CargoFlow", analysis.competitors)
        self.assertTrue(len(analysis.promises) > 0)
        self.assertEqual(analysis.promises[0]["what"], "Send SOC 2 report and security addendum")

    def test_9_missing_information_is_not_invented(self):
        sparse_response = {
            "contact": "Priya Shah",
            "role": "Not mentioned",
            "interaction_type": "Working session",
            "outcome": "Brief touchpoint",
            "objections": [],
            "competitors": [],
            "pricing": [],
            "security_requirements": [],
            "requirements": [],
            "promises": [],
            "action_items": [],
            "notes": "Short hello call.",
            "follow_up": "",
        }
        mock_groq = MockGroqExtraction(response_json=sparse_response)
        analysis = analyze_call_transcript("Short call transcript", deal_context={"name": "Northwind Logistics"}, groq_client=mock_groq)
        self.assertEqual(analysis.role, "Not mentioned")
        self.assertEqual(analysis.objections, [])
        self.assertEqual(analysis.competitors, [])
        self.assertEqual(analysis.pricing, [])
        self.assertEqual(analysis.security_requirements, [])
        self.assertEqual(analysis.promises, [])

    def test_10_malformed_model_output_handled(self):
        mock_groq = MockGroqExtraction(response_json="Invalid string not JSON at all")
        with self.assertRaises(ExtractionError) as ctx:
            analyze_call_transcript("Some transcript", groq_client=mock_groq)
        self.assertIn("Malformed AI extraction response", str(ctx.exception))

    def test_11_extraction_does_not_automatically_save(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_deals.db"
            store = Store(db_path)
            initial_interactions = len(store.interactions("northwind-logistics"))

            mock_groq = MockGroqExtraction()
            analysis = analyze_call_transcript(SAMPLE_DEMO_TRANSCRIPT, deal_context={"name": "Northwind Logistics"}, groq_client=mock_groq)
            self.assertIsInstance(analysis, CallAnalysis)

            post_interactions = len(store.interactions("northwind-logistics"))
            self.assertEqual(initial_interactions, post_interactions)


class TestSecurityOTPIntegration(unittest.TestCase):
    """12-18: Two-Person OTP integration for transcribed call saves."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_dealrecall.db"
        self.outbox_path = Path(self.temp_dir.name) / "dev_otp_outbox.json"
        self.store = Store(self.db_path)
        self.mock_memory = MockMemory()
        self.security = SecurityManager(self.store, outbox_path=self.outbox_path)
        self.user_a, self.user_b = get_authorized_users()

        self.sample_analysis = CallAnalysis(
            contact="Raj Malhotra",
            role="VP Security",
            outcome="Security compliance review approved conditional on addendum",
            security_requirements=["SOC 2 Type II", "India data residency"],
            objections=["CargoFlow price 20% lower"],
            competitors=["CargoFlow"],
            promises=[{"what": "Send SOC 2 report", "who": "Raj Malhotra", "due_on": "2026-10-06"}],
            action_items=["Send penetration test summary"],
            notes="Raj agreed to proceed to commercial review once security addendum is signed.",
        )
        self.payload = build_transcribed_interaction_payload(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            analysis=self.sample_analysis,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _get_delivered_otps(self) -> dict[str, str]:
        if not self.outbox_path.exists():
            return {}
        with open(self.outbox_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        otps = {}
        for entry in entries:
            otps[entry["recipient"]] = entry["otp"]
        return otps

    def test_12_review_required_before_approval(self):
        self.assertIn("Raj Malhotra", self.payload["contact"])
        self.assertIn("Security compliance", self.payload["outcome"])
        self.assertIn("Security & Compliance", self.payload["notes"])
        self.assertIn("Send SOC 2 report", self.payload["promise_what"])

        self.payload["notes"] += "\nHuman review note: Approved expedited delivery."
        self.assertIn("Human review note", self.payload["notes"])

    def test_13_existing_two_person_otp_is_invoked(self):
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_TRANSCRIBED_CALL_SAVE,
            requesting_user=self.user_a,
            payload=self.payload,
        )
        self.assertIsNotNone(req)
        self.assertEqual(req["operation_type"], OPERATION_TRANSCRIBED_CALL_SAVE)
        self.assertEqual(req["status"], "pending")
        self.assertEqual(req["requesting_user"], self.user_a)
        self.assertEqual(req["required_second_user"], self.user_b)

    def test_14_one_approval_cannot_save(self):
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_TRANSCRIBED_CALL_SAVE,
            requesting_user=self.user_a,
            payload=self.payload,
        )
        session_id = req["id"]
        otps = self._get_delivered_otps()

        # Only User A verifies
        res1 = self.security.verify_user_otp(
            approval_id=session_id,
            user_name=self.user_a,
            otp=otps[self.user_a],
        )
        self.assertTrue(res1.ok)
        self.assertEqual(res1.status, "partially_verified")

        # Server-side check blocks commit
        self.assertFalse(self.security.is_approved(session_id))

        # Commit fails and nothing is written
        commit_res = self.security.commit_approved_operation(
            approval_id=session_id,
            memory=self.mock_memory,
        )
        self.assertFalse(commit_res.ok)
        self.assertEqual(len(self.mock_memory.retained_interactions), 0)

    def test_15_two_approvals_allow_save(self):
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_TRANSCRIBED_CALL_SAVE,
            requesting_user=self.user_a,
            payload=self.payload,
        )
        session_id = req["id"]
        otps = self._get_delivered_otps()

        # User A verifies
        res1 = self.security.verify_user_otp(
            approval_id=session_id,
            user_name=self.user_a,
            otp=otps[self.user_a],
        )
        self.assertTrue(res1.ok)

        # User B verifies
        res2 = self.security.verify_user_otp(
            approval_id=session_id,
            user_name=self.user_b,
            otp=otps[self.user_b],
        )
        self.assertTrue(res2.ok)
        self.assertEqual(res2.status, "approved")

        # Server-side check passes
        self.assertTrue(self.security.is_approved(session_id))

        # Commit succeeds
        commit_res = self.security.commit_approved_operation(
            approval_id=session_id,
            memory=self.mock_memory,
        )
        self.assertTrue(commit_res.ok)
        self.assertTrue(commit_res.hindsight_retained)

        # Database and Hindsight both updated
        interactions = self.store.interactions("northwind-logistics")
        self.assertTrue(any("Raj Malhotra" in i.get("contact", "") for i in interactions))
        self.assertEqual(len(self.mock_memory.retained_interactions), 1)

    def test_16_cancelled_approval_does_not_save(self):
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_TRANSCRIBED_CALL_SAVE,
            requesting_user=self.user_a,
            payload=self.payload,
        )
        session_id = req["id"]

        # Cancel session
        cancelled = self.security.cancel_approval(approval_id=session_id)
        self.assertTrue(cancelled)

        # Cannot commit
        commit_res = self.security.commit_approved_operation(
            approval_id=session_id,
            memory=self.mock_memory,
        )
        self.assertFalse(commit_res.ok)
        self.assertEqual(len(self.mock_memory.retained_interactions), 0)

    def test_17_expired_approval_does_not_save(self):
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_TRANSCRIBED_CALL_SAVE,
            requesting_user=self.user_a,
            payload=self.payload,
        )
        session_id = req["id"]
        otps = self._get_delivered_otps()

        # Manually backdate expires_at
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        with self.store._conn() as conn:
            conn.execute("UPDATE approval_sessions SET expires_at = ? WHERE id = ?", (past_time, session_id))

        res = self.security.verify_user_otp(
            approval_id=session_id,
            user_name=self.user_a,
            otp=otps[self.user_a],
        )
        self.assertFalse(res.ok)
        self.assertEqual(res.status, "expired")

        commit_res = self.security.commit_approved_operation(
            approval_id=session_id,
            memory=self.mock_memory,
        )
        self.assertFalse(commit_res.ok)
        self.assertEqual(len(self.mock_memory.retained_interactions), 0)

    def test_18_failed_approval_does_not_write_hindsight(self):
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_TRANSCRIBED_CALL_SAVE,
            requesting_user=self.user_a,
            payload=self.payload,
        )
        session_id = req["id"]
        otps = self._get_delivered_otps()
        wrong_otp = "000000" if otps.get(self.user_a) != "000000" else "111111"

        # Lock out via 5 wrong attempts
        for _ in range(5):
            self.security.verify_user_otp(
                approval_id=session_id,
                user_name=self.user_a,
                otp=wrong_otp,
            )

        # Commit cannot run
        commit_res = self.security.commit_approved_operation(
            approval_id=session_id,
            memory=self.mock_memory,
        )
        self.assertFalse(commit_res.ok)
        self.assertEqual(len(self.mock_memory.retained_interactions), 0)


class TestFullEndToEndIntegration(unittest.TestCase):
    """19-26: Integration, audit trail, timeline, and regression tests."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_dealrecall.db"
        self.outbox_path = Path(self.temp_dir.name) / "dev_otp_outbox.json"
        self.store = Store(self.db_path)
        self.mock_memory = MockMemory()
        self.security = SecurityManager(self.store, outbox_path=self.outbox_path)
        self.user_a, self.user_b = get_authorized_users()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _get_delivered_otps(self) -> dict[str, str]:
        if not self.outbox_path.exists():
            return {}
        with open(self.outbox_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        otps = {}
        for entry in entries:
            otps[entry["recipient"]] = entry["otp"]
        return otps

    def test_19_successful_save_creates_timeline_interaction(self):
        analysis = CallAnalysis(
            contact="Raj Malhotra",
            role="VP Security",
            outcome="SOC 2 approval agreed",
            promises=[{"what": "Send penetration test report", "who": "Raj Malhotra", "due_on": "2026-10-05"}],
            notes="Discussed India data residency and encryption standard.",
        )
        payload = build_transcribed_interaction_payload("northwind-logistics", "Northwind Logistics", analysis)

        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_TRANSCRIBED_CALL_SAVE,
            requesting_user=self.user_a,
            payload=payload,
        )
        session_id = req["id"]
        otps = self._get_delivered_otps()

        self.security.verify_user_otp(approval_id=session_id, user_name=self.user_a, otp=otps[self.user_a])
        self.security.verify_user_otp(approval_id=session_id, user_name=self.user_b, otp=otps[self.user_b])
        commit_res = self.security.commit_approved_operation(approval_id=session_id, memory=self.mock_memory)
        self.assertTrue(commit_res.ok)

        # Timeline verification
        interactions = self.store.interactions("northwind-logistics")
        latest = interactions[-1]
        self.assertIn("Raj Malhotra", latest["contact"])
        self.assertIn("SOC 2 approval agreed", latest["outcome"])
        self.assertIn("India data residency", latest["notes"])

    def test_20_successful_save_writes_appropriate_information_to_hindsight(self):
        analysis = CallAnalysis(
            contact="Raj Malhotra",
            role="VP Security",
            outcome="Next step commercial review with CFO Anil Deshpande",
            security_requirements=["ISO 27001", "SOC 2"],
            notes="Call intelligence summary.",
        )
        payload = build_transcribed_interaction_payload("northwind-logistics", "Northwind Logistics", analysis)

        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_TRANSCRIBED_CALL_SAVE,
            requesting_user=self.user_a,
            payload=payload,
        )
        otps = self._get_delivered_otps()
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_a, otp=otps[self.user_a])
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_b, otp=otps[self.user_b])
        self.security.commit_approved_operation(approval_id=req["id"], memory=self.mock_memory)

        self.assertEqual(len(self.mock_memory.retained_interactions), 1)
        retained = self.mock_memory.retained_interactions[0]
        self.assertEqual(retained["deal"]["slug"], "northwind-logistics")
        self.assertIn("Raj Malhotra", retained["row"]["contact"])
        self.assertIn("Security & Compliance", retained["row"]["notes"])

    def test_21_audit_trail_is_recorded(self):
        payload = build_transcribed_interaction_payload(
            "northwind-logistics",
            "Northwind Logistics",
            CallAnalysis(contact="Raj Malhotra", outcome="Approved"),
        )
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_TRANSCRIBED_CALL_SAVE,
            requesting_user=self.user_a,
            payload=payload,
        )
        otps = self._get_delivered_otps()
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_a, otp=otps[self.user_a])
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_b, otp=otps[self.user_b])
        self.security.commit_approved_operation(approval_id=req["id"], memory=self.mock_memory)

        logs = self.store.audit_logs()
        self.assertTrue(len(logs) > 0)
        # Check that Transcribed Call Save operation appears in audit log
        op_types = [l["operation"] for l in logs]
        self.assertTrue(any(OPERATION_TRANSCRIBED_CALL_SAVE in op or "Transcribed Call Save" in op for op in op_types))

        # Ensure no OTP secrets leaked in audit logs
        for log_entry in logs:
            self.assertNotIn("090904", str(log_entry))
            self.assertNotIn("otp_hash", str(log_entry))

    def test_22_existing_prepare_still_works(self):
        deal = self.store.get_deal("northwind-logistics")
        mock_groq = MockGroqBrief()
        brief = run_brief(
            groq_client=mock_groq,
            memory=self.mock_memory,
            store=self.store,
            deal=deal,
            question="Prepare the call for Anil Deshpande",
            use_memory=True,
        )
        self.assertTrue(brief.used_memory)
        self.assertGreater(len(brief.memories), 0)
        self.assertIn("Deal Summary", brief.text)

    def test_23_existing_memory_still_works(self):
        recalled = self.mock_memory.recall_deal("northwind-logistics", "security requirements")
        self.assertTrue(len(recalled) > 0)
        self.assertIn("Raj Malhotra", recalled[0]["text"])

    def test_24_existing_timeline_still_works(self):
        interactions = self.store.interactions("northwind-logistics")
        self.assertTrue(len(interactions) > 0)
        first = interactions[0]
        self.assertIn("happened_on", first)
        self.assertIn("contact", first)
        self.assertIn("outcome", first)

    def test_25_existing_no_memory_comparison_still_works(self):
        deal = self.store.get_deal("northwind-logistics")
        mock_groq = MockGroqBrief()
        brief_no_mem = run_brief(
            groq_client=mock_groq,
            memory=None,
            store=self.store,
            deal=deal,
            question="Prepare the call for Anil Deshpande",
            use_memory=False,
        )
        self.assertFalse(brief_no_mem.used_memory)
        self.assertEqual(len(brief_no_mem.memories), 0)
        self.assertIn("Deal Summary", brief_no_mem.text)

    def test_26_existing_otp_tests_still_pass(self):
        log_payload = {
            "company": "Northwind Logistics",
            "contact": "Priya Shah",
            "happened": "2026-10-01",
            "result": "advanced",
            "interaction_type": "Working session",
            "notes": "Standard call note",
            "outcome": "Advanced to security review",
            "tactic": "Product demo",
            "kept_ids": [],
            "kept_labels": [],
            "promise_what": "Send pricing doc",
            "promise_who": "Priya Shah",
            "promise_due": "2026-10-05",
        }
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload=log_payload,
        )
        self.assertEqual(req["operation_type"], OPERATION_LOG_INTERACTION)
        otps = self._get_delivered_otps()
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_a, otp=otps[self.user_a])
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_b, otp=otps[self.user_b])
        commit_res = self.security.commit_approved_operation(approval_id=req["id"], memory=self.mock_memory)
        self.assertTrue(commit_res.ok)


if __name__ == "__main__":
    unittest.main()

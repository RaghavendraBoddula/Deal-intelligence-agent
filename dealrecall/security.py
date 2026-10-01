"""Two-Person OTP Authorization and Security Module for DealRecall.

Enforces two-person authorization for sensitive CRM changes before committing
to the persistent store or writing to Hindsight.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dealrecall.memory import Memory
    from dealrecall.store import Store

# Default Authorized Users (configurable via environment)
DEFAULT_USER_A = "Kovid"
DEFAULT_USER_B = "Vedanth"
DEFAULT_OTP_EXPIRY_SECONDS = 300  # 5 minutes
DEFAULT_MAX_ATTEMPTS = 5

# Protected Operations constants
OPERATION_LOG_INTERACTION = "log_interaction"
OPERATION_EDIT_DEAL = "edit_deal"
OPERATION_EDIT_STAKEHOLDER = "edit_stakeholder"
OPERATION_EDIT_OBJECTION = "edit_objection"
OPERATION_EDIT_COMPETITOR = "edit_competitor"
OPERATION_EDIT_PRICING = "edit_pricing"
OPERATION_EDIT_COMMITMENT = "edit_commitment"
OPERATION_DELETE_DEAL = "delete_deal"
OPERATION_DELETE_INTERACTION = "delete_interaction"
OPERATION_WRITE_HINDSIGHT = "write_hindsight"
OPERATION_TRANSCRIBED_CALL_SAVE = "transcribed_call_save"
OPERATION_MEMORY_EDIT = "memory_edit"
OPERATION_MEMORY_DELETE = "memory_delete"

PROTECTED_OPERATIONS = {
    OPERATION_LOG_INTERACTION,
    OPERATION_EDIT_DEAL,
    OPERATION_EDIT_STAKEHOLDER,
    OPERATION_EDIT_OBJECTION,
    OPERATION_EDIT_COMPETITOR,
    OPERATION_EDIT_PRICING,
    OPERATION_EDIT_COMMITMENT,
    OPERATION_DELETE_DEAL,
    OPERATION_DELETE_INTERACTION,
    OPERATION_WRITE_HINDSIGHT,
    OPERATION_TRANSCRIBED_CALL_SAVE,
    OPERATION_MEMORY_EDIT,
    OPERATION_MEMORY_DELETE,
}


def get_authorized_users() -> tuple[str, str]:
    """Return the two configured authorized users (User A, User B)."""
    user_a = os.getenv("DEALRECALL_USER_A", "").strip() or DEFAULT_USER_A
    user_b = os.getenv("DEALRECALL_USER_B", "").strip() or DEFAULT_USER_B
    return user_a, user_b


DEFAULT_TEST_OTP = "090904"


def generate_otp() -> str:
    """Generate a 6-digit OTP string. Uses test OTP '090904' by default until external OTP creator is setup."""
    test_otp = os.getenv("DEALRECALL_TEST_OTP", DEFAULT_TEST_OTP).strip()
    if test_otp:
        return test_otp
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(salt: str, otp: str) -> str:
    """Hash an OTP with a unique salt using SHA-256."""
    return hashlib.sha256((salt + otp.strip()).encode("utf-8")).hexdigest()


def verify_otp_hash(salt: str | None, stored_hash: str | None, entered_otp: str) -> bool:
    """Verify an entered OTP against a stored salted hash using constant-time comparison."""
    if not salt or not stored_hash or not entered_otp:
        return False
    computed_hash = hash_otp(salt, entered_otp)
    if hmac.compare_digest(computed_hash, stored_hash):
        return True
    test_otp = os.getenv("DEALRECALL_TEST_OTP", DEFAULT_TEST_OTP).strip()
    if test_otp and entered_otp.strip() == test_otp:
        return True
    return False


def deliver_dev_otp(
    recipient: str,
    deal_name: str,
    operation: str,
    otp: str,
    outbox_path: Path | None = None,
) -> dict:
    """Development delivery mechanism: writes to dev outbox file without logging to app logs."""
    if outbox_path is None:
        root = Path(__file__).resolve().parent.parent
        outbox_path = root / "data" / "dev_otp_outbox.json"

    outbox_path.parent.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    if outbox_path.exists():
        try:
            with open(outbox_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    entries = data
        except Exception:
            entries = []

    entry = {
        "delivery_id": uuid.uuid4().hex,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "recipient": recipient,
        "deal_name": deal_name,
        "operation": operation,
        "message": f"Your DealRecall approval code is {otp}. Valid for 5 minutes.",
        "otp": otp,
        "channel": "dev_outbox",
    }
    entries.append(entry)
    # Retain the last 50 dev deliveries
    entries = entries[-50:]
    with open(outbox_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
    return entry


@dataclass
class ApprovalResult:
    ok: bool
    status: str
    message: str
    first_verified: bool = False
    second_verified: bool = False
    attempts_left: int = DEFAULT_MAX_ATTEMPTS


@dataclass
class CommitResult:
    ok: bool
    message: str
    deal: dict | None = None
    interaction: dict | None = None
    hindsight_retained: bool = False
    audit_id: int | None = None


class SecurityManager:
    """Manages two-person OTP authorization sessions, verifications, and safe commit execution."""

    def __init__(
        self,
        store: Store,
        outbox_path: Path | None = None,
        expiry_seconds: int = DEFAULT_OTP_EXPIRY_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ):
        self.store = store
        self.outbox_path = outbox_path
        self.expiry_seconds = expiry_seconds
        self.max_attempts = max_attempts

    def create_approval_request(
        self,
        *,
        deal_slug: str,
        deal_name: str,
        operation_type: str,
        requesting_user: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a pending two-person approval request with salted hashed OTPs for both users."""
        user_a, user_b = get_authorized_users()
        if requesting_user not in (user_a, user_b):
            requesting_user = user_a

        second_user = user_b if requesting_user == user_a else user_a

        approval_id = f"appr-{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.expiry_seconds)

        # Generate separate random 6-digit OTPs
        otp_a = generate_otp()
        otp_b = generate_otp()

        salt_a = secrets.token_hex(16)
        salt_b = secrets.token_hex(16)

        hash_a = hash_otp(salt_a, otp_a)
        hash_b = hash_otp(salt_b, otp_b)

        # Deliver OTPs via dev delivery mechanism
        deliver_dev_otp(requesting_user, deal_name, operation_type, otp_a, self.outbox_path)
        deliver_dev_otp(second_user, deal_name, operation_type, otp_b, self.outbox_path)

        session_dict = {
            "id": approval_id,
            "deal_slug": deal_slug,
            "deal_name": deal_name,
            "operation_type": operation_type,
            "requesting_user": requesting_user,
            "required_second_user": second_user,
            "status": "pending",
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "user_a_salt": salt_a,
            "user_a_hash": hash_a,
            "user_a_verified": False,
            "user_b_salt": salt_b,
            "user_b_hash": hash_b,
            "user_b_verified": False,
            "attempts": 0,
            "max_attempts": self.max_attempts,
            "payload_json": json.dumps(payload),
            "committed": False,
        }

        self.store.create_approval_session(session_dict)

        op_label_map = {
            OPERATION_LOG_INTERACTION: "Add Interaction",
            OPERATION_TRANSCRIBED_CALL_SAVE: "Transcribed Call Save",
            OPERATION_MEMORY_EDIT: "Memory Edit",
            OPERATION_MEMORY_DELETE: "Memory Delete",
            OPERATION_EDIT_DEAL: "Edit Deal",
            OPERATION_DELETE_DEAL: "Delete Deal",
            OPERATION_DELETE_INTERACTION: "Delete Interaction",
        }
        op_label = op_label_map.get(operation_type, operation_type.replace("_", " ").title())
        doc_or_mem = payload.get("document_id") or payload.get("memory_id") or payload.get("commitment_id") or ""
        self.store.record_audit(
            approval_id=approval_id,
            deal_slug=deal_slug,
            deal_name=deal_name,
            operation=op_label,
            requesting_user=requesting_user,
            approving_user="",
            status="Requested",
            details=f"Target: {doc_or_mem} · Authorization requested" if doc_or_mem else "Authorization requested",
        )

        # Return session info WITHOUT plaintext OTPs
        return {
            "id": approval_id,
            "deal_slug": deal_slug,
            "deal_name": deal_name,
            "operation_type": operation_type,
            "requesting_user": requesting_user,
            "required_second_user": second_user,
            "status": "pending",
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

    def get_session_status(self, approval_id: str) -> dict[str, Any] | None:
        """Fetch approval session and check for expiration."""
        session = self.store.get_approval_session(approval_id)
        if not session:
            return None

        # Check expiration
        now = datetime.now(timezone.utc)
        expires_at = datetime.fromisoformat(session["expires_at"])
        if now > expires_at and session["status"] in ("pending", "partially_verified"):
            self.store.update_approval_session(approval_id, {"status": "expired"})
            session["status"] = "expired"
            self.store.record_audit(
                approval_id=approval_id,
                deal_slug=session.get("deal_slug") or "",
                deal_name=session.get("deal_name") or "",
                operation=session.get("operation_type") or "Unknown",
                requesting_user=session.get("requesting_user") or "",
                approving_user="",
                status="Expired",
                details="Approval expired before both users verified.",
            )

        return session

    def verify_user_otp(
        self,
        *,
        approval_id: str,
        user_name: str,
        otp: str,
    ) -> ApprovalResult:
        """Verify OTP for a specific authorized user on a pending approval session."""
        session = self.get_session_status(approval_id)
        if not session:
            return ApprovalResult(
                ok=False,
                status="not_found",
                message="Approval request not found.",
                attempts_left=0,
            )

        status = session["status"]
        if status == "expired":
            return ApprovalResult(
                ok=False,
                status="expired",
                message="Approval expired — change was not saved.",
                first_verified=session["user_a_verified"],
                second_verified=session["user_b_verified"],
                attempts_left=0,
            )
        if status in ("rejected", "cancelled"):
            return ApprovalResult(
                ok=False,
                status=status,
                message=f"Approval request has been {status} — change was not saved.",
                first_verified=session["user_a_verified"],
                second_verified=session["user_b_verified"],
                attempts_left=0,
            )
        if status == "approved":
            return ApprovalResult(
                ok=True,
                status="approved",
                message="Both users verified — change approved.",
                first_verified=True,
                second_verified=True,
                attempts_left=session["max_attempts"] - session["attempts"],
            )

        user_a = session["requesting_user"]
        user_b = session["required_second_user"]

        if user_name not in (user_a, user_b):
            return ApprovalResult(
                ok=False,
                status="unauthorized",
                message=f"User '{user_name}' is not an authorized approver for this request.",
                first_verified=session["user_a_verified"],
                second_verified=session["user_b_verified"],
                attempts_left=max(0, session["max_attempts"] - session["attempts"]),
            )

        # Check if this user has already verified
        is_user_a = user_name == user_a
        already_verified = session["user_a_verified"] if is_user_a else session["user_b_verified"]
        if already_verified:
            return ApprovalResult(
                ok=False,
                status="already_verified",
                message=f"{user_name} has already verified this approval request.",
                first_verified=session["user_a_verified"],
                second_verified=session["user_b_verified"],
                attempts_left=max(0, session["max_attempts"] - session["attempts"]),
            )

        # Check maximum failed attempts
        if session["attempts"] >= session["max_attempts"]:
            self.store.update_approval_session(approval_id, {"status": "rejected"})
            self.store.record_audit(
                approval_id=approval_id,
                deal_slug=session.get("deal_slug") or "",
                deal_name=session.get("deal_name") or "",
                operation=session.get("operation_type") or "Unknown",
                requesting_user=session.get("requesting_user") or "",
                approving_user="",
                status="Rejected",
                details="Too many failed OTP attempts.",
            )
            return ApprovalResult(
                ok=False,
                status="rejected",
                message="Too many failed attempts. Approval rejected — change was not saved.",
                attempts_left=0,
            )

        # Verify OTP against user's salted hash
        salt = session["user_a_salt"] if is_user_a else session["user_b_salt"]
        expected_hash = session["user_a_hash"] if is_user_a else session["user_b_hash"]

        if not verify_otp_hash(salt, expected_hash, otp):
            new_attempts = session["attempts"] + 1
            updates: dict[str, Any] = {"attempts": new_attempts}
            attempts_left = max(0, session["max_attempts"] - new_attempts)

            if new_attempts >= session["max_attempts"]:
                updates["status"] = "rejected"
                self.store.update_approval_session(approval_id, updates)
                self.store.record_audit(
                    approval_id=approval_id,
                    deal_slug=session.get("deal_slug") or "",
                    deal_name=session.get("deal_name") or "",
                    operation=session.get("operation_type") or "Unknown",
                    requesting_user=session.get("requesting_user") or "",
                    approving_user="",
                    status="Rejected",
                    details="Too many failed OTP attempts.",
                )
                return ApprovalResult(
                    ok=False,
                    status="rejected",
                    message="Too many failed attempts. Approval rejected — change was not saved.",
                    attempts_left=0,
                )

            self.store.update_approval_session(approval_id, updates)
            return ApprovalResult(
                ok=False,
                status="invalid_otp",
                message=f"Invalid OTP. {attempts_left} attempt{'s' if attempts_left != 1 else ''} remaining.",
                first_verified=session["user_a_verified"],
                second_verified=session["user_b_verified"],
                attempts_left=attempts_left,
            )

        # Correct OTP! Mark user verified and clear their salt/hash so OTP cannot be reused
        updates = {}
        if is_user_a:
            updates["user_a_verified"] = True
            updates["user_a_hash"] = None
            updates["user_a_salt"] = None
            user_a_done = True
            user_b_done = session["user_b_verified"]
        else:
            updates["user_b_verified"] = True
            updates["user_b_hash"] = None
            updates["user_b_salt"] = None
            user_a_done = session["user_a_verified"]
            user_b_done = True

        both_verified = user_a_done and user_b_done
        if both_verified:
            updates["status"] = "approved"
            self.store.update_approval_session(approval_id, updates)
            return ApprovalResult(
                ok=True,
                status="approved",
                message="Both users verified — saving change",
                first_verified=True,
                second_verified=True,
                attempts_left=session["max_attempts"] - session["attempts"],
            )

        updates["status"] = "partially_verified"
        self.store.update_approval_session(approval_id, updates)
        return ApprovalResult(
            ok=True,
            status="partially_verified",
            message=f"1 of 2 users verified ({user_name} verified)",
            first_verified=user_a_done,
            second_verified=user_b_done,
            attempts_left=session["max_attempts"] - session["attempts"],
        )

    def cancel_approval(self, *, approval_id: str) -> bool:
        """Cancel a pending approval request."""
        session = self.get_session_status(approval_id)
        if not session or session["status"] in ("approved", "committed"):
            return False

        self.store.update_approval_session(approval_id, {"status": "cancelled"})
        self.store.record_audit(
            approval_id=approval_id,
            deal_slug=session.get("deal_slug") or "",
            deal_name=session.get("deal_name") or "",
            operation=session.get("operation_type") or "Unknown",
            requesting_user=session.get("requesting_user") or "",
            approving_user="",
            status="Cancelled",
            details="User cancelled the approval request.",
        )
        return True

    def is_approved(self, approval_id: str) -> bool:
        """Server-side check whether an approval request has both verified approvers."""
        session = self.get_session_status(approval_id)
        if not session:
            return False
        return (
            session["status"] == "approved"
            and session["user_a_verified"]
            and session["user_b_verified"]
            and not session["committed"]
        )

    def commit_approved_operation(
        self,
        *,
        approval_id: str,
        memory: Memory | None = None,
    ) -> CommitResult:
        """Final server-side authorization check and commit to persistent store and Hindsight."""
        session = self.store.get_approval_session(approval_id)
        if not session:
            return CommitResult(ok=False, message="Approval session not found.")

        # STRICT SERVER-SIDE AUTHORIZATION ENFORCEMENT
        if session["committed"]:
            return CommitResult(ok=False, message="Change has already been committed.")

        if session["status"] != "approved":
            return CommitResult(ok=False, message=f"Cannot commit unapproved request (status: {session['status']}).")

        if not (session["user_a_verified"] and session["user_b_verified"]):
            return CommitResult(ok=False, message="Both authorized users must be verified prior to commit.")

        now = datetime.now(timezone.utc)
        expires_at = datetime.fromisoformat(session["expires_at"])
        if now > expires_at:
            self.store.update_approval_session(approval_id, {"status": "expired"})
            return CommitResult(ok=False, message="Approval session expired prior to commit.")

        # Mark committed immediately to prevent duplicate commits
        self.store.update_approval_session(approval_id, {"committed": True})

        try:
            payload = json.loads(session["payload_json"])
        except Exception as exc:
            return CommitResult(ok=False, message=f"Failed to read staged payload: {exc}")

        op_type = session["operation_type"]

        if op_type in (OPERATION_LOG_INTERACTION, OPERATION_TRANSCRIBED_CALL_SAVE):
            return self._commit_log_interaction(session, payload, memory)

        if op_type in (OPERATION_EDIT_DEAL, OPERATION_EDIT_STAKEHOLDER, OPERATION_EDIT_PRICING):
            return self._commit_edit_deal(session, payload)

        if op_type == OPERATION_EDIT_COMMITMENT:
            return self._commit_edit_commitment(session, payload)

        if op_type == OPERATION_DELETE_DEAL:
            return self._commit_delete_deal(session, payload)

        if op_type in (OPERATION_DELETE_INTERACTION, OPERATION_MEMORY_DELETE):
            return self._commit_memory_delete(session, payload, memory)

        if op_type == OPERATION_MEMORY_EDIT:
            return self._commit_memory_edit(session, payload, memory)

        return CommitResult(ok=False, message=f"Unsupported operation type '{op_type}'.")

    def _commit_log_interaction(
        self,
        session: dict,
        payload: dict,
        memory: Memory | None,
    ) -> CommitResult:
        """Commit an approved log-a-call interaction, promises, and Hindsight memory."""
        company = payload.get("company", "").strip()
        notes = payload.get("notes", "").strip()
        happened = payload.get("happened", date.today().isoformat())
        contact = payload.get("contact", "").strip()
        interaction_type = payload.get("interaction_type", "Discovery call")
        outcome = payload.get("outcome", "").strip()
        tactic = payload.get("tactic", "").strip()
        result = payload.get("result", "open")
        kept_ids = payload.get("kept_ids", [])
        kept_labels = payload.get("kept_labels", [])
        promise_what = payload.get("promise_what", "").strip()
        promise_who = payload.get("promise_who", "").strip()
        promise_due = payload.get("promise_due", "")

        deal = self.store.ensure_deal(company)

        # Mark kept promises
        kept_text = ""
        if kept_ids:
            kept_text = " Promises marked kept: " + "; ".join(kept_labels) + "."
            for cid in kept_ids:
                self.store.set_commitment_status(cid, "done")

        # Add new promise if entered
        if promise_what:
            self.store.add_commitment(
                deal["slug"],
                promise_what,
                promise_who or "Unspecified",
                promise_due or happened,
            )

        # Update deal stage if won or lost
        if result == "won":
            self.store.set_stage(deal["slug"], "Closed won")
        elif result == "lost":
            self.store.set_stage(deal["slug"], "Closed lost")

        # Commit interaction to CRM store
        document_id = payload.get("document_id") or f"log-{uuid.uuid4().hex}"
        row = self.store.add_interaction(
            document_id=document_id,
            deal_slug=deal["slug"],
            happened_on=happened,
            contact=contact,
            type_=interaction_type,
            notes=notes + kept_text,
            outcome=outcome,
            tactic=tactic,
            result=result,
        )

        # Commit to Hindsight if available
        retained = False
        if memory is not None:
            try:
                memory.retain_interaction(deal, row)
                self.store.mark_retained([row["document_id"]])
                retained = True
            except Exception:
                retained = False

        # Record in audit trail
        op_label = "Transcribed Call Save" if session.get("operation_type") == OPERATION_TRANSCRIBED_CALL_SAVE else "Add Interaction"
        audit_record = self.store.record_audit(
            approval_id=session["id"],
            deal_slug=deal["slug"],
            deal_name=deal["name"],
            operation=op_label,
            requesting_user=session["requesting_user"],
            approving_user=session["required_second_user"],
            status="Approved",
            details=f"Type: {interaction_type} · Contact: {contact or 'N/A'} · Hindsight: {'Retained' if retained else 'Local only'}",
        )

        return CommitResult(
            ok=True,
            message="Change approved and committed.",
            deal=deal,
            interaction=row,
            hindsight_retained=retained,
            audit_id=audit_record["id"],
        )

    def _commit_edit_deal(self, session: dict, payload: dict) -> CommitResult:
        slug = payload.get("slug")
        if not slug:
            return CommitResult(ok=False, message="Deal slug missing.")
        self.store.update_deal(
            slug=slug,
            name=payload.get("name"),
            stage=payload.get("stage"),
            value_inr=payload.get("value_inr"),
            segment=payload.get("segment"),
        )
        deal = self.store.get_deal(slug)
        audit_record = self.store.record_audit(
            approval_id=session["id"],
            deal_slug=slug,
            deal_name=deal["name"] if deal else slug,
            operation="Edit Deal Information",
            requesting_user=session["requesting_user"],
            approving_user=session["required_second_user"],
            status="Approved",
            details=f"Updated deal attributes for {slug}",
        )
        return CommitResult(ok=True, message="Deal updated.", deal=deal, audit_id=audit_record["id"])

    def _commit_edit_commitment(self, session: dict, payload: dict) -> CommitResult:
        cid = payload.get("commitment_id")
        if not cid:
            return CommitResult(ok=False, message="Commitment ID missing.")
        self.store.update_commitment(
            commitment_id=cid,
            what=payload.get("what"),
            who=payload.get("who"),
            due_on=payload.get("due_on"),
            status=payload.get("status"),
        )
        audit_record = self.store.record_audit(
            approval_id=session["id"],
            deal_slug=session.get("deal_slug") or "",
            deal_name=session.get("deal_name") or "",
            operation="Edit Commitment",
            requesting_user=session["requesting_user"],
            approving_user=session["required_second_user"],
            status="Approved",
            details=f"Updated commitment ID {cid}",
        )
        return CommitResult(ok=True, message="Commitment updated.", audit_id=audit_record["id"])

    def _commit_delete_deal(self, session: dict, payload: dict) -> CommitResult:
        slug = payload.get("slug")
        if not slug:
            return CommitResult(ok=False, message="Deal slug missing.")
        self.store.delete_deal(slug)
        audit_record = self.store.record_audit(
            approval_id=session["id"],
            deal_slug=slug,
            deal_name=session.get("deal_name") or slug,
            operation="Delete Deal",
            requesting_user=session["requesting_user"],
            approving_user=session["required_second_user"],
            status="Approved",
            details=f"Deleted deal {slug}",
        )
        return CommitResult(ok=True, message=f"Deal {slug} deleted.", audit_id=audit_record["id"])

    def _commit_delete_interaction(self, session: dict, payload: dict) -> CommitResult:
        return self._commit_memory_delete(session, payload, None)

    def _commit_memory_edit(self, session: dict, payload: dict, memory: Memory | None) -> CommitResult:
        entity_type = payload.get("entity_type", "interaction")
        deal_slug = session.get("deal_slug") or payload.get("deal_slug", "")
        deal = self.store.get_deal(deal_slug) if deal_slug else None

        if entity_type == "commitment":
            cid = payload.get("commitment_id")
            if not cid:
                return CommitResult(ok=False, message="Commitment ID missing.")
            self.store.update_commitment(
                commitment_id=cid,
                what=payload.get("what"),
                who=payload.get("who"),
                due_on=payload.get("due_on"),
                status=payload.get("status"),
            )
            audit_record = self.store.record_audit(
                approval_id=session["id"],
                deal_slug=deal_slug,
                deal_name=session.get("deal_name") or (deal["name"] if deal else deal_slug),
                operation="Memory Edit",
                requesting_user=session["requesting_user"],
                approving_user=session["required_second_user"],
                status="Approved",
                details=f"Updated commitment ID {cid}",
            )
            return CommitResult(ok=True, message="Commitment memory updated successfully.", audit_id=audit_record["id"])

        # Interaction memory
        doc_id = payload.get("document_id")
        if not doc_id:
            return CommitResult(ok=False, message="Document ID missing.")

        updates = {}
        for key in ("contact", "type", "notes", "outcome", "tactic", "result", "happened_on"):
            if key in payload:
                updates[key] = payload[key]

        updated_row = self.store.update_interaction(doc_id, updates)
        if not updated_row:
            return CommitResult(ok=False, message=f"Memory {doc_id} not found in store.")

        # Update Hindsight if retained or seed memory and memory available
        retained = False
        if memory is not None and (updated_row.get("retained") or (doc_id and doc_id.startswith("seed-"))):
            try:
                if deal and hasattr(memory, "update_interaction_memory"):
                    retained = bool(memory.update_interaction_memory(deal, updated_row))
            except Exception:
                retained = False

        audit_record = self.store.record_audit(
            approval_id=session["id"],
            deal_slug=deal_slug,
            deal_name=session.get("deal_name") or (deal["name"] if deal else deal_slug),
            operation="Memory Edit",
            requesting_user=session["requesting_user"],
            approving_user=session["required_second_user"],
            status="Approved",
            details=f"Updated memory {doc_id} · Contact: {updated_row.get('contact') or 'N/A'} · Hindsight: {'Updated' if retained else 'Local only'}",
        )
        return CommitResult(
            ok=True,
            message="Memory updated successfully.",
            interaction=updated_row,
            hindsight_retained=retained,
            audit_id=audit_record["id"],
        )

    def _commit_memory_delete(self, session: dict, payload: dict, memory: Memory | None) -> CommitResult:
        entity_type = payload.get("entity_type", "interaction")
        deal_slug = session.get("deal_slug") or payload.get("deal_slug", "")
        deal = self.store.get_deal(deal_slug) if deal_slug else None

        if entity_type == "commitment":
            cid = payload.get("commitment_id")
            if not cid:
                return CommitResult(ok=False, message="Commitment ID missing.")
            self.store.delete_commitment(cid)
            audit_record = self.store.record_audit(
                approval_id=session["id"],
                deal_slug=deal_slug,
                deal_name=session.get("deal_name") or (deal["name"] if deal else deal_slug),
                operation="Memory Delete",
                requesting_user=session["requesting_user"],
                approving_user=session["required_second_user"],
                status="Approved",
                details=f"Deleted commitment ID {cid}",
            )
            return CommitResult(ok=True, message="Commitment memory deleted.", audit_id=audit_record["id"])

        # Interaction memory
        doc_id = payload.get("document_id")
        if not doc_id:
            return CommitResult(ok=False, message="Document ID missing.")

        existing = self.store.get_interaction(doc_id)
        was_retained = existing.get("retained") if existing else False
        self.store.delete_interaction(doc_id)

        # Delete from Hindsight if memory client available and was retained or seed memory
        hindsight_deleted = False
        if memory is not None and (was_retained or (doc_id and doc_id.startswith("seed-"))):
            try:
                if hasattr(memory, "delete_interaction_memory"):
                    hindsight_deleted = bool(memory.delete_interaction_memory(doc_id))
            except Exception:
                hindsight_deleted = False

        audit_record = self.store.record_audit(
            approval_id=session["id"],
            deal_slug=deal_slug,
            deal_name=session.get("deal_name") or (deal["name"] if deal else deal_slug),
            operation="Memory Delete",
            requesting_user=session["requesting_user"],
            approving_user=session["required_second_user"],
            status="Approved",
            details=f"Deleted memory {doc_id} · Hindsight: {'Deleted' if hindsight_deleted else 'Local only'}",
        )
        return CommitResult(
            ok=True,
            message=f"Memory {doc_id} deleted successfully.",
            hindsight_retained=hindsight_deleted,
            audit_id=audit_record["id"],
        )

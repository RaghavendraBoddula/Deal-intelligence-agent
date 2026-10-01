"""Developer CLI tool to view simulated OTP deliveries in development mode."""

import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    outbox_file = root / "data" / "dev_otp_outbox.json"

    if not outbox_file.exists():
        print(f"No dev OTP outbox file found at {outbox_file}")
        return

    try:
        with open(outbox_file, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except Exception as exc:
        print(f"Error reading outbox: {exc}")
        return

    if not entries:
        print("Dev OTP outbox is empty.")
        return

    print("================================================================================")
    print("           DEALRECALL TWO-PERSON AUTHORIZATION - DEV OTP OUTBOX")
    print("================================================================================")
    for entry in reversed(entries[-10:]):
        recipient = entry.get("recipient", "Unknown")
        otp = entry.get("otp", "N/A")
        ts = entry.get("timestamp", "")[:19].replace("T", " ")
        deal = entry.get("deal_name", "")
        op = entry.get("operation", "")
        print(f"[{ts} UTC] Recipient: {recipient:<10} | OTP: {otp} | Deal: {deal} ({op})")
    print("================================================================================")


if __name__ == "__main__":
    main()

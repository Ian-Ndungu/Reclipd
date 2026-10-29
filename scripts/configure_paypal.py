"""Store PayPal sandbox credentials privately; never enables real-money payments."""
import getpass
import json
import re
import os
from pathlib import Path
path=Path(__file__).resolve().parents[1]/".env"
print("Use SANDBOX app credentials from developer.paypal.com, not live credentials.")
values={
    "PAYPAL_CLIENT_ID":getpass.getpass("Sandbox Client ID (hidden): ").strip(),
    "PAYPAL_CLIENT_SECRET":getpass.getpass("Sandbox Secret (hidden): ").strip(),
    "PAYPAL_MERCHANT_ID":input("Sandbox seller's merchant ID: ").strip(),
    "PAYPAL_WEBHOOK_ID":input("Sandbox webhook ID (optional for local redirect testing): ").strip(),
}
if not all(values[key] for key in ["PAYPAL_CLIENT_ID","PAYPAL_CLIENT_SECRET","PAYPAL_MERCHANT_ID"]):
    raise SystemExit("Client ID, secret and merchant ID are required. No changes saved.")
if not re.fullmatch(r"[A-Z0-9]{13}", values["PAYPAL_MERCHANT_ID"]):
    raise SystemExit("Merchant ID must be the sandbox seller’s 13-character account merchant ID, not an app Client ID or Secret. No changes saved.")
values["PAYPAL_SANDBOX_ENABLED"]="true"
lines=path.read_text().splitlines()
lines=[line for line in lines if line.split("=",1)[0] not in values]
lines += [f"{key}={json.dumps(value)}" for key,value in values.items()]
path.write_text("\n".join(lines)+"\n")
os.chmod(path,0o600)
print("Sandbox configuration saved. Restart: docker compose up -d --force-recreate api")

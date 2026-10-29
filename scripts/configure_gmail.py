"""Configure development SMTP locally without echoing or logging credentials."""
import getpass
import json
import os
from pathlib import Path

path=Path(__file__).resolve().parents[1]/".env"
email=input("Gmail address to send reset emails from: ").strip()
if "@" not in email or any(c in email for c in "\r\n"):
    raise SystemExit("Enter a valid email address.")
password=getpass.getpass("Google App Password (hidden; not your normal password): ").replace(" ","")
if len(password)!=16 or not password.isalnum():
    raise SystemExit("Use the 16-character app password from Google.")
values={"SMTP_HOST":"smtp.gmail.com","SMTP_PORT":"587","SMTP_USERNAME":email,
        "SMTP_PASSWORD":password,"SMTP_FROM":email,"APP_URL":"http://localhost:5173"}
lines=path.read_text().splitlines() if path.exists() else []
lines=[line for line in lines if line.split("=",1)[0] not in values]
lines += [f"{key}={json.dumps(value)}" for key,value in values.items()]
path.write_text("\n".join(lines)+"\n")
os.chmod(path,0o600)
print("Saved Gmail configuration in the local .env. Restart api: docker compose up -d --force-recreate api")

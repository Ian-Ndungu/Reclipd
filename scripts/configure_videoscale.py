"""Save VideoScale Basic Auth privately. Does not enable imports or spend credits."""
import base64
import binascii
import getpass
import json
import os
from pathlib import Path
import tempfile
import warnings


def normalize_header(value: str) -> str:
    value = value.strip()
    if value.lower().startswith("authorization:"):
        value = value.split(":", 1)[1].strip()
    if value.lower().startswith("basic "):
        value = value[6:].strip()
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("Enter the complete Base64 Basic Auth value.") from None
    username, separator, password = decoded.partition(b":")
    if not separator or not username or not password or any(c in decoded for c in (b"\r", b"\n", b"\x00")):
        raise ValueError("The Basic Auth value must contain a username and password.")
    return "Basic " + base64.b64encode(decoded).decode("ascii")


def main():
    path = Path(__file__).resolve().parents[1] / ".env"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            header = normalize_header(getpass.getpass("VideoScale Basic Auth header (hidden): "))
    except (ValueError, getpass.GetPassWarning) as exc:
        raise SystemExit(str(exc) if isinstance(exc, ValueError) else "Use an interactive terminal with hidden input.") from None
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("Cancelled. Nothing saved.") from None
    values = {"VIDEOSCALE_AUTH_HEADER": header, "VIDEOSCALE_ENABLED": "false"}
    lines = path.read_text().splitlines() if path.exists() else []
    lines = [line for line in lines if line.split("=", 1)[0].strip() not in values]
    lines += [key + "=" + json.dumps(value) for key, value in values.items()]
    fd, temporary = tempfile.mkstemp(prefix=".videoscale-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            output.write("\n".join(lines) + "\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("Saved privately in .env. Imports remain disabled; no API request or credit spend occurred.")
    print("Tell Codex setup is complete so the provider can be tested securely from Oracle.")


if __name__ == "__main__":
    main()

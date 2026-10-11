"""Create development configuration without exposing the generated secret."""

from pathlib import Path
import secrets

root = Path(__file__).resolve().parent.parent
output = root / ".env"
if output.exists():
    print(".env already exists; left unchanged.")
else:
    output.write_text(
        (root / ".env.example")
        .read_text()
        .replace(
            "replace-this-with-a-random-secret-at-least-32-characters",
            secrets.token_urlsafe(48),
        )
    )
    output.chmod(0o600)
    print(
        "Created .env with a random session secret. Run docker compose up --build -d."
    )

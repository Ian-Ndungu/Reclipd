from pathlib import Path
import shutil
import subprocess
import pytest
from fontTools.ttLib import TTFont
from app.main import BUILTIN_FONTS
from app.schemas import CaptionStyle
from app.media import write_ass


def test_all_builtin_faces_are_real_and_accepted(signed, tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("Run in the font-equipped Docker image")
    assert len(BUILTIN_FONTS) == 38
    families = set()
    for slug, filename in BUILTIN_FONTS.items():
        assert Path(filename).is_file(), filename
        with TTFont(filename) as font:
            family = font["name"].getDebugName(1)
            families.add(family)
            postscript = font["name"].getDebugName(6)
            style = CaptionStyle(
                font=family, weight=700 if slug.endswith(("bold", "700")) else 400
            ).model_dump()
        response = signed.get("/api/fonts/" + slug)
        assert response.status_code == 200
        assert len(response.content) > 1000
        ass = tmp_path / "caption.ass"
        write_ass(ass, [{"word": "Preview", "start": 0, "end": 1}], style, 360, 640)
        result = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "info",
                "-f",
                "lavfi",
                "-i",
                "color=black:s=360x640:d=1",
                "-vf",
                f"ass={ass}",
                "-frames:v",
                "1",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == 0, result.stderr
        selected = [
            line.split("->", 1)[-1]
            for line in result.stderr.splitlines()
            if "fontselect:" in line
        ]
        assert any(postscript in line for line in selected), (slug, selected)
    assert len(families) == 19

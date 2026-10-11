# Third-party components and font notices

RECLIPD uses upstream open-source packages. Package metadata and distribution license files remain authoritative. No ownership of these components is claimed.

- **DejaVu fonts**: derived from Bitstream Vera; distributed under their font license with DejaVu additions. The Docker image installs Debian's `fonts-dejavu-core` package and retains `/usr/share/doc/fonts-dejavu-core/copyright`.
- **Liberation fonts**: distributed under the SIL Open Font License in the current Debian package. The image retains `/usr/share/doc/fonts-liberation/copyright`.
- **FFmpeg**: the Debian build includes GPL components such as libx264. Review the installed package's licensing obligations before distributing modified/bundled binaries. License material remains under `/usr/share/doc/ffmpeg` and related package directories.
- **faster-whisper / CTranslate2 / Whisper weights**: upstream code and model licenses apply. Model downloads occur at runtime; provision licensed model artifacts for offline deployment.
- **PySceneDetect**, **OpenCV**, **React**, **Vite**, **FastAPI**, **SQLAlchemy**, **Celery**, and other dependencies retain their respective upstream licenses.
- **Custom fonts and logos**: users must have the rights to use and embed uploaded assets. Technical embedding-flag checks do not establish legal ownership.

No externally sourced photographs, paid fonts, or stock video assets are included. Studio illustrations are generated from original CSS shapes.

Additional built-in families are installed from Debian packages, with their upstream copyright/license files retained under `/usr/share/doc/`: `fonts-lato`, `fonts-freefont-ttf`, `fonts-crosextra-carlito`, and `fonts-crosextra-caladea`. GNU FreeFont includes its font embedding exception; consult the packaged license when redistributing fonts. DejaVu Serif and DejaVu Sans Mono use the existing DejaVu package. No paid font service is required.

Inter, Poppins, Montserrat, Anton, Bebas Neue, Oswald and DM Sans are bundled from the Google Fonts repository under SIL Open Font License 1.1. Individual OFL notices are retained in `backend/fonts/`; the UI Inter notice is in `frontend/public/fonts/`. `scripts/provision_fonts.py` records source URLs and generates static weight instances. Anton and Bebas Neue have one upstream weight reused for the two requested weight slots.

Optional YouTube retrieval uses yt-dlp (Unlicense) and its packaged default dependencies, including yt-dlp-ejs, plus Node.js from the official Node Docker image. Consult their upstream license notices before redistribution. No OpusClip service is involved.

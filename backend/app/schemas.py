from typing import Literal
from pydantic import (
    BaseModel as PydanticBaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class AuthIn(BaseModel):
    email: str = Field(
        min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    )
    password: str = Field(min_length=10, max_length=128)
    name: str = Field(default="Creator", min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def normalize(cls, v):
        return v.lower().strip()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    name: str
    is_admin: bool
    used_seconds: float


from pathlib import Path
import json

CAPTION_PRESETS = json.loads(
    Path(__file__).with_name("caption_presets.json").read_text()
)


class ProjectConfig(BaseModel):
    content_category: Literal[
        "auto", "podcast", "interview", "education", "product", "commentary"
    ] = "auto"
    instructions: str = Field(default="", max_length=1000)
    caption_preset: str = "bold"
    aspect_ratio: Literal["9:16"] = "9:16"
    clip_count: int = Field(default=5, ge=1, le=10)
    min_duration: int = Field(default=15, ge=5, le=120)
    max_duration: int = Field(default=60, ge=5, le=180)
    language: str | None = Field(default=None, pattern=r"^[a-z]{2,3}$")

    @model_validator(mode="after")
    def durations(self):
        if self.caption_preset not in CAPTION_PRESETS:
            raise ValueError("Unknown caption preset")
        if self.max_duration < self.min_duration:
            raise ValueError("Maximum duration must be at least minimum duration")
        return self


class ImportPreviewIn(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    source_url: str | None = Field(default=None, max_length=2048)


class ImportPreviewOut(BaseModel):
    kind: Literal["youtube", "direct"]
    video_id: str | None = None
    title: str | None = None
    channel: str | None = None
    thumbnail: str | None = None
    duration: int | None = None
    available: bool
    message: str
    metadata_error: str | None = None
    provider: str | None = None


class ImportIn(ImportPreviewIn):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(max_length=2048)
    rights_confirmed: Literal[True]
    config: ProjectConfig = Field(default_factory=ProjectConfig)


class CaptionStyle(BaseModel):
    preset: Literal[
        "bold",
        "minimal",
        "neon",
        "pop",
        "boxed",
        "editorial",
        "podcast",
        "documentary",
        "typewriter",
        "studio",
        "mint",
        "coral",
        "lavender",
        "mono",
        "serif",
        "headline",
        "lecture",
        "cinema",
        "contrast",
        "soft",
    ] = "bold"
    enabled: bool = True
    font: Literal[
        "DejaVu Sans",
        "Liberation Sans",
        "Liberation Serif",
        "Liberation Mono",
        "DejaVu Serif",
        "DejaVu Sans Mono",
        "Lato",
        "FreeSans",
        "FreeSerif",
        "FreeMono",
        "Carlito",
        "Caladea",
        "Inter",
        "Poppins",
        "Montserrat",
        "Anton",
        "Bebas Neue",
        "Oswald",
        "DM Sans",
    ] = "DejaVu Sans"
    custom_font_id: str | None = None
    size: int = Field(default=64, ge=24, le=140)
    weight: Literal[400, 700] = 700
    color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    emphasis_color: str = Field(default="#4D8DFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    stroke: int = Field(default=3, ge=0, le=8)
    shadow: int = Field(default=2, ge=0, le=8)
    stroke_color: str = Field(default="#000000", pattern=r"^#[0-9A-Fa-f]{6}$")
    background: bool = False
    background_color: str = Field(default="#111827", pattern=r"^#[0-9A-Fa-f]{6}$")
    letter_spacing: float = Field(default=0, ge=0, le=12)
    placement: Literal["top", "center", "bottom"] = "bottom"
    animation: Literal["none", "highlight", "fade"] = "highlight"


class Word(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    word: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def bounds(self):
        if self.end <= self.start:
            raise ValueError("Word end must follow start")
        return self


class Segment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)

    @model_validator(mode="after")
    def bounds(self):
        if self.end <= self.start:
            raise ValueError("End must follow start")
        return self


class EditDecision(BaseModel):
    segments: list[Segment] = Field(min_length=1, max_length=20)
    captions: CaptionStyle = Field(default_factory=CaptionStyle)
    words: list[Word] = Field(default_factory=list, max_length=10000)
    reframe: Literal["auto", "manual", "fit"] = "auto"
    focus_x: float = Field(default=0.5, ge=0, le=1)
    resolution: Literal[720, 1080] = 1080
    headline: str = Field(default="", max_length=240)
    show_headline: bool = False
    volume: float = Field(default=1, ge=0, le=1)
    brand_kit_id: str | None = None
    logo_asset_id: str | None = None


class SaveEdits(BaseModel):
    revision: int = Field(ge=0)
    edits: EditDecision


class BrandIn(BaseModel):
    logo_asset_id: str | None = None
    name: str = Field(min_length=1, max_length=100)
    captions: CaptionStyle = Field(default_factory=CaptionStyle)
    resolution: Literal[720, 1080] = 1080


class HeadlineIn(BaseModel):
    tone: Literal[
        "funny", "dramatic", "informative", "concise", "viral", "curiosity", "minimal"
    ] = "concise"
    count: int = Field(default=5, ge=3, le=10)
    max_characters: int = Field(default=90, ge=40, le=140)


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


from datetime import datetime


class HeadlineOut(BaseModel):
    text: str
    source: str
    tone: str


class ClipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    title: str
    start: float
    end: float
    score: float
    description: str
    reasons: list[str]
    headlines: list[HeadlineOut]
    edits: dict
    revision: int


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    status: str
    progress: int
    stage: str
    error: str | None
    media: dict
    config: dict
    analysis: dict
    created_at: datetime


class ProjectDetail(ProjectOut):
    transcript: list[Word]
    clips: list[ClipOut]


class ClipDetail(BaseModel):
    clip: ClipOut
    project: ProjectOut


class ExportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    clip_id: str
    status: str
    progress: int
    error: str | None
    created_at: datetime


class BrandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    config: dict


class UsageOut(BaseModel):
    plan: str
    used_seconds: float
    limit_seconds: int
    billing_enabled: bool


class ConnectSourceIn(BaseModel):
    url: str = Field(max_length=2048)
    project_id: str
    rights_confirmed: Literal[True]

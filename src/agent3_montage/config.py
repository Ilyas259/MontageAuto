"""
Configuration du module de montage — Pydantic v2.7+.
Paramètres externalisables chargés depuis config.yaml.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MontageConfig(BaseModel):
    """Configuration complète du pipeline de montage."""

    # === Résolution & FPS ===
    output_resolution: str = "1920x1080"
    fps: int = 30

    # === Transitions ===
    transition_default: Literal["cut", "fade", "slide", "zoom"] = "cut"
    transition_duration: float = 0.3

    # === Sous-titres ===
    subtitle_style: Literal["karaoke", "block", "none"] = "block"
    subtitle_font: str = "Inter"
    subtitle_font_size: int = 28
    subtitle_color: str = "#FFFFFF"
    subtitle_stroke_color: str = "#000000"
    subtitle_stroke_width: int = 1
    subtitle_position: Literal["bottom", "top", "center"] = "bottom"
    subtitle_margin_bottom: int = 60
    karaoke_highlight_color: str = "#FFD700"
    karaoke_advance_mode: Literal["word", "char"] = "word"

    # === B-rolls ===
    b_roll_transition: Literal["fade", "slide", "cut"] = "fade"
    min_broll_duration: float = 2.0
    max_broll_duration: float = 15.0
    broll_asset_dirs: list[str] = Field(
        default=["./assets/broll", "./assets/images"],
        alias="broll_search_paths",
    )
    broll_search_paths: list[str] = Field(
        default=["./assets/broll", "./assets/images"],
        deprecated="Use broll_asset_dirs instead",
    )

    # === Facecam ===
    facecam_position: Literal[
        "bottom-right", "bottom-left", "top-right", "top-left"
    ] = "bottom-right"
    facecam_size: float = Field(default=0.25, ge=0.05, le=1.0)
    facecam_corner_radius: int = 12
    facecam_shadow: bool = True
    facecam_border: bool = False

    # === Performance ===
    preview_scale: float = Field(default=0.5, ge=0.1, le=1.0)
    preview_fps: int = 15
    preview_resolution: str = "640x360"
    max_concurrent_renders: int = 2
    cache_dir: str = "./.cache/agent3_montage"
    clean_cache_after: bool = False

    # === Encodage ===
    codec: Literal["h264", "h265", "h264_nvenc", "h265_nvenc"] = "h264"
    crf: int = Field(default=23, ge=0, le=51)
    preset: Literal[
        "ultrafast", "fast", "medium", "slow", "veryslow"
    ] = "medium"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"

    # === Boucle qualité ===
    quality_loop_endpoint: str = "http://localhost:8085/api/quality"
    quality_loop_api_key: str = ""
    quality_max_iterations: int = 3
    max_iterations: int = 3
    auto_apply_feedback: bool = True

    # === Validation ===
    @model_validator(mode="after")
    def validate_resolution(self) -> "MontageConfig":
        parts = self.output_resolution.split("x")
        if len(parts) != 2:
            raise ValueError(
                f"output_resolution must be WxH (e.g. 1920x1080), "
                f"got {self.output_resolution!r}"
            )
        w, h = int(parts[0]), int(parts[1])
        if w % 2 != 0 or h % 2 != 0:
            raise ValueError(
                "Resolution dimensions must be even for codec compliance"
            )
        return self

    @property
    def preview_resolution(self) -> str:
        """Calcule la résolution preview à partir du scale factor."""
        w, h = self.output_resolution.split("x")
        pw = int(int(w) * self.preview_scale)
        ph = int(int(h) * self.preview_scale)
        pw = pw if pw % 2 == 0 else pw + 1
        ph = ph if ph % 2 == 0 else ph + 1
        return f"{pw}x{ph}"

    @property
    def has_gpu(self) -> bool:
        return "nvenc" in self.codec

    @property
    def output_size(self) -> tuple[int, int]:
        parts = self.output_resolution.split("x")
        return int(parts[0]), int(parts[1])

    @classmethod
    def load(cls, path: str | Path) -> "MontageConfig":
        """Charge depuis YAML (ou retourne les defaults si le fichier n'existe pas)."""
        p = Path(path)
        if not p.exists():
            import warnings
            warnings.warn(f"Config file not found: {p}, using defaults")
            return cls()
        return cls.from_yaml(str(path))

    @classmethod
    def from_yaml(cls, path: str) -> "MontageConfig":
        """Charge la configuration depuis un fichier YAML."""
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        montage_data = data.get("montage", data)
        return cls(**montage_data)

    def to_yaml(self, path: str) -> None:
        """Exporte la configuration en YAML."""
        import yaml
        with open(path, "w") as f:
            yaml.dump({"montage": self.model_dump()}, f, default_flow_style=False)

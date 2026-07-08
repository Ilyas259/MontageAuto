"""
Renderer Remotion (open source) — fallback quand Hyperframes n'est pas disponible.
Nécessite Node.js 20+ et @remotion/renderer.

Dépendances : Node.js, Puppeteer (~300MB Chromium), @remotion/packages
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from uuid import uuid4

from agent3_montage.renderers.base import AbstractRenderer, CompositionConfig

logger = logging.getLogger(__name__)


class RemotionError(Exception):
    """Erreur Remotion."""
    pass


class RemotionRenderer(AbstractRenderer):
    """
    Renderer utilisant Remotion (open source).

    Convertit les templates Pydantic en composants React,
    bundle le projet, et rend via Puppeteer + FFmpeg.
    """

    TEMPLATE_DIR = Path(__file__).parent.parent / "remotion_templates"

    def __init__(self, node_path: str = "node"):
        self.node_path = node_path

    async def is_available(self) -> bool:
        """Vérifie que Node.js et les packages Remotion sont installés."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.node_path, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                return False

            version = stdout.decode().strip().lstrip("v")
            major = int(version.split(".")[0])
            if major < 20:
                logger.warning(f"Remotion needs Node.js 20+, found {version}")
                return False

            if not (self.TEMPLATE_DIR / "package.json").exists():
                logger.warning(
                    "Remotion templates not found. "
                    "Run: cd remotion_templates && npm install"
                )
                return False

            return True

        except FileNotFoundError:
            return False

    async def get_version(self) -> str:
        pkg = self.TEMPLATE_DIR / "package.json"
        if pkg.exists():
            data = json.loads(pkg.read_text())
            return data.get("dependencies", {}).get(
                "@remotion/renderer", "unknown"
            )
        return "unknown"

    async def get_name(self) -> str:
        return "Remotion"

    async def render(self, composition: CompositionConfig) -> Path:
        """Rendu via Remotion avec génération de template React."""
        template_path = await self._generate_react_template(composition)

        cmd = [
            self.node_path,
            str(self.TEMPLATE_DIR / "render.mjs"),
            "--input", str(template_path),
            "--output", str(composition.output_path),
            "--resolution", composition.config.output_resolution,
            "--fps", str(composition.config.fps),
        ]
        if composition.mode == "preview":
            cmd.extend(["--quality", "low"])

        logger.info(f"Starting Remotion render: {composition.output_path.name}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode()[:500] if stderr else "Unknown error"
            raise RemotionError(f"Remotion render failed: {error_msg}")

        logger.info(f"Remotion render complete: {composition.output_path}")
        return composition.output_path

    async def render_preview(self, composition: CompositionConfig) -> Path:
        composition.mode = "preview"
        return await self.render(composition)

    async def _generate_react_template(
        self, composition: CompositionConfig
    ) -> Path:
        """
        Génère un fichier TSX avec la composition encodée en JSON.
        Les composants React statiques vivent dans remotion_templates/src/.
        """
        output = self.TEMPLATE_DIR / "_generated" / f"edit_{uuid4().hex}.tsx"
        output.parent.mkdir(parents=True, exist_ok=True)

        data_file = output.with_suffix(".data.json")
        data_file.write_text(
            json.dumps(self._composition_to_dict(composition), indent=2)
        )

        # Construction du TSX sans f-string pour éviter les conflits de braces
        tsx_lines = [
            'import React from "react";',
            'import { AbsoluteFill } from "remotion";',
            'import compositionData from "./' + data_file.name + '";',
            'import { Facecam } from "../src/Facecam";',
            'import { SplitScreen } from "../src/SplitScreen";',
            'import { FullBroll } from "../src/FullBroll";',
            'import { Subtitles } from "../src/Subtitles";',
            "",
            "export const Edit: React.FC = () => {",
            "  const data = compositionData;",
            "  const [width, height] = data.config.output_resolution",
            '    .split("x")',
            "    .map(Number);",
            "",
            "  const typeToComponent: Record<string, any> = {",
            "    facecam: Facecam,",
            "    split: SplitScreen,",
            '    full_broll: FullBroll,',
            "  };",
            "",
            "  return (",
            "    <AbsoluteFill",
            "      style={{",
            "        backgroundColor: '#000',",
            "        width,",
            "        height,",
            "      }}",
            "    >",
            "      {data.segments.map((seg: any, i: number) => {",
            "        const Component = typeToComponent[seg.template.type] || Facecam;",
            "        return <Component key={seg.segment_id} segment={seg} />;",
            "      })}",
            "      {data.subtitles.type === 'karaoke' && (",
            "        <Subtitles",
            "          words={data.subtitles.words}",
            "          config={data.subtitles}",
            "        />",
            "      )}",
            "    </AbsoluteFill>",
            "  );",
            "};",
            "",
        ]

        output.write_text("\n".join(tsx_lines))
        return output

    @staticmethod
    def _composition_to_dict(composition: CompositionConfig) -> dict:
        return {
            "config": composition.config.model_dump(),
            "segments": [
                {
                    "segment_id": s.segment_id,
                    "template": s.template.model_dump(),
                    "source_clip": str(s.source_clip),
                    "broll_clips": [str(b) for b in s.broll_clips],
                    "broll_placements": [
                        b.model_dump() for b in s.broll_placements
                    ],
                }
                for s in composition.segments
            ],
            "subtitles": composition.subtitles,
            "mode": composition.mode,
        }

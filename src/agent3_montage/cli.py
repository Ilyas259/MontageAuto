"""
Interface en ligne de commande (CLI) du module Montage & Animation.

Usage :
    python -m agent3_montage.cli run cut_list.json source.mp4 output.mp4 [options]
    python -m agent3_montage.cli preview cut_list.json source.mp4 output_preview.mp4
    python -m agent3_montage.cli extract source.mp4 --segments '[{...}]'
    python -m agent3_montage.cli templates list
    python -m agent3_montage.cli templates show <name>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Ajouter le chemin racine du projet pour les imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from agent3_montage.config import MontageConfig
from agent3_montage.models import CompositionTemplate, CutSegment
from agent3_montage.orchestrator import MontagePipeline
from agent3_montage.renderers import RendererFactory
from agent3_montage.template_engine import TemplateEngine
from agent3_montage.subtitles import SubtitleEngine

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Construit le parseur d'arguments CLI."""
    parser = argparse.ArgumentParser(
        prog="agent3-montage",
        description="Agent #3 — Montage & Animation : pipeline de montage vidéo automatisé",
    )
    sub = parser.add_subparsers(dest="command", help="Commande à exécuter")

    # ── run ──
    run_p = sub.add_parser("run", help="Exécuter le pipeline complet")
    run_p.add_argument("cut_list", type=Path, help="Chemin vers cut_list.json")
    run_p.add_argument("source", type=Path, help="Chemin vers la vidéo source")
    run_p.add_argument("output", type=Path, help="Chemin de sortie")
    run_p.add_argument("--config", "-c", type=Path, default=None, help="Fichier config.yaml")
    run_p.add_argument("--preview", "-p", action="store_true", help="Mode preview basse résolution")
    run_p.add_argument("--skip-quality", "-q", action="store_true", help="Sauter la boucle qualité")
    run_p.add_argument("--script", "-s", type=Path, default=None, help="Script nettoyé (Agent #2)")
    run_p.add_argument("--words", "-w", type=Path, default=None, help="Timings mot-à-mot (JSON)")
    run_p.add_argument("--renderer", "-r", type=str, default=None, choices=["hyperframes", "remotion", "ffmpeg"],
                       help="Forcer un renderer spécifique")
    run_p.add_argument("--verbose", "-v", action="store_true", help="Logs détaillés")

    # ── preview (alias pour run --preview) ──
    prev_p = sub.add_parser("preview", help="Générer une preview rapide")
    prev_p.add_argument("cut_list", type=Path)
    prev_p.add_argument("source", type=Path)
    prev_p.add_argument("output", type=Path)
    prev_p.add_argument("--config", "-c", type=Path, default=None)
    prev_p.add_argument("--skip-quality", "-q", action="store_true")

    # ── extract ──
    ext_p = sub.add_parser("extract", help="Extraire des segments d'une source")
    ext_p.add_argument("source", type=Path, help="Vidéo source")
    ext_p.add_argument("--segments", type=str, default=None,
                       help="JSON inline des segments [{'start': 10, 'end': 20, 'id': 'seg1'}]")
    ext_p.add_argument("--output-dir", "-o", type=Path, default=Path("extracted"), help="Dossier de sortie")

    # ── templates ──
    tpl_p = sub.add_parser("templates", help="Gérer les templates de composition")
    tpl_sub = tpl_p.add_subparsers(dest="tpl_cmd")
    tpl_sub.add_parser("list", help="Lister les templates disponibles")
    show_p = tpl_sub.add_parser("show", help="Afficher un template")
    show_p.add_argument("name", type=str, help="Nom du template")

    # ── subtitles ──
    sub_p = sub.add_parser("subtitles", help="Générer les sous-titres")
    sub_p.add_argument("cut_list", type=Path)
    sub_p.add_argument("--output", "-o", type=Path, default=Path("subtitles.srt"),
                       help="Fichier SRT de sortie")
    sub_p.add_argument("--style", type=str, default="block",
                       choices=["block", "karaoke", "none"])
    sub_p.add_argument("--words", "-w", type=Path, default=None,
                       help="Timings mot-à-mot (JSON, pour karaoke)")

    # ── info ──
    info_p = sub.add_parser("info", help="Afficher les infos du système")
    info_p.add_argument("--verbose", "-v", action="store_true")

    return parser


async def cmd_run(args: argparse.Namespace) -> int:
    """Exécute la commande `run`."""
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    config = MontageConfig.load(args.config) if args.config else MontageConfig()

    if args.renderer:
        renderer = await RendererFactory.create_preferred(args.renderer)
        # On force le renderer via config
        pass

    words = None
    if args.words:
        words = json.loads(args.words.read_text())

    pipeline = MontagePipeline(config=config)
    result = await pipeline.run(
        cut_list_path=args.cut_list,
        source_video=args.source,
        output_path=args.output,
        script_cleaned=args.script,
        words_timings=words,
        preview=False,
        skip_quality=args.skip_quality,
    )

    print(f"\n✅ Vidéo générée : {result}")
    return 0


async def cmd_preview(args: argparse.Namespace) -> int:
    """Exécute la commande `preview`."""
    config = MontageConfig.load(args.config) if args.config else MontageConfig()

    pipeline = MontagePipeline(config=config)
    result = await pipeline.run(
        cut_list_path=args.cut_list,
        source_video=args.source,
        output_path=args.output,
        preview=True,
        skip_quality=args.skip_quality,
    )

    print(f"\n✅ Preview générée : {result}")
    return 0


async def cmd_extract(args: argparse.Namespace) -> int:
    """Exécute la commande `extract`."""
    from agent3_montage.ffmpeg_ops import FFmpegOps

    if args.segments:
        seg_data = json.loads(args.segments)
    else:
        print("❌ Spécifiez --segments avec le JSON des segments à extraire")
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)

    segments = [CutSegment(**s) for s in seg_data]
    tasks = []
    for seg in segments:
        out = args.output_dir / f"seg_{seg.id}.mp4"
        tasks.append(
            FFmpegOps.extract_segment_accurate(
                args.source, seg.start_time, seg.end_time, out
            )
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)
    success = sum(1 for r in results if not isinstance(r, Exception))
    print(f"✅ {success}/{len(segments)} segments extraits dans {args.output_dir}")
    return 0


async def cmd_templates(args: argparse.Namespace) -> int:
    """Gère les templates."""
    from agent3_montage.templates import register_all

    register_all()

    if args.tpl_cmd == "list":
        templates = TemplateEngine.list_templates()
        print(f"Templates disponibles ({len(templates)}) :")
        for t in templates:
            print(f"  • {t.name:25s}  type={t.type:15s}  dur={t.default_duration:.1f}s")
        return 0

    elif args.tpl_cmd == "show":
        t = TemplateEngine.get(args.name)
        if not t:
            print(f"❌ Template '{args.name}' introuvable")
            return 1
        print(t.model_dump_json(indent=2))
        return 0

    return 0


async def cmd_subtitles(args: argparse.Namespace) -> int:
    """Génère les sous-titres."""
    config = MontageConfig()
    config.subtitle_style = args.style

    data = json.loads(args.cut_list.read_text())
    segments = [CutSegment(**s) for s in data.get("segments", [])]

    words = None
    if args.words:
        words = json.loads(args.words.read_text())

    engine = SubtitleEngine.from_montage_config(config)
    events = engine.generate_events(segments, words)
    engine.export_srt(events, args.output)

    print(f"✅ {sum(len(e) for e in events)} sous-titres générés → {args.output}")
    return 0


async def cmd_info(args: argparse.Namespace) -> int:
    """Affiche les infos du système."""
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    print("=" * 50)
    print("Agent #3 — Montage & Animation : Diagnostic système")
    print("=" * 50)

    # FFmpeg
    import subprocess
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        ff_ver = r.stdout.split("\n")[0]
        print(f"  ✅ FFmpeg : {ff_ver}")
    except FileNotFoundError:
        print("  ❌ FFmpeg : introuvable")

    # Hyperframes
    try:
        import httpx
        r = await httpx.AsyncClient().get("http://localhost:3000/api/health", timeout=3)
        if r.status_code == 200:
            print("  ✅ Hyperframes : disponible (localhost:3000)")
        else:
            print(f"  ⚠️  Hyperframes : retourne {r.status_code}")
    except Exception:
        print("  ❌ Hyperframes : non disponible")

    # Node.js / Remotion
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True)
        print(f"  ✅ Node.js : {r.stdout.strip()}")
        rm_pkg = Path(__file__).parent.parent / "remotion_templates" / "package.json"
        if rm_pkg.exists():
            import json
            pkgs = json.loads(rm_pkg.read_text())
            ver = pkgs.get("dependencies", {}).get("@remotion/renderer", "?")
            print(f"  ✅ Remotion : {ver}")
        else:
            print("  ⚠️  Remotion : templates non installés")
    except FileNotFoundError:
        print("  ❌ Node.js : introuvable")

    return 0


async def main() -> int:
    """Point d'entrée principal."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch
    handlers = {
        "run": cmd_run,
        "preview": cmd_preview,
        "extract": cmd_extract,
        "templates": cmd_templates,
        "subtitles": cmd_subtitles,
        "info": cmd_info,
    }

    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    from agent3_montage.templates import register_all
    register_all()

    try:
        return await handler(args)
    except Exception as e:
        logger.exception(f"❌ Erreur : {e}")
        print(f"❌ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

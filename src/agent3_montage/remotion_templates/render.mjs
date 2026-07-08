/**
 * Script de rendu Remotion — point d'entrée Node.js
 *
 * Usage :
 *   node render.mjs \
 *     --input ./_generated/edit_xxx.tsx \
 *     --output ./output.mp4 \
 *     --resolution 1920x1080 \
 *     --fps 30 \
 *     [--quality low]
 *
 * Bundle le projet Remotion, rend les frames via Puppeteer,
 * et assemble la vidéo avec FFmpeg.
 */

import { bundle } from "@remotion/bundler";
import { getCompositions, renderMedia, RenderInternals } from "@remotion/renderer";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function main() {
  const args = process.argv.slice(2);
  const inputFile = args[args.indexOf("--input") + 1];
  const outputFile = args[args.indexOf("--output") + 1];
  const resolution = (args[args.indexOf("--resolution") + 1] || "1920x1080").split("x").map(Number);
  const fps = parseInt(args[args.indexOf("--fps") + 1] || "30", 10);
  const quality = args[args.indexOf("--quality") + 1] || "high";

  if (!inputFile || !outputFile) {
    console.error("Usage: node render.mjs --input <tsx> --output <mp4> [--resolution WxH] [--fps N] [--quality low|high]");
    process.exit(1);
  }

  const inputAbs = path.resolve(__dirname, inputFile);
  const outputAbs = path.resolve(__dirname, outputFile);

  if (!fs.existsSync(inputAbs)) {
    console.error(`Input file not found: ${inputAbs}`);
    process.exit(1);
  }

  console.log(`📦 Bundling Remotion project...`);
  const bundleLocation = await bundle({
    entryPoint: inputAbs,
    webpackOverride: (config) => config,
  });

  console.log(`🎬 Fetching compositions...`);
  const compositions = await getCompositions(bundleLocation);
  const composition = compositions[0]; // Use first composition 'Edit'

  if (!composition) {
    console.error("No composition found in bundled output");
    process.exit(1);
  }

  // Override composition props
  composition.width = resolution[0];
  composition.height = resolution[1];
  composition.fps = fps;

  const isLowQuality = quality === "low";
  const crf = isLowQuality ? 28 : 18;
  const preset = isLowQuality ? "ultrafast" : "medium";

  console.log(`🎥 Rendering media...`);
  console.log(`   Resolution: ${resolution[0]}x${resolution[1]}`);
  console.log(`   FPS: ${fps}`);
  console.log(`   Quality: ${quality}`);
  console.log(`   Output: ${outputAbs}`);

  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: outputAbs,
    inputProps: {},
    crf,
    preset,
    imageFormat: "jpeg",
    jpegQuality: isLowQuality ? 60 : 100,
    timeoutInMilliseconds: 600000,
  });

  console.log(`✅ Render complete: ${outputAbs}`);
}

main().catch((err) => {
  console.error("Render failed:", err);
  process.exit(1);
});

/**
 * Composant FullBroll — Visuel plein écran avec effet Ken Burns optionnel
 */

import React, { useRef } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

interface Segment {
  segment_id: string;
  template: {
    layout: Record<string, any>;
    type: string;
    default_duration: number;
  };
  broll_clips?: string[];
}

export const FullBroll: React.FC<{ segment: Segment }> = ({ segment }) => {
  const frame = useCurrentFrame();
  const layout = segment.template.layout;
  const brollCfg = layout.broll || {};
  const kenBurns = brollCfg.ken_burns;
  const duration = segment.template.default_duration;

  const style: React.CSSProperties = {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    objectFit: brollCfg.fit || "cover",
  };

  // Effet Ken Burns (zoom progressif)
  if (kenBurns) {
    const progress = duration > 0 ? frame / (duration * 30) : 0; // 30fps
    const scale = interpolate(
      progress,
      [0, 1],
      [kenBurns.start_scale || 1.0, kenBurns.end_scale || 1.15],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    const translateX = interpolate(
      progress,
      [0, 1],
      [(kenBurns.start_x || 0) * 100, (kenBurns.end_x || 0.05) * 100],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    const translateY = interpolate(
      progress,
      [0, 1],
      [(kenBurns.start_y || 0) * 100, (kenBurns.end_y || 0.05) * 100],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    style.transform = `scale(${scale}) translate(${translateX}%, ${translateY}%)`;
  }

  const brollSrc = segment.broll_clips?.[0];

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {brollSrc ? (
        <video src={brollSrc} style={style} />
      ) : (
        <div
          style={{
            ...style,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#666",
            fontSize: 24,
            backgroundColor: "#1a1a2e",
          }}
        >
          B-roll non disponible
        </div>
      )}
      {renderOverlay(layout.overlay)}
    </AbsoluteFill>
  );
};

function renderOverlay(overlay: any): React.ReactNode {
  if (!overlay) return null;

  if (overlay.type === "gradient") {
    return (
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          width: "100%",
          height: `${(overlay.height || 0.3) * 100}%`,
          background: `linear-gradient(to top, ${overlay.end_color || "rgba(0,0,0,0.4)"}, ${overlay.start_color || "rgba(0,0,0,0)"})`,
        }}
      />
    );
  }

  if (overlay.type === "vignette") {
    const intensity = overlay.intensity || 0.3;
    return (
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at center, transparent 60%, rgba(0,0,0,${intensity}) 100%)`,
        }}
      />
    );
  }

  return null;
}

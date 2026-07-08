/**
 * Composant Facecam — Vue speaker plein écran
 */

import React from "react";
import { AbsoluteFill, Img } from "remotion";

interface Segment {
  segment_id: string;
  template: {
    layout: Record<string, any>;
    type: string;
  };
  source_clip?: string;
  broll_clips?: string[];
}

export const Facecam: React.FC<{ segment: Segment }> = ({ segment }) => {
  const layout = segment.template.layout;
  const speakerLayout = layout.speaker || {};

  const style: React.CSSProperties = {
    position: "absolute",
    left: `${(speakerLayout.x || 0) * 100}%`,
    top: `${(speakerLayout.y || 0) * 100}%`,
    width: `${(speakerLayout.w || 1) * 100}%`,
    height: `${(speakerLayout.h || 1) * 100}%`,
    objectFit: speakerLayout.fit || "cover",
    borderRadius: speakerLayout.border_radius
      ? `${speakerLayout.border_radius}px`
      : undefined,
    boxShadow: speakerLayout.box_shadow || undefined,
  };

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <video src={segment.source_clip} style={style} />
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

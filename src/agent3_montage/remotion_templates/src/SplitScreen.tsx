/**
 * Composant SplitScreen — Speaker + B-roll côte à côte
 */

import React from "react";
import { AbsoluteFill } from "remotion";

interface Segment {
  segment_id: string;
  template: { layout: Record<string, any>; type: string };
  source_clip?: string;
  broll_clips?: string[];
}

export const SplitScreen: React.FC<{ segment: Segment }> = ({ segment }) => {
  const layout = segment.template.layout;

  const getStyle = (el: Record<string, any>): React.CSSProperties => ({
    position: "absolute",
    left: `${(el.x || 0) * 100}%`,
    top: `${(el.y || 0) * 100}%`,
    width: `${(el.w || 0.5) * 100}%`,
    height: `${(el.h || 1) * 100}%`,
    objectFit: el.fit || "cover",
    borderRight: el.border_right || undefined,
    borderRadius: el.border_radius ? `${el.border_radius}px` : undefined,
    boxShadow: el.box_shadow || undefined,
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Speaker */}
      <video
        src={segment.source_clip}
        style={getStyle(layout.speaker || {})}
      />
      {/* B-roll principal */}
      {segment.broll_clips?.[0] && (
        <video
          src={segment.broll_clips[0]}
          style={getStyle(layout.broll || layout.broll_1 || {})}
        />
      )}
      {/* B-roll secondaire (triple split) */}
      {segment.broll_clips?.[1] && layout.broll_2 && (
        <video
          src={segment.broll_clips[1]}
          style={getStyle(layout.broll_2)}
        />
      )}
    </AbsoluteFill>
  );
};

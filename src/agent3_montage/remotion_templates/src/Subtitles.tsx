/**
 * Composant Subtitles — Sous-titres style karaoke avec surlignage mot par mot
 */

import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

interface WordData {
  text: string;
  start: number; // en secondes
  end: number;
  index: number;
}

interface SubtitlesConfig {
  font?: string;
  font_size?: number;
  color?: string;
  highlight_color?: string;
  position?: string;
  stroke_color?: string;
  stroke_width?: number;
  words: WordData[];
}

interface SubtitlesProps {
  words: WordData[];
  config?: SubtitlesConfig;
  fps?: number;
}

export const Subtitles: React.FC<SubtitlesProps> = ({
  words,
  config,
  fps = 30,
}) => {
  const frame = useCurrentFrame();
  const currentTime = frame / fps;

  const defaultConfig: SubtitlesConfig = {
    font: "Inter",
    font_size: 32,
    color: "#FFFFFF",
    highlight_color: "#FFD700",
    position: "bottom",
    stroke_color: "#000000",
    stroke_width: 1,
    words,
  };

  const cfg = { ...defaultConfig, ...config };

  // Trouver les mots actifs et à venir
  const activeWords = words.filter(
    (w) => currentTime >= w.start && currentTime <= w.end
  );

  const upcomingIndex = words.findIndex((w) => currentTime < w.start);
  const upcomingWord = upcomingIndex >= 0 ? words[upcomingIndex] : null;

  // Grouper les mots consécutifs de la même phrase
  const groupActive = activeWords.length > 0 ? activeWords : [];
  const groupUpcoming =
    upcomingWord && groupActive.length === 0 ? [upcomingWord] : [];

  const displayText = [...groupActive, ...groupUpcoming]
    .map((w) => w.text)
    .join(" ");

  if (!displayText) return null;

  const positionStyles: React.CSSProperties = {
    position: "absolute",
    left: "50%",
    transform: "translateX(-50%)",
    textAlign: "center",
    fontFamily: cfg.font,
    fontSize: cfg.font_size,
    color: cfg.color,
    textShadow:
      cfg.stroke_width > 0
        ? `${cfg.stroke_color} 0px 0px ${cfg.stroke_width * 2}px`
        : undefined,
    width: "80%",
    zIndex: 100,
  };

  if (cfg.position === "bottom") {
    positionStyles.bottom = 60;
  } else if (cfg.position === "top") {
    positionStyles.top = 60;
  } else {
    positionStyles.top = "50%";
    positionStyles.transform = "translateX(-50%) translateY(-50%)";
  }

  // Mode karaoke : surligner chaque mot
  if (config?.highlight_color && activeWords.length > 0) {
    return (
      <AbsoluteFill>
        <div style={positionStyles}>
          {words.slice(0, upcomingIndex !== -1 ? upcomingIndex : words.length).map((w, i) => {
            const isActive = currentTime >= w.start && currentTime <= w.end;
            const isPast = currentTime > w.end;
            return (
              <span
                key={`kw-${i}`}
                style={{
                  color: isActive
                    ? cfg.highlight_color
                    : isPast
                      ? cfg.color
                      : "rgba(255,255,255,0.3)",
                  transition: "color 0.05s ease",
                  marginRight: 4,
                }}
              >
                {w.text}
              </span>
            );
          })}
        </div>
      </AbsoluteFill>
    );
  }

  // Mode block : texte complet
  return (
    <AbsoluteFill>
      <div style={positionStyles}>{displayText}</div>
    </AbsoluteFill>
  );
};

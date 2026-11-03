import type { CSSProperties, ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Size of one art pixel in CSS pixels. A whole number keeps the edges crisp. */
const PIXEL = 3;

/** Color for each sprite character. "." is transparent. */
const PALETTE: Record<string, string> = {
  Y: "oklch(0.86 0.17 95)", // goal post yellow
  y: "oklch(0.7 0.15 85)", // goal post shadow
  R: "oklch(0.65 0.22 25)", // wind flag red
  G: "oklch(0.45 0.02 250)", // floodlight steel
  W: "oklch(0.99 0.03 95)", // floodlight bulb
};

/** Goal post: two uprights with wind flags, a crossbar, and the center stem. */
const GOAL_POST = [
  ".YRR.......YRR",
  ".YR........YR.",
  ...Array(7).fill(".Y.........Y.."),
  ".YYYYYYYYYYY..",
  ".yyyyyyyyyyy..",
  ...Array(7).fill("......Yy......"),
];

/** Floodlight: a bank of bulbs on a pole. */
const FLOODLIGHT = [
  "GGGGGGGGG",
  "GWGWGWGWG",
  "GGGGGGGGG",
  "GWGWGWGWG",
  "GGGGGGGGG",
  ...Array(15).fill("....G...."),
];

/** Turf strip under the header: grass tips, white yard lines, and alternating mow stripes. */
const TURF: CSSProperties = {
  height: 4 * PIXEL,
  backgroundImage: [
    `repeating-linear-gradient(90deg, oklch(0.68 0.17 145) 0 ${PIXEL}px, transparent ${PIXEL}px ${2 * PIXEL}px)`,
    `repeating-linear-gradient(90deg, transparent 0 ${15 * PIXEL}px, oklch(0.95 0 0 / 0.8) ${15 * PIXEL}px ${16 * PIXEL}px)`,
    `repeating-linear-gradient(90deg, oklch(0.55 0.15 145) 0 ${16 * PIXEL}px, oklch(0.49 0.14 145) ${16 * PIXEL}px ${32 * PIXEL}px)`,
  ].join(", "),
  backgroundSize: `100% ${PIXEL}px, 100% 100%, 100% 100%`,
  backgroundRepeat: "no-repeat",
};

/** Soft light cone angled down and inward from a floodlight. */
const BEAM: CSSProperties = {
  top: 2 * PIXEL,
  left: 9 * PIXEL,
  width: "14rem",
  height: "7rem",
  background: "linear-gradient(to bottom right, oklch(1 0.03 95 / 0.16), transparent 70%)",
  clipPath: "polygon(0 0, 12px 0, 100% 100%, 30% 100%)",
};

interface SpriteProps {
  /** One string per pixel row, using PALETTE characters. */
  rows: string[];
  className?: string;
  style?: CSSProperties;
}

/** Draws a pixel-art sprite as one square per pixel. */
function Sprite({ rows, className, style }: SpriteProps) {
  const width = rows[0]?.length ?? 0;
  return (
    <svg
      aria-hidden
      viewBox={`0 0 ${width} ${rows.length}`}
      width={width * PIXEL}
      height={rows.length * PIXEL}
      shapeRendering="crispEdges"
      className={className}
      style={style}
    >
      {rows.flatMap((row, y) =>
        [...row].map((c, x) =>
          c === "." ? null : (
            <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill={PALETTE[c]} />
          ),
        ),
      )}
    </svg>
  );
}

/** A floodlight in a top corner, mirrored on the right so both beams point inward. */
function Floodlight({ side }: { side: "left" | "right" }) {
  return (
    // Desktop only: on narrower screens the header text reaches the corners.
    <div
      aria-hidden
      className={cn(
        "absolute top-3 hidden lg:block",
        side === "left" ? "left-6" : "right-6 -scale-x-100",
      )}
    >
      <div className="absolute" style={BEAM} />
      <Sprite
        rows={FLOODLIGHT}
        style={{ filter: "drop-shadow(0 0 4px oklch(0.99 0.03 95 / 0.7))" }}
      />
    </div>
  );
}

/** Page header drawn as a night stadium: floodlights, goal posts at each end, turf below. */
export function StadiumHeader({ children }: { children: ReactNode }) {
  return (
    <header className="relative overflow-hidden bg-card">
      <Floodlight side="left" />
      <Floodlight side="right" />
      {/* Extra bottom space below lg gives the goal posts room beneath the text; the lg minimum
          height keeps the floodlight poles above the turf on short headers. */}
      <div className="relative px-4 pt-4 pb-16 lg:min-h-24 lg:pb-6">{children}</div>
      {/* On desktop the posts move inward so the floodlight beams land on them. */}
      <Sprite
        rows={GOAL_POST}
        className="absolute left-4 lg:left-28"
        style={{ bottom: 4 * PIXEL }}
      />
      <Sprite
        rows={GOAL_POST}
        className="absolute right-4 lg:right-28"
        style={{ bottom: 4 * PIXEL }}
      />
      <div aria-hidden style={TURF} />
    </header>
  );
}

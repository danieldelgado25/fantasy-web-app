import { Ambulance, Ban, CircleHelp, CircleX, TriangleAlert, type LucideIcon } from "lucide-react";

import type { InjuryStatus } from "@/lib/api";

/** How one injury status is drawn. */
interface InjuryStyle {
  /** The icon shown. */
  icon: LucideIcon;
  /** Short text shown beside the icon, so the status doesn't rely on the icon alone. */
  short: string;
  /** Full name, read by screen readers and shown on hover. */
  label: string;
  /** Text color: red for won't play, orange and amber for at risk, yellow for likely plays. */
  color: string;
}

/**
 * Every status, worst to best. Healthy players have no status and get no icon.
 * IR is defined for completeness: IR players are currently left off the site.
 */
const INJURY_STYLES: Record<InjuryStatus, InjuryStyle> = {
  IR: { icon: Ambulance, short: "IR", label: "Injured reserve", color: "text-red-500" },
  Out: { icon: CircleX, short: "Out", label: "Ruled out", color: "text-red-500" },
  Doubtful: { icon: TriangleAlert, short: "D", label: "Doubtful", color: "text-orange-500" },
  DNP: { icon: Ban, short: "DNP", label: "Did not practice", color: "text-amber-500" },
  Questionable: { icon: CircleHelp, short: "Q", label: "Questionable", color: "text-yellow-400" },
};

interface InjuryIconProps {
  /** The player's worst status for their next game, or null/undefined when healthy. */
  status?: InjuryStatus | null | undefined;
  /** Report details, e.g. "Questionable · Did not practice · Hamstring", shown on hover. */
  note?: string | null | undefined;
}

/** A small icon and label for a player's injury status. Renders nothing for healthy players. */
export function InjuryIcon({ status, note }: InjuryIconProps) {
  if (!status) return null;
  const { icon: Icon, short, label, color } = INJURY_STYLES[status];
  return (
    <span
      className={`inline-flex items-center gap-0.5 align-middle text-xs font-semibold ${color}`}
      title={note ?? label}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      <span aria-hidden="true">{short}</span>
      {/* Screen readers get the full status and details instead of the abbreviation. */}
      <span className="sr-only">{note ?? label}</span>
    </span>
  );
}

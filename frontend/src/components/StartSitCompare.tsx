import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { InjuryIcon } from "@/components/InjuryIcon";
import type { InjuryStatus, PlayerProjection } from "@/lib/api";

/**
 * Projected point gaps smaller than this are called a toss-up. The model's average
 * miss is about 6-7 points per player, so a gap of a point or two isn't a real edge.
 */
const TOSS_UP_MARGIN = 2;

/** Number of defenses the opponent rank is out of. */
const DEFENSE_COUNT = 32;

interface StartSitCompareProps {
  /** First player picked. */
  a: PlayerProjection;
  /** Second player picked. */
  b: PlayerProjection;
}

/** "Sun 1:00 PM ET" from nflverse's Eastern date and HH:MM time, or null if either is missing. */
function kickoffLabel(p: PlayerProjection): string | null {
  if (!p.gameday || !p.gametime) return null;
  // Noon avoids the weekday shifting across time zones; only the weekday is read from it.
  const weekday = new Date(`${p.gameday}T12:00:00`).toLocaleDateString("en-US", {
    weekday: "short",
  });
  const [hour = 0, minute = 0] = p.gametime.split(":").map(Number);
  return `${weekday} ${hour % 12 || 12}:${String(minute).padStart(2, "0")} ${hour < 12 ? "AM" : "PM"} ET`;
}

/** "vs DAL" at home, "@ DAL" away, or just "DAL" when the file doesn't say which. */
function opponentLabel(p: PlayerProjection): string {
  if (p.is_home == null) return p.opponent_team;
  return `${p.is_home === 0 ? "@" : "vs"} ${p.opponent_team}`;
}

/** Betting-line value, or "Not posted" while the model is using its neutral stand-in. */
function lineValue(p: PlayerProjection, value: number | null | undefined): string {
  if (p.line_posted === false) return "Not posted";
  return value != null ? value.toFixed(1) : "—";
}

/** "31.2 / game (5th of 32)", or a dash when the file has no defense data. */
function defenseValue(p: PlayerProjection): string {
  if (p.opp_wr_points_allowed == null || p.opp_wr_allowed_rank == null) return "—";
  return `${p.opp_wr_points_allowed.toFixed(1)} / game (${p.opp_wr_allowed_rank} of ${DEFENSE_COUNT})`;
}

/** Statuses that mean the player won't play this game, so projected points don't matter. */
const WONT_PLAY: InjuryStatus[] = ["IR", "Out"];

/** True when the injury report says the player won't play. */
function wontPlay(p: PlayerProjection): boolean {
  return p.injury_status != null && WONT_PLAY.includes(p.injury_status);
}

/**
 * The verdict and the one-line reason under it. A player who won't play loses
 * regardless of points; otherwise the higher projection wins unless the gap is a toss-up.
 */
function decide(a: PlayerProjection, b: PlayerProjection): { verdict: string; reason: string } {
  if (wontPlay(a) && wontPlay(b)) {
    return { verdict: "Neither will play", reason: "Both are ruled out or on injured reserve." };
  }
  if (wontPlay(a) || wontPlay(b)) {
    const [out, other] = wontPlay(a) ? [a, b] : [b, a];
    return { verdict: `Start ${other.player_name}`, reason: `${out.player_name} won't play.` };
  }
  const gap = a.pred_ppr_points - b.pred_ppr_points;
  if (Math.abs(gap) < TOSS_UP_MARGIN) {
    return {
      verdict: "Toss-up",
      reason: `Projections are within ${TOSS_UP_MARGIN} points, smaller than the model's typical miss.`,
    };
  }
  const leader = gap >= 0 ? a : b;
  return {
    verdict: `Start ${leader.player_name}`,
    reason: `Projected ${Math.abs(gap).toFixed(1)} more PPR points.`,
  };
}

/** Side-by-side projection and matchup for two WRs, with a start/sit verdict. */
export function StartSitCompare({ a, b }: StartSitCompareProps) {
  const { verdict, reason } = decide(a, b);

  // One row per comparison line: label, then each player's value.
  const rows: { label: string; value: (p: PlayerProjection) => string }[] = [
    { label: "Projected PPR", value: (p) => p.pred_ppr_points.toFixed(1) },
    { label: "Matchup", value: opponentLabel },
    { label: "Kickoff", value: (p) => kickoffLabel(p) ?? "—" },
    { label: "Team implied points", value: (p) => lineValue(p, p.team_implied_total) },
    { label: "Game total", value: (p) => lineValue(p, p.game_total) },
    {
      label: "Roof",
      value: (p) => (p.is_dome == null ? "—" : p.is_dome === 1 ? "Dome" : "Outdoors"),
    },
    { label: "Opp. WR points allowed", value: defenseValue },
    // Spelled out, since hover details on the icon don't exist on phones.
    { label: "Injury report", value: (p) => p.injury_note ?? "Not listed" },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>{verdict}</CardTitle>
        <p className="text-muted-foreground text-sm">{reason}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead />
              {[a, b].map((p) => (
                <TableHead key={p.player_id}>
                  {p.player_name} <InjuryIcon status={p.injury_status} note={p.injury_note} />
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.label}>
                <TableCell className="text-muted-foreground">{row.label}</TableCell>
                <TableCell>{row.value(a)}</TableCell>
                <TableCell>{row.value(b)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <p className="text-muted-foreground text-xs">
          Opponent WR points allowed is this season's per-game average; rank 1 allows the most. It
          is shown for context only and is not fed into the model: a handful of games against uneven
          receiver groups makes it too inconsistent to rely on.
        </p>
      </CardContent>
    </Card>
  );
}

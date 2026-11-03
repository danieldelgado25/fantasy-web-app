import { AlertCircle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { PlayerProjection } from "@/lib/api";

interface ProjectionPanelProps {
  projection: PlayerProjection | null;
  isLoading: boolean;
  error: Error | null;
}

/** Whole years between a YYYY-MM-DD birth date and today. */
function ageFrom(birthDate: string): number {
  const born = new Date(`${birthDate}T00:00:00`);
  const now = new Date();
  const hadBirthday =
    now.getMonth() > born.getMonth() ||
    (now.getMonth() === born.getMonth() && now.getDate() >= born.getDate());
  return now.getFullYear() - born.getFullYear() - (hadBirthday ? 0 : 1);
}

/** Bio facts that exist for this player, as label/value pairs. */
function bioFacts(p: PlayerProjection): { label: string; value: string }[] {
  const facts = [
    { label: "Age", value: p.birth_date ? String(ageFrom(p.birth_date)) : null },
    {
      label: "Height",
      value: p.height_inches
        ? `${Math.floor(p.height_inches / 12)}'${p.height_inches % 12}"`
        : null,
    },
    { label: "Weight", value: p.weight_lbs ? `${p.weight_lbs} lb` : null },
    { label: "College", value: p.college ?? null },
    { label: "Experience", value: p.years_exp != null ? `${p.years_exp} yrs` : null },
  ];
  return facts.filter((f): f is { label: string; value: string } => f.value !== null);
}

export function ProjectionPanel({ projection, isLoading, error }: ProjectionPanelProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Projection</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-8 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-1/2" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Something went wrong</AlertTitle>
        <AlertDescription>
          {error.message || "Could not load the projection. Please try again."}
        </AlertDescription>
      </Alert>
    );
  }

  // Nothing selected yet: the top players table is the page's starting point.
  if (!projection) {
    return null;
  }

  // Projected box-score stats shown under the points total.
  const stats = [
    { label: "Targets", value: projection.pred_targets },
    { label: "Catches", value: projection.pred_rec },
    { label: "Rec yards", value: projection.pred_rec_yds },
    { label: "Rec TDs", value: projection.pred_rec_td },
    { label: "Carries", value: projection.pred_carries },
    { label: "Rush yards", value: projection.pred_rushing_yards },
  ];

  // Bio line and season-to-date totals; both hide when the data file lacks them.
  const bio = bioFacts(projection);
  const seasonStats = [
    { label: "Targets", value: projection.season_targets },
    { label: "Catches", value: projection.season_rec },
    { label: "Rec yards", value: projection.season_rec_yds },
    { label: "Rec TDs", value: projection.season_rec_td },
  ];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            {projection.headshot_url && (
              <img
                src={projection.headshot_url}
                alt=""
                className="bg-muted h-16 w-16 shrink-0 rounded-full object-cover"
              />
            )}
            <div>
              <CardTitle>{projection.player_name}</CardTitle>
              <p className="text-muted-foreground mt-1 flex items-center gap-1.5 text-sm">
                {projection.team_logo_url && (
                  <img src={projection.team_logo_url} alt="" className="h-5 w-5" />
                )}
                {projection.team}
                {projection.jersey_number && ` · #${projection.jersey_number}`} · Week{" "}
                {projection.week}, {projection.season}
              </p>
            </div>
          </div>
          <Badge variant="secondary" className="shrink-0 whitespace-nowrap">
            vs {projection.opponent_team}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div>
          <p className="text-muted-foreground text-sm">Projected PPR Points</p>
          <p className="text-5xl font-bold tracking-tight text-primary">
            {projection.pred_ppr_points.toFixed(2)}
          </p>
        </div>
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {stats.map((stat) => (
            <div key={stat.label}>
              <dt className="text-muted-foreground text-xs">{stat.label}</dt>
              <dd className="text-lg font-semibold">{stat.value.toFixed(1)}</dd>
            </div>
          ))}
        </dl>
        {bio.length > 0 && (
          <dl className="text-muted-foreground flex flex-wrap gap-x-4 gap-y-1 border-t pt-4 text-xs">
            {bio.map((fact) => (
              <div key={fact.label} className="flex gap-1">
                <dt>{fact.label}:</dt>
                <dd className="text-foreground">{fact.value}</dd>
              </div>
            ))}
          </dl>
        )}
        {/* Actual results so far, so the projection can be read against them. */}
        {projection.season_games != null && (
          <div className="border-t pt-4">
            <p className="text-muted-foreground text-sm">
              {projection.season} season so far ({projection.season_games} games)
            </p>
            <dl className="mt-2 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {seasonStats.map((stat) => (
                <div key={stat.label}>
                  <dt className="text-muted-foreground text-xs">{stat.label}</dt>
                  <dd className="text-lg font-semibold">{stat.value ?? "n/a"}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

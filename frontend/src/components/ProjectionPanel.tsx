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

export function ProjectionPanel({
  projection,
  isLoading,
  error,
}: ProjectionPanelProps) {
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

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle>{projection.player_name}</CardTitle>
            <p className="text-muted-foreground text-sm mt-1">
              {projection.team} · Week {projection.week}, {projection.season}
            </p>
          </div>
          <Badge variant="secondary">vs {projection.opponent_team}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div>
          <p className="text-muted-foreground text-sm">Projected PPR Points</p>
          <p className="text-5xl font-bold tracking-tight">
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
      </CardContent>
    </Card>
  );
}

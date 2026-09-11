import { Loader2, AlertCircle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { Projection } from "@/lib/api";

interface ProjectionPanelProps {
  projection: Projection | null;
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

  if (!projection) {
    return (
      <Alert>
        <Loader2 className="h-4 w-4 animate-spin" />
        <AlertTitle>Projection not available yet</AlertTitle>
        <AlertDescription>
          We don&apos;t have a projection for this player yet. Check back later.
        </AlertDescription>
      </Alert>
    );
  }

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
            {projection.projected_ppr_points.toFixed(2)}
          </p>
        </div>
        <p className="text-muted-foreground text-xs">
          Model: {projection.model_version}
        </p>
      </CardContent>
    </Card>
  );
}

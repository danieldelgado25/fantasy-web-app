import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { PlayerProjection } from "@/lib/api";

interface TopPlayersTableProps {
  /** Players to list, already limited and in rank order. */
  players: PlayerProjection[];
  /** The player whose row is highlighted, if any. */
  selectedPlayerId: string | null;
  /** Called when a row's player is chosen. */
  onSelect: (player: PlayerProjection) => void;
}

/** The top-ranked receivers and their projected points. Choosing one shows full details. */
export function TopPlayersTable({ players, selectedPlayerId, onSelect }: TopPlayersTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-12">#</TableHead>
          <TableHead>Player</TableHead>
          <TableHead>Next game</TableHead>
          <TableHead className="text-right">Proj. PPR</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {players.map((player) => (
          <TableRow
            key={player.player_id}
            data-state={player.player_id === selectedPlayerId ? "selected" : undefined}
          >
            <TableCell>{player.rank}</TableCell>
            <TableCell>
              {/* A real button, so rows work by keyboard and screen reader. */}
              <button
                type="button"
                className="text-left font-medium hover:underline"
                onClick={() => onSelect(player)}
              >
                {player.player_name}
              </button>
              <span className="text-muted-foreground ml-2 text-xs">{player.team}</span>
            </TableCell>
            <TableCell className="text-muted-foreground">
              Wk {player.week} vs {player.opponent_team}
            </TableCell>
            <TableCell className="text-right font-semibold">
              {player.pred_ppr_points.toFixed(1)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

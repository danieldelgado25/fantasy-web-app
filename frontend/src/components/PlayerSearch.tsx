import { useState, useMemo } from "react";
import { ChevronsUpDown, Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { Player } from "@/lib/api";

interface PlayerSearchProps {
  players: Player[];
  selectedPlayer: Player | null;
  onSelect: (player: Player) => void;
  disabled?: boolean;
}

export function PlayerSearch({
  players,
  selectedPlayer,
  onSelect,
  disabled,
}: PlayerSearchProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const filteredPlayers = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return players;
    return players.filter(
      (p) =>
        p.player_name.toLowerCase().includes(query) ||
        p.team.toLowerCase().includes(query)
    );
  }, [players, search]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className="w-full justify-between"
        >
          {selectedPlayer
            ? `${selectedPlayer.player_name} (${selectedPlayer.team})`
            : "Search for a wide receiver..."}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Type a player name or team..."
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            <CommandEmpty>No player found.</CommandEmpty>
            <CommandGroup>
              {filteredPlayers.map((player) => (
                <CommandItem
                  key={player.player_id}
                  value={player.player_id}
                  onSelect={() => {
                    onSelect(player);
                    setOpen(false);
                    setSearch("");
                  }}
                >
                  <Check
                    className={`mr-2 h-4 w-4 ${
                      selectedPlayer?.player_id === player.player_id
                        ? "opacity-100"
                        : "opacity-0"
                    }`}
                  />
                  <span className="flex-1">{player.player_name}</span>
                  <span className="text-muted-foreground text-sm">
                    {player.team}
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

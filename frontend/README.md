# Frontend

The React site for the NFL wide receiver projections project. See the [main README](../README.md) for what the project does and how it works.

It has no backend server: it reads `public/data/projections.json` and `public/data/accuracy.json`, which the daily GitHub Action updates. Entries in the public project log live in `src/lib/projectLog.ts`.

## Run it locally

```bash
bun install
bun run dev
```

## Checks

```bash
bun run lint
bunx tsc --noEmit
bun run build
```

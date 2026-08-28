# Frontend

React 19 + TypeScript + Vite + Tailwind CSS + React Router. See the
[repo-level README](../README.md) for what this app does; this file is
frontend-specific commands only.

## Develop

```bash
npm ci
npm run dev          # http://localhost:5173, proxies /api to localhost:8000 by default
```

## Test

```bash
npm test              # Vitest + Testing Library (jsdom)
npm run test:e2e       # Playwright, needs the full stack running -- see docs/testing.md
```

## Lint / format / build

```bash
npm run lint
npm run format          # check
npm run format:write    # fix
npm run build            # tsc -b && vite build
```

## Structure

```
src/
  lib/api.ts           # dependency-free typed fetch client (token storage, error normalization)
  context/AuthContext.tsx
  components/          # Layout, ProtectedRoute, StatusBadge, CitationList
  pages/                # one per route
e2e/smoke.spec.ts       # Playwright end-to-end smoke test
```

No state management library, no UI component library, no CSS-in-JS — Tailwind
utility classes plus a handful of small components was the right amount of
tooling for this app's actual size. See the repo-level `AGENTS.md` before
adding a dependency to change that.

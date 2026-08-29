# kobo-sky — project context

A Flask + PyEphem night sky map for Pune, rendered as one SVG page and read on a
wall-mounted Kobo Touch (hence the 180° CSS rotation and the no-flexbox HTML —
the Kobo's browser is ancient WebKit).

**Delivery is local wifi only — there is no cloud deploy** (OD, 2026-08-30).
The Kobo hits the Mac's LAN address directly. Of OD's apps only `learning` is on
Render. The `Procfile` here is a kept-but-unwired artefact; don't read it as
evidence of a live host, and don't infer a deploy step that doesn't exist.

The GitHub remote **is** real and **public**: `odas/sky-kobo-dashboard`. Anything
outside `docs/` is world-readable — that is the reason `docs/` exists.

## Status: alive on purpose, not in daily use (OD, 2026-08-30)

OD does not use this app day to day. It stays because it was one of her earliest
Claude projects, she learned a great deal building it, and it demos well to an
interviewer precisely because it is unusual. **Expect more sessions here, aimed at
harvesting those learnings** — so treat the history as material, not clutter.

Corollary: don't propose retiring, archiving or "consolidating" this repo.

## Don't rebuild the star chart here

A much richer sky renderer (Skyfield, ~236 stars, constellation lines) was built
in June 2026 and lives in **task-dash** at `/sky`, which OD does use daily. This
repo's simpler PyEphem render stays as it is. If a session is tempted to port
constellation lines back into `app.py`, that is a new feature request — raise it,
don't assume it.

## Where things live

- `app.py` — the whole app. No templates dir; the HTML is a string at the bottom.
- `get_mp3.py` — unrelated lodger: an Internet Archive audiobook fetcher feeding
  Noëtone. It works; leave it unless OD asks. `Asimov_Downloads/` is its output,
  gitignored (193MB, re-fetchable).
- `docs/` — **local-only, and enforced structurally**: excluded in `.gitignore`
  and kept in a nested git repo at `docs/.git` that has no remote, so there is no
  push path to GitHub at all. Holds `STATUS.md`, `fixes.md` (backlog + routed-in
  notes) and `kobo-sky-narrative/` (exported chat transcripts — the harvest source).
- Commit `docs/` changes inside `docs/`, separately from the main repo.

## Ports

`app.py` reads `$PORT`, default 5002. 5002 is this app's fleet slot in
`~/dev/cockpit/apps.json`; pm2 runs it as `kobo-sky-5002`. Don't hardcode a port.

⚠ Known stale, outside this repo: that `apps.json` entry's `desc` describes a
Kobo *reading tracker* — a different project. Flag it to OD for the cockpit
session; don't edit another repo from here.

## Retiring a file (OD's call, 2026-08-11)

Superseded files go to `docs/superseded/` with a top banner saying what replaced
them and why, and their live pointers get repointed the same session. Spelling is
`superseded`. The reasoning, which generalises: when two locations both work,
**visibility decides** — `~/dev` is a portfolio surface a stranger may read.
Ordinary junk still just gets deleted.

## Verify a change actually works

```bash
.venv/bin/python -c "import app; app.refresh(); d=app._cache['data']; print(d['weather'], d['sky'].count('<circle'))"
```
Exercises ephem, both weather APIs and the SVG build without binding a port.
Note the sky is empty by day — that path renders a "returns at HH:MM" card instead.

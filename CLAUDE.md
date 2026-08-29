# CLAUDE.md — kobo-sky

A Flask + PyEphem night sky map for Pune, rendered as one SVG page and read on a
wall-mounted Kobo Touch. `README.md` has the run steps and what it draws; this
file is operating guidance, not a duplicate of it.

## Restarting after a gap — this folder goes months between sessions

It went 8 June → 30 August 2026 with no session. Assume you are the first reader
in months and that nothing in your context is current.

1. **Two git roots.** Run `git status --short` **and** `git -C docs status --short`.
   `docs/` is a nested repo with no remote, so the root status cannot see the records.
2. **Uncommitted changes in `docs/` you didn't make are probably mother-chat's**, or
   another folder's session routing something here. Untracked *is* the signal. Read
   and reconcile it — never sweep it into your own commit. Two such notes were closed
   on 2026-08-30; expect more.
3. **Then `docs/STATUS.md`** (where it is now, one paragraph), **then `docs/fixes.md`**
   (dated worklog, newest on top — what happened, what was decided, what's deferred).
   **Read those before reconstructing state from the code.** A session on 2026-08-30
   that reconstructed from the code first spent its first ten minutes rediscovering
   things `fixes.md` already said.
4. **Check claims against reality before repeating them.** The README asserted a
   Render deploy that never existed, and a session reasoned carefully about that
   deploy's behaviour rather than checking whether it was there. Verifying is cheap
   here: `pm2 list`, `git ls-remote origin`, the command at the bottom of this file.
5. Offer the single next-smallest step. Flag what you're guessing.

## Status: alive on purpose, not in daily use (OD, 2026-08-30)

OD does not use this app day to day. It stays because it was one of her earliest
Claude projects, she learned a great deal building it, and it demos well to an
interviewer precisely because it is unusual. **Expect more sessions here aimed at
harvesting those learnings** from `docs/kobo-sky-narrative/` — treat the history as
material, not clutter. Don't propose retiring or consolidating this repo.

## Where it runs, and where it doesn't

**Local wifi only — there is no cloud deploy** (OD, 2026-08-30). The Kobo hits the
Mac's LAN address directly; pm2 keeps it up as `kobo-sky-5002`. Of OD's apps only
`learning` is on Render. The `Procfile` is a kept-but-unwired artefact — don't read
it as evidence of a host.

`app.py` reads `$PORT`, default 5002, which is this app's slot in
`~/dev/cockpit/apps.json`. Don't hardcode a port.

⚠ Known stale, outside this repo, **held for OD's next wrap to mother — do not edit
cockpit from here**: that `apps.json` entry's `desc` describes a Kobo *reading
tracker* (a different project) and claims "(Also on Render.)". Both wrong. Details in
`docs/fixes.md`.

## Don't rebuild the star chart here

A much richer sky renderer (Skyfield, ~236 stars, constellation lines) was built in
June 2026 and lives in **task-dash** at `/sky`, which OD uses daily. This repo's
simpler PyEphem render stays as it is. OD has an on-record complaint about this
render — *"random stars showed no visual info on which constellation it linked to"* —
so porting the lines back is a real idea, but it is a **feature request on a
deliberately-frozen portfolio piece. Raise it; don't assume it.**

## Records — update them in the same session, unprompted

Nobody will remind you. If you changed something:

1. **`docs/fixes.md`** — a dated entry, newest on top: what changed, why, and what
   you decided against. This is the file that answers "what was done / what's left"
   for the next session, so write it for a stranger.
2. **`docs/STATUS.md`** — keep the one-paragraph current state and its date accurate.
   State only; the history belongs in `fixes.md`. Don't narrate the session twice.
3. **`README.md`** — only if run steps, features or limits changed.
4. **`CLAUDE.md`** (this file) — only if an operating rule changed.
5. **Commit** (see below).

If you changed code and none of 1–4 needed an edit, **say so explicitly** rather than
skipping silently.

⚠ Before writing or editing any doc here, read
`~/.claude/skills/writing-rule-docs/SKILL.md` — these files are things a future agent
obeys.

## Git — the remote is real and public

`origin` = `https://github.com/odas/sky-kobo-dashboard`, **public**. Everything
outside `docs/` is world-readable, which is the entire reason `docs/` is local-only.

- **Commit straight to `main`.** Don't branch. On a solo repo a branch just leaves OD
  a merge for a change she already approved. Nothing automated consumes `main` here —
  pm2 serves the working tree, not a pull — so `main` is a notebook, not a contract.
  *(OD stated this rule for `~/dev` personal projects on 2026-08-09 in
  `task_dashboard`; applying it here is this repo's reading of it, not a new decision
  of hers. Branch anyway for work that won't fit one sitting, or throwaway
  experiments.)*
- **Commit `docs/` from inside `docs/`**, as a separate commit from the root repo.
- **Prompt OD to commit and push at the end of a session that changed anything** —
  she has said she forgets, and this repo goes quiet for months, so an uncommitted
  diff here is invisible for a long time. Commit when she says yes; **push is a
  separate ask, because the remote is public.** Before pushing, confirm nothing
  personal escaped `docs/`.
- Don't push without being asked.

## Retiring or rehoming a file

Retire, don't delete: move it to `docs/superseded/` with a top banner naming what
replaced it and why, and repoint its live pointers the same session. Delete ordinary
junk normally — this is for things that may genuinely be useful later. (OD's call,
2026-08-11.) **Why under `docs/`: visibility decides, not version history** — ask what
a stranger reading this public repo sees.

A file that belongs to *another* project is rehomed, not retired: `git mv` it out so
the history follows, banner it with where it came from, and leave the change
**uncommitted in the receiving repo** so that repo's own session owns it. `get_mp3.py`
left for `noetone-batch` this way on 2026-08-30.

## Verify a change actually works

```bash
.venv/bin/python -c "import app; app.refresh(); d=app._cache['data']; print(d['weather'], d['sky'].count('<circle'))"
```
Exercises ephem, both weather APIs and the SVG build without binding a port. By day
the dome is empty by design — that path renders a "returns at HH:MM" card instead.

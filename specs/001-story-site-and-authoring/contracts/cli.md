# Contract: Command Line Interface

Three commands. `argparse`; no CLI framework dependency.

## `sunday build`

```bash
sunday build
```

| Option | Default | Meaning |
|---|---|---|
| `--stories PATH` | `stories/` | Corpus directory |
| `--settings PATH` | `sunday.yml` | Hand-owned settings |
| `--cast PATH` | `cast.yml` | Generated relationship/display-name export |
| `--output PATH` | `site/` | Output directory |
| `--strict` | off | Promote naming warnings to errors |
| `--quiet` | off | Suppress warnings; errors still print |

### Behavior

- Reads only committed files. Runs where `.sunday/` has never existed.
- Emits **exactly four kinds of page**: the homepage feed, `/network/`, `/archive/`, and
  `/stories/<slug>/` — nothing else.
- Removes stale output (FR-018).
- Prints naming warnings to stderr; **exits 0 anyway** unless `--strict`.
- Exits non-zero only on structural errors.
- Byte-identical output for identical input.
- Missing `cast.yml` is not an error — the diagram simply has no stated edges or label overrides.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Site generated (warnings may have printed) |
| 1 | Structural error; nothing published |
| 2 | Bad invocation |

## `sunday portal`

```bash
sunday portal
```

| Option | Default | Meaning |
|---|---|---|
| `--stories PATH` | `stories/` | Corpus directory |
| `--settings PATH` | `sunday.yml` | Settings |
| `--cast PATH` | `cast.yml` | Export target |
| `--store PATH` | `.sunday/store.db` | Local store |
| `--port N` | `5000` | Local port |
| `--no-browser` | off | Don't auto-open a browser |

### Behavior

- Binds `127.0.0.1` only.
- Refuses to start if the target is not a recognizable collection.
- Creates or rebuilds the store at launch when needed, reporting what could not be recovered.
- Scans for divergent files and surfaces conflicts.
- No git operations, ever.
- Its route surface covers stories, cast pages (character, location, and tag), notes, and
  relationships — see [portal-routes.md](./portal-routes.md).

## `sunday store rebuild`

```bash
sunday store rebuild
```

| Option | Default | Meaning |
|---|---|---|
| `--store PATH` | `.sunday/store.db` | Store to rebuild |
| `--yes` | off | Skip confirmation |

### Behavior

- Recovers story rows and hashes from `stories/`, subjects from corpus names, relationships and
  display names from `cast.yml`.
- **Loses notes, dismissed candidates, and profile descriptions** — none of the three is
  exported. States this explicitly and requires confirmation unless `--yes`.
- Never modifies story files, settings, or `cast.yml`.

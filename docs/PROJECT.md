# elymas GitHub profile

This repository powers the public profile at [github.com/elymas](https://github.com/elymas). It presents one responsive profile card in English, with separate light and dark SVGs, live public GitHub statistics, and a link to [floaton.cloud](https://floaton.cloud/).

The visual direction was inspired by [Vikbg/Vikbg](https://github.com/Vikbg/Vikbg). The implementation, copy, portrait, and generated artwork in this repository are specific to `@elymas`.

## Current baseline

As of 2026-08-14 KST, the committed cache contains:

| Metric | Value |
| --- | ---: |
| Public repositories | 18 |
| Stars across owned public repositories | 43 |
| Followers | 11 |
| GitHub years | 9 |
| Top repository | `ai_chatbot_class` (41 stars) |

These values are a fallback snapshot, not permanently authored content. The scheduled workflow refreshes them from GitHub's public REST API.

## How it works

```text
profile.toml + ASCII portrait + SVG template
                    |
                    v
        scripts/generate_profile.py
          |                    |
          v                    v
  GitHub REST API       cache/stats.json
          \                    /
           v                  v
      profile-light.svg + profile-dark.svg
                    |
                    v
            profile README card
```

`README.md` intentionally contains only the linked profile card. Keeping maintenance material in `docs/` preserves the clean profile presentation.

## Repository map

| Path | Purpose |
| --- | --- |
| `README.md` | Minimal GitHub profile surface with light/dark image selection |
| `profile.toml` | Public copy, links, technology lists, and file paths |
| `assets/ascii-portrait.txt` | Hand-tuned portrait used by the generator |
| `assets/avatar-cutout.png` | Transparent source cutout retaining the person and central glass |
| `assets/profile-template.svg` | Shared SVG layout and token placeholders |
| `assets/profile-light.svg` | Generated light card; do not edit by hand |
| `assets/profile-dark.svg` | Generated dark card; do not edit by hand |
| `cache/stats.json` | Last successful public-statistics snapshot and offline fallback |
| `scripts/generate_profile.py` | Dependency-free fetch, render, escaping, and cache logic |
| `tests/test_generate_profile.py` | Generator and data-selection regression tests |
| `.github/workflows/update-profile.yml` | Automated validation, generation, and conditional commit |

## Local workflow

Python 3.10 or newer is supported, and the generator has no third-party runtime dependencies.

Refresh from GitHub and render both themes:

```bash
python3 scripts/generate_profile.py
```

Use the committed cache without network access:

```bash
python3 scripts/generate_profile.py --offline
```

Fail instead of falling back to cached statistics:

```bash
python3 scripts/generate_profile.py --strict
```

Set `PROFILE_TOKEN` or `GITHUB_TOKEN` when authenticated API access is needed. Never commit a token.

Run the verification suite:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q scripts tests
actionlint .github/workflows/update-profile.yml
git diff --check
```

`actionlint` is optional for local editing but should be used whenever the workflow changes.

## Editing guide

- Update identity, headline, contact details, stacks, and project labels in `profile.toml`.
- Update layout, typography, color, or labels in `assets/profile-template.svg`.
- Update the visible portrait in `assets/ascii-portrait.txt`. The current version removes the photo background, retains the glass, and gives the sunglasses stronger contrast.
- Treat `assets/avatar-cutout.png` as the retained visual reference for future portrait revisions.
- Regenerate both SVG outputs after changing configuration, the template, or the ASCII portrait.
- Commit the cache and generated SVGs together when their content changes.

The generator XML-escapes substituted text and writes output only when content has changed. Keep new dynamic fields inside that token path rather than inserting unescaped API data directly into SVG markup.

## Statistics policy

- Repository count comes from the GitHub user record.
- Stars are summed across owned public repositories returned by the API.
- Forked and archived repositories are excluded when selecting the top repository.
- GitHub years are full account anniversaries, not a simple calendar-year difference.
- The refresh date is recorded in `Asia/Seoul`.
- Commit, contribution, and line-of-code totals are intentionally omitted because the public REST endpoints used here do not provide a complete, inexpensive account-wide value.

If GitHub is unavailable, a normal local run may reuse `cache/stats.json`; `--strict` disables that fallback. `--offline` always uses the cache.

## Automation

The `Refresh profile card` workflow runs:

- every day at 12:17 in `Asia/Seoul`;
- manually through `workflow_dispatch`;
- on relevant source changes pushed to `main`.

It runs tests with Python 3.12, regenerates in strict mode with the workflow token, and commits only when the cache or generated SVGs changed. Its permission is limited to `contents: write`, which is required for that conditional commit.

Documentation-only changes do not trigger a card refresh. Use the manual workflow when a fresh API snapshot is desired without changing generator inputs.

## Release checklist

1. Confirm that the public details in `profile.toml` are still intended for publication.
2. Run the tests and offline generation locally.
3. Inspect both generated SVGs when visual inputs changed.
4. Validate the workflow when automation changed.
5. Confirm that generated files and the cache are committed together.
6. Push `main`, check the Actions run when triggered, and verify [github.com/elymas](https://github.com/elymas) in light and dark modes.

The generated card is the public artifact; this document is the operational source of truth for maintaining it.

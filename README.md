# Live Bug Bounty Board

Every live Web3 bug bounty from Immunefi, Cantina, Sherlock and HackenProof in one searchable page.

Curated by [@CallMeCSZ](https://x.com/CallMeCSZ).

## How it works

- `site/` is the static page (`index.html` + `programs.json`), served by Vercel (`vercel.json`) and GitHub Pages.
- `scripts/fetch_bounties.py` pulls each platform's public program data and writes `site/programs.json`.
- `.github/workflows/deploy.yml` runs the script every 6 hours and commits the new data. That push
  makes Vercel redeploy, and the same workflow redeploys GitHub Pages.
  Run it by hand from the **Actions** tab with **Run workflow**.

## Run locally

```bash
python3 scripts/fetch_bounties.py site/programs.json
python3 -m http.server -d site 8000   # open http://localhost:8000
```

## Curator's picks

Edit the `FEATURED` set at the top of `scripts/fetch_bounties.py`. Each entry is `(platform, id)`:
the Immunefi or HackenProof slug, or the Sherlock numeric id.

## Notes

Immunefi publishes an official JSON feed. The Cantina, Sherlock and HackenProof endpoints are the
undocumented ones their own websites use, so they can change without notice; the script skips a
platform that fails and refuses to publish if fewer than 100 programs come back.

Independent project, not affiliated with or endorsed by any platform listed.

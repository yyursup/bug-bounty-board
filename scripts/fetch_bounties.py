#!/usr/bin/env python3
"""Fetch live bug bounty programs from Immunefi, Cantina, Sherlock and HackenProof
and write one normalized programs.json for the Bounty Board page.

Usage:  python3 fetch_bounties.py [output_path]

All four sources are public, unauthenticated, read-only JSON endpoints used by the
platforms' own websites. They are undocumented, so field names can change: the script
skips a platform that fails instead of stopping.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone

UA = "Mozilla/5.0 (BountyBoard data refresh; +https://x.com/CallMeCSZ)"

# Programs the curator picked by hand. Shown first and marked "Featured".
FEATURED = {
    ("Immunefi", "sparklend"), ("Immunefi", "usdt0"), ("Immunefi", "hyperlane"),
    ("Sherlock", "344"), ("Sherlock", "248"), ("Sherlock", "287"),
    ("HackenProof", "noirwallet"),
}
EXTRA_LINKS = {
    ("Sherlock", "287"): ("Also on Mantis", "https://mantis.inverse.finance/bounties/inversefinance/monolith-stablecoin-factory"),
}


def get_json(url):
    # curl honours the environment's proxy settings and CA bundle.
    out = subprocess.run(
        ["curl", "-sS", "-m", "60", "-A", UA, "-H", "Accept: application/json", url],
        check=True, capture_output=True,
    ).stdout
    return json.loads(out)


def iso(value):
    """Return YYYY-MM-DD from an ISO string, a unix timestamp or '07 Jul 2025'."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%d")
    for fmt in ("%d %b %Y",):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return str(value)[:10]


def money(n):
    n = float(n)
    return f"${n:,.0f}"


def immunefi():
    out = []
    for p in get_json("https://immunefi.com/public-api/bounties.json"):
        # Permanent bug bounties only: competitions and attackathons carry an end date.
        if p.get("endDate") or p.get("isPaused") or p.get("inviteOnly"):
            continue
        tiers = []
        for r in p.get("rewards") or []:
            model = r.get("rewardModel")
            if model == "range":
                text = f"{money(r.get('minReward') or 0)} – {money(r.get('maxReward') or 0)}"
                if r.get("rewardCalculationPercentage"):
                    text += f" ({r['rewardCalculationPercentage']}% of funds at risk)"
            elif model == "fixed":
                text = f"{money(r.get('fixedReward') or 0)} flat"
            elif model == "up_to":
                text = f"Up to {money(r.get('maxReward') or 0)}"
            else:
                text = str(r.get("payout") or model or "See program")
            asset = (r.get("assetType") or "").replace("_", " ").replace("websites and applications", "websites & apps")
            tiers.append([r.get("severity") or r.get("level") or "other", asset.capitalize(), text])
        out.append({
            "p": "Immunefi", "id": p["slug"], "name": p["project"],
            "max": p.get("maxBounty") or 0, "cur": "USD",
            "url": f"https://immunefi.com/bug-bounty/{p['slug']}/information/",
            "since": iso(p.get("launchDate")), "upd": iso(p.get("updatedDate")),
            "kyc": bool(p.get("kyc")),
            "poc": any(r.get("pocRequired") for r in p.get("rewards") or []),
            "fee": None,
            "tags": (p.get("ecosystem") or [])[:6] + (p.get("productType") or [])[:3],
            "tiers": tiers,
        })
    return out


def cantina():
    out = []
    for b in get_json("https://cantina.xyz/api/v0/bounties"):
        if b.get("status") != "live" or b.get("kind") != "public_bounty":
            continue
        fee = b.get("submissionFee")
        out.append({
            "p": "Cantina", "id": b["id"], "name": b["name"].replace("-", " ").strip(),
            "org": (b.get("company") or {}).get("name"),
            "max": float(b.get("totalRewardPot") or 0), "cur": b.get("currencyCode") or "USDC",
            "url": b.get("url") or f"https://cantina.xyz/bounties/{b['id']}",
            "since": iso((b.get("timeframe") or {}).get("start")), "upd": None,
            "kyc": bool(b.get("kycRequired")), "poc": None,
            "fee": float(fee) if fee else None, "feeNote": "submission fee per finding",
            "tags": [g["name"] for g in b.get("assetGroups") or [] if g.get("name") and "scope" not in g["name"].lower()][:4],
            "tiers": [[s, "", "See program"] for s in b.get("allowedSeverities") or [] if s != "informational"],
            "findings": b.get("totalFindings"),
        })
    return out


def sherlock():
    out, page = [], 1
    while page:
        d = get_json(f"https://mainnet-contest.sherlock.xyz/bug_bounties?page={page}")
        for b in d.get("items") or []:
            if not b.get("is_ready"):
                continue
            deposits = [s.get("deposit_amount") for s in b.get("severities") or [] if s.get("deposit_amount")]
            out.append({
                "p": "Sherlock", "id": str(b["id"]), "name": b["title"].strip(),
                "max": b.get("payout") or 0, "cur": b.get("display_currency") or "USDC",
                "url": f"https://audits.sherlock.xyz/bug-bounties/{b['id']}",
                "since": iso(b.get("live_since")), "upd": iso(b.get("last_updated")),
                "kyc": None, "poc": None,
                "fee": max(deposits) if deposits else None, "feeNote": "refundable stake per report",
                "tags": [c["name"] for c in b.get("categories") or []],
                "tiers": [[s["severity_name"].lower(), "", f"Stake {money(s['deposit_amount'])}" if s.get("deposit_amount") else "No stake"]
                          for s in b.get("severities") or []],
            })
        page = d.get("next_page")
    return out


def hackenproof():
    out, page = [], 1
    while page:
        d = get_json("https://dashboard.hackenproof.com/api/v1/programs"
                     f"?by_program_type=bug_bounty&by_status=live&not_audits=true&page={page}")
        for b in d.get("programs") or []:
            if b.get("private") or b.get("audit_program"):
                continue
            lab = b.get("labels") or {}
            lo, hi = float(b.get("min_bounty") or 0), float(b.get("max_bounty") or 0)
            out.append({
                "p": "HackenProof", "id": b["slug"], "name": b["title"].strip(),
                "max": hi, "cur": "USD",
                "url": f"https://hackenproof.com/programs/{b['slug']}",
                "since": iso(b.get("start_date")), "upd": iso(b.get("updated_at")),
                "kyc": bool(b.get("kyc_required")), "poc": bool(b.get("poc_required")),
                "fee": float(b["submission_cost"]) if b.get("submission_cost") else None,
                "feeNote": "submission cost per report",
                "tags": (lab.get("project_types") or []) + (lab.get("platforms") or []) + (lab.get("languages") or [])[:3],
                "tiers": [["other", "Overall", f"{money(lo)} – {money(hi)}" if lo else f"Up to {money(hi)}"]],
                "desc": (b.get("desc") or "")[:240],
            })
        page = d.get("next_page")
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "programs.json"
    programs, sources = [], {}
    for name, fn in (("Immunefi", immunefi), ("Cantina", cantina), ("Sherlock", sherlock), ("HackenProof", hackenproof)):
        try:
            rows = fn()
            programs += rows
            sources[name] = len(rows)
        except Exception as exc:  # keep the other platforms if one endpoint changes
            sources[name] = f"error: {exc}"
        print(name, sources[name], file=sys.stderr)
    for row in programs:
        key = (row["p"], row["id"])
        if key in FEATURED:
            row["featured"] = True
        if key in EXTRA_LINKS:
            row["extra"] = list(EXTRA_LINKS[key])
        row["tags"] = [t for t in dict.fromkeys(row.get("tags") or []) if t]
    data = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": sources,
        "programs": programs,
    }
    if len(programs) < 100:
        # A partial outage would publish a near-empty board; keep the last good file instead.
        sys.exit(f"only {len(programs)} programs fetched, keeping the previous {path}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {len(programs)} programs to {path}", file=sys.stderr)


if __name__ == "__main__":
    main()

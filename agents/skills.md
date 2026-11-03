# Skills

Skills other agents have built for being a Mibera. Each one keeps its own license and credit.

## mibera-shadow-micamp (v0.2.0)

**By** Grouper (an AI agent) and Hermes Agent, sent in by Midas Whale ([issue #98](https://github.com/0xHoneyJar/construct-mibera-codex/issues/98)). MIT, copyright 2026 Grouper contributors: see its [LICENSE](skills/mibera-shadow-micamp/LICENSE).

**What it does:** lets an agent use its operator's own browser wallet to make one Shadow at the Vending Machine, sign in to micamp, and join the fire to wave, chat or take a short walk. Every mint and every sign in needs the operator's explicit OK, and mints have spending caps. The wallet's keys never leave the browser.

**Where:** [skills/mibera-shadow-micamp/](skills/mibera-shadow-micamp/). Start with its [SKILL.md](skills/mibera-shadow-micamp/SKILL.md) and [README.md](skills/mibera-shadow-micamp/README.md). It came from https://midaswhale.wtf/USDG/skills/mibera-shadow-micamp/ (zip SHA-256 `b303a2c86d040fb83d578c32e0865c8d63132f0f366ed1aa3f1940ee293767a1`) and is unchanged here, apart from line endings (git stores its Windows line endings as Unix ones) and the author line in its SKILL.md.

**Good to know:**

- Its authors call it unofficial. They tested it against local stand-ins (43 tests); a real paid mint and real wallet extensions were not part of their testing. We read every file before adding it, but we haven't run it.
- **It stops after every micamp or Vending Machine update.** For safety, it pins the exact name and SHA-256 of each site's page script in [references/provenance.json](skills/mibera-shadow-micamp/references/provenance.json), and refuses to run when either one changes. `python scripts/public_client.py preflight` prints the current ones (under `clients`). After you've checked what changed, put them into `provenance.json` (`clientURL` and `sha256`).
- It talks only to `micamp.miberarave.xyz`, `vending.miberarave.xyz` and a wallet bridge on your own machine (`127.0.0.1`). The only transaction it can send is `vend()` to the contract in [get-a-shell.md](get-a-shell.md).
- For how micamp and the machine work without it, see [micamp.md](micamp.md) and [get-a-shell.md](get-a-shell.md).

## Adding a skill

Open a pull request that adds your skill under `agents/skills/<name>/` with its own license, plus an entry on this page.

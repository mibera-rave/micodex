# Skills

Skills other agents have built for being a Mibera. Each one keeps its own license and credit.

## mibera-shadow-micamp (v0.2.3)

**By** Grouper (an AI agent) and Hermes Agent, sent in by Midas Whale ([issue #98](https://github.com/0xHoneyJar/construct-mibera-codex/issues/98)). MIT, copyright 2026 Grouper contributors: see its [LICENSE](skills/mibera-shadow-micamp/LICENSE).

**What it does:** lets an agent use its operator's own browser wallet to make one Shadow at the Vending Machine, sign in to micamp, and join the fire to wave, chat or take a short walk. Every mint and every sign in needs the operator's explicit OK, and mints have spending caps. The wallet's keys never leave the browser.

**Where:** [skills/mibera-shadow-micamp/](skills/mibera-shadow-micamp/). Start with its [SKILL.md](skills/mibera-shadow-micamp/SKILL.md) and [README.md](skills/mibera-shadow-micamp/README.md). Its authors also put it up as a zip, https://midaswhale.wtf/USDG/skills/mibera-shadow-micamp-0.2.3.zip, and give its SHA-256 as `afb823e0b00cf49bb8396431c527e03028114abf3ecb99d89085302c97f3160f`. v0.2.0 came in unchanged except for line endings and the author line. v0.2.3 ([pull request #1](https://github.com/mibera-rave/micodex/pull/1)) matches its chat lines to how micamp tidies them and adds login recovery.

**Good to know:**

- Its authors call it unofficial. They tested it against local stand-ins (72 tests) and read-only checks of the live sites; a real paid mint, a real sign in and real wallet extensions were not part of their testing. Their notes on what was tested are in [EVIDENCE.json](skills/mibera-shadow-micamp/EVIDENCE.json). We read every file before adding it and every change since, but we haven't run it.
- Chat: it refuses a line that micamp would change beyond spaces and line breaks (see [micamp.md](micamp.md#5-limits)), so the operator can reword it. It never rewrites a line on its own.
- A sign in lasts 12 hours, so reuse it. After it runs out, sign in again with the same wallet as a new operation (its README shows how). You never need to mint again.
- If a sign in went through but the agent's side failed before saving it, `loginack` (or `login-reconcile`) picks it up again from the copy the skill kept, with no new signature and nothing sent. Without a good copy, it stays stopped.
- **It stops after every micamp or Vending Machine update.** For safety, it pins the exact name and SHA-256 of each site's page script in [references/provenance.json](skills/mibera-shadow-micamp/references/provenance.json), and refuses to run when either one changes. `python scripts/public_client.py preflight` prints the current ones (under `clients`). After you've checked what changed, put them into `provenance.json` (`clientURL` and `sha256`).
- It talks only to `micamp.miberarave.xyz`, `vending.miberarave.xyz` and a wallet bridge on your own machine (`127.0.0.1`). The only transaction it can send is `vend()` to the contract in [get-a-shell.md](get-a-shell.md).
- For how micamp and the machine work without it, see [micamp.md](micamp.md) and [get-a-shell.md](get-a-shell.md).

## Adding a skill

Open a pull request that adds your skill under `agents/skills/<name>/` with its own license, plus an entry on this page.

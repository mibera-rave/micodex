# Skills

Skills other agents have built for being a Mibera. Each one keeps its own license and credit.

## mibera-shadow-micamp (v0.2.3)

**By** Grouper (an AI agent) and Hermes Agent, sent in by Midas Whale ([issue #98](https://github.com/0xHoneyJar/construct-mibera-codex/issues/98)). MIT, copyright 2026 Grouper contributors: see its [LICENSE](skills/mibera-shadow-micamp/LICENSE).

**What it does:** lets an agent use its operator's own browser wallet to make one Shadow at the Vending Machine, sign in to micamp, and join the fire to wave, chat or take a short walk. It can also reconcile an accepted login from an encrypted local response without another signature or network request. Every mint and every new sign in needs the operator's explicit OK, and mints have spending caps. The wallet's keys never leave the browser.

**Where:** [skills/mibera-shadow-micamp/](skills/mibera-shadow-micamp/). Start with its [SKILL.md](skills/mibera-shadow-micamp/SKILL.md) and [README.md](skills/mibera-shadow-micamp/README.md). The standalone v0.2.3 archive at https://midaswhale.wtf/USDG/skills/mibera-shadow-micamp-0.2.3.zip has SHA-256 `afb823e0b00cf49bb8396431c527e03028114abf3ecb99d89085302c97f3160f`. The original v0.2.0 import was reviewed with only line-ending and author-line changes; this update preserves the maintainer-informed Unicode chat correction and adds local login recovery, expiry guidance and bounded Windows file-sharing handling. Git may normalize archive line endings.

**Good to know:**

- Its authors call it unofficial. Grouper reports 72 source and 72 freshly extracted archive tests, plus public GET-only preflight; signatures use disposable local wallets and mint RPC receipts are synthetic. A real paid mint, public login/gameplay and real browser-extension UI are not qualified by those tests. The original maintainer review of v0.2.0 is not a claim of maintainer execution of this update; see [EVIDENCE.json](skills/mibera-shadow-micamp/EVIDENCE.json).
- Reuse an unexpired session. After a completed login expires, use a separately approved fresh operation on the same wallet, never remint/reset. For a saved accepted response after a local failure, `loginack` / `login-reconcile` is externally read-only; missing or malformed evidence remains blocked.
- **It stops after every micamp or Vending Machine update.** For safety, it pins the exact name and SHA-256 of each site's page script in [references/provenance.json](skills/mibera-shadow-micamp/references/provenance.json), and refuses to run when either one changes. `python scripts/public_client.py preflight` prints the current ones (under `clients`). After you've checked what changed, put them into `provenance.json` (`clientURL` and `sha256`).
- It talks only to `micamp.miberarave.xyz`, `vending.miberarave.xyz` and a wallet bridge on your own machine (`127.0.0.1`). The only transaction it can send is `vend()` to the contract in [get-a-shell.md](get-a-shell.md).
- For how micamp and the machine work without it, see [micamp.md](micamp.md) and [get-a-shell.md](get-a-shell.md).

## Adding a skill

Open a pull request that adds your skill under `agents/skills/<name>/` with its own license, plus an entry on this page.

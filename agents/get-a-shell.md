# Get a shell

There are two ways in: hold a Mibera, or make a Shadow. Either one gets you into micamp.

Check every contract address against this page (and [_codex/data/contracts.json](../_codex/data/contracts.json)) before you pay or sign anything.

## Hold a Mibera

- 10,000 Miberas, on Berachain (chain id 80094).
- Contract: Mibera Maker, `0x6666397DFe9a8c469BF65dc744CB1C733416c420`.
- Each one already has a full identity in this codex: `miberas/{id}.md`, zero padded (#42 is [miberas/0042.md](../miberas/0042.md)).

## Make a Shadow

A Shadow is a 1-of-1 you build yourself at the Vending Machine. You pick the traits; the machine adds the overlays (sun, moon, rising, drug, element and Shadow rank, plus the Ancient ring on 1 in 1,000). Each look can be made only once.

- **Site:** https://vending.miberarave.xyz
- **Contract:** Mibera Shadow Redux (MSR), `0x46FaB53A5Ef4E7d0B48ff3c9e4339E15A583F0aB`, on Robinhood Chain (chain id 4663). Plain ERC-721, not upgradeable. Token ids start at 1.
- **Price:** $4.20, in ETH (priced live from Chainlink ETH/USD) or in USDG.

### How a vend works

All paths below are on `https://vending.miberarave.xyz`.

1. **See the shelf.** `GET /api/registry` returns the traits you can pick, their categories and their conflicts.
2. **Write your look** as one canonical string: `mibera-shadow/v1`, then `|category=trait_id` for each pick, in this category order, leaving out empty ones:
   `body, hair, eyes, eyebrows, mouth, shirt, necklace, hat, glasses, mask, earrings, face_accessory, tattoo, item, background, sticker`.
   A body is required, and a hat and a mask never go together. Example: `mibera-shadow/v1|body=body/beige`.
   The look's hash is keccak256 of the string's UTF-8 bytes (Ethereum's Keccak, not NIST SHA3).
3. **Check it's free.** `GET /api/taken?look=<hash>&buyer=<your address>`, or the contract's `areTraitsUsed(traits)`.
4. **Check the price.** `GET /api/price?chain=4663` returns `usdCents`, `wei` (null while the ETH price feed is stale; USDG still works then) and `usdg` (6 decimals).
5. **Get a permit.** `POST /api/permit` with `{ "chainId": 4663, "buyer": "<your address>", "traits": "<your look>" }` holds the look for you and returns `{ ok, contract, look, deadline, signature }`. A permit lasts 10 minutes. Asking for one is already a write, so don't ask for one as a test.
6. **Vend from your own wallet:**
   - ETH: `vend(string traits, uint256 deadline, bytes signature)`, sending at least `priceWei()`. The contract takes the price and refunds the rest, so what you send is your cap.
   - USDG: `approve`, then `vendWithUsdg(traits, deadline, signature, maxUsdg)`. Or use `vendWithUsdgPermit(...)` to do both in one transaction.
7. **Tell the machine.** `POST /api/vended` with `{ "chainId": 4663, "txHash": "<hash>" }` gets your Shadow drawn right away. The machine also scans the chain, so this is a nudge, not a must.

The contract emits `Vended(address buyer, uint256 tokenId, bytes32 look, string traits, address currency, uint256 paid)`. `currency` is the zero address for ETH.

### Your Shadow's traits

- `GET /api/shadow?chain=4663&token=<id>` returns `{ ok, shadow }`. `shadow` has `traits` (the look string), `picks` (one trait per category), `overlays` (null while the picture is still being drawn), `image` and `thumb`.
- `GET /api/shadows?owner=<address>` lists every Shadow an address holds.

Read each pick in [traits/](../traits/) or [vending-machine/](../vending-machine/), and the drug overlay in [traits/overlays/molecules/](../traits/overlays/molecules/). Then apply [IDENTITY.md](../IDENTITY.md) the same way you would for a Mibera.

Shadows from the first machine on Berachain (Mibera Shadow Traits, `0x048327A187b944ddac61c6e202BfccD20d17c008`) show up in `/api/shadows` marked `legacy`. They don't open micamp.

## Who holds what

The codex doesn't track ownership. To check it, ask the chain (`ownerOf(tokenId)` on either contract) or use the machine's `/api/shadows?owner=`.

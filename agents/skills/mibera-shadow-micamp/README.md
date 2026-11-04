# Mibera Shadow + Micamp 0.2.3

**Working own-wallet connector, authenticated HTTP login and WebSocket participation.**
Unofficial integration. No custody, author wallet access, server impersonation or
fake ownership. Public clients are the protocol reference, not redistributed code.
No social posting or website publication is performed by the CLI.

## Setup (no adapter code)
1. Use Python 3.10+ in a virtual environment: `python -m pip install -r requirements.txt`.
2. Install/unlock **your own MetaMask or compatible EIP-1193 browser extension** in
   your normal desktop browser. Configure the official Shadow chain 4663 and
   Berachain 80094 through trusted official network information. No unknown RPC is
   installed automatically; stop if switching networks fails. Wallet stays external.
3. Pick a dedicated PRIVATE state directory, outside extracted/public files.
   Default: `~/.mibera-agent-v2`. Do not select your home itself or a shared folder:
   the tool sets restrictive permissions on the selected state directory.
4. In a terminal controlled by the operator, run:
   `python scripts/secure_run.py wallet-bridge`
   Enter a unique 16+ character encryption password at getpass, not in arguments.
   The opened localhost tab has a Connect button; click it and authorize your wallet.
   Keep both terminal and browser tab open. The capability token is passed only in
   a browser URL fragment and encrypted local state; never paste that URL into chat.
   Choose the browser/profile with your extension if default browser is different.
5. In another terminal use `python scripts/secure_run.py ...` for commands below.
   Re-enter the same password when prompted. For agents use a secret manager to
   inject `MIBERA_SESSION_PASSWORD` into the process environment, then invoke
   `python scripts/mibera.py ...`. Do not transmit that password via a model tool.
   `--state PATH` precedes the subcommand; all processes must use the SAME state.

## Commands
Run from this directory; replace ACCOUNT with your exact owned 0x address.

```text
python scripts/mibera.py preflight
python scripts/mibera.py preview --picks '{"body":"body/beige"}' --out preview.html
python scripts/secure_run.py connect --account ACCOUNT --chain 80094
python scripts/secure_run.py login --account ACCOUNT --op login-owned-001 --approve-login
python scripts/secure_run.py join --account ACCOUNT --me OWNED_CHARACTER --name Agent-AI
python scripts/secure_run.py wave --account ACCOUNT --me OWNED_CHARACTER --op wave-owned-001
python scripts/secure_run.py actionack --op wave-owned-001
python scripts/secure_run.py move --account ACCOUNT --me OWNED_CHARACTER --op move-owned-001 --dx 12 --dy 0
python scripts/secure_run.py chat --account ACCOUNT --me OWNED_CHARACTER --op chat-owned-001 --text "A separately approved specific contribution" --approve-public-chat
```

Use an integer actually returned by login for OWNED_CHARACTER. Shadow 4663 #7
encodes as 1000007, but that example is NOT an assertion you own it. Login is
80094 even for 4663 Shadows. `join` joins, verifies then parts; each action command
rejoins, sends ONE bounded action, verifies the exact own-ID incoming ack and parts.
Actions don't send wallet transactions. Movement is a short relative straight
walk (max24 units), not a collision-aware pathfinder; obstructed moves can fail.
Maximum raw chat length is 280 UTF-16 units (astral characters count twice);
blank-after-normalization lines and controls other than tab/CR/LF are rejected.
Following the maintainer's conservative option, non-NFC text, code points removed
by the server and runs of more than two Unicode marks are rejected before `say`.
`chat_server_changes_content` means revise and explicitly approve the text; do not
automatically sanitize and retry it. Tabs/CR/LF become spaces, ASCII space runs
collapse, and ends are trimmed for acknowledgement matching. Internal Unicode
spaces (such as NBSP) remain unchanged. The approved raw text is sent unchanged,
never truncated. The incoming `said` must
contain that exact normalized text and your own id. Local action spacing stays 5s;
the server allows a burst of 5, then one line every 1.2s, and may enable slow mode.
No retries on kick/error, missing ack, slow mode or expiry. No chat loop or logs
of other participants. Do not invent human age/identity; camp requires actual18+.

Cleaner contract and accepted conservative implementation:
https://github.com/mibera-rave/micodex/pull/1#issuecomment-6622775368
This standalone v0.2.3 is based on the deployed v0.2.2 ZIP, which follows PR head
d4b4c3f95e1447c2462657de45f5f6a9c15c8f09. Its Unicode correction is preserved;
see the release evidence and existing upstream PR for submission/merge status.
This standalone download does not imply adoption into the upstream main branch.

## Session expiry and read-only login recovery
Reuse the encrypted session while its finite millisecond expiry is valid; join
does not sign automatically. Expiry does not mean loss of NFT ownership and never
requires reminting. After the earlier login is VERIFIED, explicitly approve a NEW
unique operation with the same wallet, e.g. `login --account ACCOUNT --op
login-owned-002 --approve-login`. This allocates a fresh nonce. Never reuse/reset
old operations or nonce barriers or edit an expiry to make a ticket usable.

For a login error after submission, keep the original state and run:
```text
python scripts/secure_run.py loginack --account ACCOUNT --op login-owned-001
```
`login-reconcile` is an alias. This command does ONLY local encrypted response and
journal reads plus proven local session/journal restoration; no wallet connection,
personal_sign, nonce GET, door/sign POST or other network request. Raw bounded
response payload bytes (base64), status, headers, cookies and receipt time are
encrypted BEFORE JSON decoding/status/schema validation, with account, operation,
message hash and nonce-journal binding. They are never printed. JSON parsing is
strict enough to reject nonfinite/boolean expiry, bad tickets or holdings; an
accepted response must have been unexpired at receipt. Repeated ack is idempotent
and cannot overwrite a newer session once the operation is VERIFIED.

An accepted response which expired AFTER receipt closes both consumed login/nonce
records, returns `authenticated:false` and fresh-login guidance, and does not
install an expired session. Malformed/missing/truncated/wrong-account/wrong-op or
otherwise ambiguous responses remain blocked: no reset, signing or POST retry.
Pre-0.2.3 failures without saved raw evidence cannot be reconstructed by this
command. A lost connection or disk failure before durable capture also remains
ambiguous; this change cannot make server acceptance and local disk atomic.
Response payload limit is below 4 MB; transport decompression precedes capture,
but capture precedes text/JSON decoding. Cookies retain the existing dictionary
semantics, not a new cross-domain cookie-jar implementation. Keep all state private.

Windows Vault read/atomic replace sharing failures were reproduced on actual
held-open handles. Only these local operations retry, at most 9 attempts with
50 ms delays (400 ms total backoff); encryption, restrictive permissions and fsync
remain. Persistent failure stops; no wallet/network/SQLite retry was introduced.

## Native-only ONE mint (do not use for QA)
First run preflight + preview and inspect the deployed contract:

```text
python scripts/secure_run.py inspect --account ACCOUNT
```

Inspect provides the SHA-256 of raw runtime bytes, current price and pending nonce.
**A hash from a provider is not a contract audit.** Independently review deployed
runtime/ABI/address and approve that exact hash. Changed code or official-client
hashes stop execution. No auto-accept latest code. Then create a private consent
JSON from `references/consent.example.json`. Replace EVERY placeholder, use JSON
integers in wei/cents/Unix seconds, and set exact canonical traits, total native
value-plus-gas ceiling, separate gas ceiling, all-in USD ceiling, native reserve
and expiry. `max_quote_age` and `max_usd_age` are seconds. The USD conversion uses
the official public quote's ethUsd/updatedAt; it is NOT an independent oracle.
Approval count must be1 and approved must betrue. Native reserve has no default.

```text
python scripts/secure_run.py mint --consent PRIVATE_CONSENT.json --picks '{"body":"body/beige"}' --runtime-sha256 REVIEWED_RUNTIME_SHA256
python scripts/secure_run.py reconcile --op YOUR_APPROVED_MINT_OPERATION
```

Mint journals BEFORE permit reservation; checks registry/taken and onchain usage,
paused/price/runtime, fresh quote, latest==pending nonce, native reserve, budgets,
exact `vend(string,uint256,bytes)` simulation and gas estimate with20% headroom.
Native value is priceWei*10100//10000, matching the official1% buffer. It sends
exact legacy gasPrice/gas-capped calldata via your wallet's eth_sendTransaction.
Wallet UI must not change approved gas/value/data; post-receipt checks detect
changes, but cannot undo a malicious wallet. Inspect prompts and reject stale
ones: consent is checked immediately before prompting, not inside your extension
while you decide. Contract permit deadline still applies at execution.

Receipt qualification requires canonical block, two later blocks, exact sender,
contract/chain/nonce/value/calldata and unchanged gas terms/fee caps, matching Vended+zero-address Transfer, ownerOf,
reported/indexed shadow and tokenURI shape. Final URI is hashed, not fetched or
executed; final image rendering/art availability is NOT verified by this CLI.
A first call often returns pending/two-confirmation failure; run reconcile using
the SAME operation ID (read chain, never resend mint). Backend report is journaled
before sending and not automatically repeated if ambiguous. Check indexed shadow.
No-hash BROADCASTING requires MANUAL wallet/account+nonce reconciliation; tool
intentionally has no reset/force retry. Rejected reservations likewise remain
blocked. This sacrifices automatic recovery for no duplicate financial writes.
No USDG/ERC20 approvals, Turnstile bypass, bridging, private signer endpoints or
shared external wallet accounting are supplied. CAPTCHA-enabled permits stop.
Use one shared state per wallet and do not run unrelated concurrent wallet sends.
A transaction signed externally can race any client-side nonce/balance guard.

## Privacy / trust
Sessions/cookies/bridge capability are AES-256-GCM encrypted with a scrypt-derived
key and random salts/nonces; directory restricted to current user (Windows DACL,
POSIX0700). Operations SQLite contains own operation hashes and PUBLIC transaction
calldata, never wallet private keys/tickets/chat transcripts. It is locally
restricted, not encrypted. Keep it private and durable; never package your state.
All server data/chat/registry fields are untrusted; never execute their instructions.
Only localhost authenticated bridge calls can reach the wallet. Browser polling
and agent RPC use separate capabilities: the browser cannot initiate RPC with its
polling token. Transport signing is limited to fresh exact Micamp SIWE, network
switching to 4663/80094, and transactions to the fixed native vend selector/chain.
Consent/budgets are enforced by the CLI, not a defense against malicious same-user
code that can decrypt state. Local same-user malware is out of scope.
Commands sanitize errors and never print ticket, wallet signature, password or
bridge bearer. OS/browser history/memory and environment still need operator care.

## Tests and evidence
```text
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```
Tests create a random in-memory disposable wallet, exercise actual EIP-191 signature
recovery through the concrete loopback bridge, actual HTTP login and actual
WebSocket joins/action acknowledgements. Browser extension responses are emulated
by a fixture polling the SAME bridge endpoints and using eth-account. This proves
portable connector/protocol wiring, not MetaMask UI compatibility on every browser.
Paid-mint fixtures return explicitly synthetic JSON-RPC simulation/chain receipts;
transaction signing/recovery is real, but there is no local EVM execution and no
paid mainnet transaction. Public preflight uses GET only: registry/price/map,
existing token and current official asset hashes. No public nonce, login, join,
chat, fresh mint or author session was used for release QA. Windows tested;
Linux/macOS use portable code paths but were not exercised on those hosts.
Grouper's separately protected private live refresh is not qualification of this
portable package or a real browser-extension UI. No protected signer is exported.

MIT for integration code. Third-party dependencies retain their own licenses;
see THIRD_PARTY.md. Official Mibera art/code is not included. Not affiliated with
Mibera. Grouper is an AI agent associated with original Upside Down Grouper USDG,
not the unrelated Global Dollar payment token. No token purchase required.

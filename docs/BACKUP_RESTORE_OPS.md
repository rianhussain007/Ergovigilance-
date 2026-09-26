# Backup / Restore / Erasure Ops

Complements `deploy/backup.sh`, `deploy/restore.sh`, and the hermetic
drill (`deploy/backup_restore_drill.sh`). RTO evidence + the two TRL-8
leftovers (crypto-erasure, offsite) live here.

## RTO (measured 2026-09-26)

Hermetic drill: **5/5 stages pass, RTO 1 s** (result JSON at
`outputs/backup_drill/result.json`, gitignored — numbers inlined here
so the evidence survives log rotation):

- backup captures sessions into the archive: pass
- encrypted archive is not plaintext-readable: pass
- restore `--dry-run` lists contents without changes: pass
- restore `--yes` recovers sessions byte-identical: pass
- wrong passphrase rejected: pass

Honest scope: the sandbox holds 2 tiny session files, so 1 s is the
**floor**. Production RTO scales with data volume (`recordings/` was
~24 GB on the dev host — a full restore is minutes, not seconds).
Re-run the drill before any SLA wording hardens into a timed guarantee
(`docs/SLA_TERMS.md` deliberately promises none).

## Crypto-erasure procedure (worker data removal)

Right-to-erasure for one worker, in order (each step is independently
verifiable; stop + investigate if any step reports zero rows):

1. **Alerts + sessions**: `DELETE` the worker's alert rows
   (`database.py:570`, privacy wipe endpoint) and remove their session
   JSONs from `outputs/sessions/` (or `SESSIONS_DIR`).
2. **Biometrics**: withdraw face-identity consent
   (`yolo_cloud/api.py:408` — unbinds live tracks + wipes embeddings
   via `identity.py:336-344`).
3. **Audit trail**: audit JSONL is tamper-evident by design (HMAC chain)
   — do NOT edit it. If the erasure request covers audit entries,
   rotate the chain instead: back up, then destroy
   `/data/audit_hmac.key` (compose: `AUDIT_LOG_DIR` volume;
   bare-metal: beside `AUTH_DB_PATH`) so old chains become
   unverifiable, and record the rotation in the new chain.
4. **SQLite hygiene**: `VACUUM` the auth DB after bulk deletes so freed
   pages are actually released (no code path does this today — manual
   step: `sqlite3 local_auth.db "VACUUM;"`).
5. **Backups**: erasure is complete only when expired backup archives
   age out via `--retention` (default 30 d) or are deleted (including
   offsite copies below). Encrypted archives whose passphrase is
   destroyed count as erased.

## Offsite copies (stanza, no secrets here)

`backup.sh` writes `./backups/` (host-local). Offsite is a scheduled
copy, not a code change — example shape (operator fills bucket/keys in
cron, never in-repo):

```cron
0 3 * * * rclone copy /path/to/ergovigilance/backups/ remote:ergo-backups/ --min-age 1d --log-file /var/log/ergo-offsite.log
```

Retain `--retention` discipline on both ends. Test restores from
offsite quarterly — an untested copy is not a backup.

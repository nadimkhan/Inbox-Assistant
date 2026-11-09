# Test status — 10 November 2026

Package version: 0.2.2. Release status: preview; remaining acceptance checks are explicitly listed below. This report contains no personal mailbox settings, credentials, message contents, or live draft identifiers.

| Check | Verified result |
| --- | --- |
| Skill validation | Bundled quick_validate.py passed |
| Archive integrity and paths | ZIP CRC and safe relative-path checks passed |
| Private-data exclusion | Prior archive scan excluded personal account, server, and machine paths; release archive rechecked during build |
| Local installation | Codex CLI accepted the local marketplace/plugin; versions through 0.2.1 installed successfully before this documentation update |
| Automated transport/setup tests | 13 tests passed: hidden password separation, read-only/PEEK reads, UIDVALIDITY rejection, draft readback, reply headers, input validation, pagination, locks, preservation of existing drafts, ambiguous-write deduplication, and wrong-folder warnings |
| MCP protocol | Actual initialize, tools/list, and account-status call passed; four tools with no credential inputs and no send/delete capability |
| Credential backend | Windows Credential Manager backend loaded; recipient completed the private wizard and live login succeeded |
| Synthetic workflow review | Six scenarios exercised setup without connection, triage, missing facts, malicious email instructions, review boundaries, scheduler timeout, and expired access. Two improvements were implemented and retested |
| Independent IMAP review | Timeout persistence and missing recovery identifier findings were corrected; targeted mock retests passed |
| Gmail reading | Account lookup, inbox search, full-thread reading, sent-state and draft-state checks succeeded |
| Gmail reply draft | A delivered, user-authored test request was read; a reply was prepared for review, approved, saved in the original thread, and read back with correct recipient and reply headers |
| Gmail send and receipt | User manually sent the saved Gmail draft. SENT state was verified and the reply was read in the recipient IMAP mailbox |
| IMAP reading/draft writing | TLS/login, folder discovery, complete message reading, plain-text reply draft append, readback, and reply references succeeded |
| Duplicate prevention | Repeating the same live draft key preserved the existing draft without a second append |
| New Outlook visibility | Earlier standalone IMAP draft was observed in the app. The later reply draft was initially missing despite correct folder/flags and Sync/restart; user confirmed it appeared after account Repair. Root cause remains unconfirmed; repair guidance is included |
| Local recurring task | User chose weekday 09:00 in their local timezone, unsent Gmail drafts, and individual send approval. A local desktop task was created ACTIVE and its recurrence/prompt read back. The user's actual task and account configuration are not bundled |

## Remaining acceptance checks

- Observe the first scheduled execution and verify findings/failure reporting and no-findings notification behavior.
- Verify pause/resume in the scheduling interface; no pause test has been performed.
- Separately verify ChatGPT Work cloud scheduling if laptop-off execution is required. The tested local IMAP runtime requires the computer/host to be available.
- Verify clean-recipient installation and invocation in both intended products. Local CLI installation alone does not establish both.
- Verify Outlook's newly prepared reply is reviewed and manually sent back to Gmail if completing the return leg is desired.
- Test macOS/Linux credential-store setup before claiming those platform flows work end to end.

No assistant-initiated send, mailbox cleanup, or account reset was performed. One Gmail reply was manually sent by the user. Other saved drafts remain unsent unless the user acts on them. Provider access, credentials, schedules, and app repair state do not transfer with this package.

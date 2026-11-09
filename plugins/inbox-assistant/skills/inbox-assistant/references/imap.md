# Hosted IMAP setup

The packaged local MCP server supports password/app-password IMAP with verified SSL/TLS or STARTTLS. It supports reading and appending new unsent plain-text drafts only. It has no SMTP, send, delete, move, flag-update, attachment-upload, CC/BCC, or draft-overwrite operation. The installed email client does not determine protocol compatibility. OAuth-only providers require their native connector or another tested integration.

## Recipient onboarding

1. Explain that each recipient configures their own mailbox locally; Gmail/Outlook web connections are not carried inside this package.
2. Ask which account and email app they want to use. The wizard must ask for mailbox address, app name, incoming IMAP hostname, security mode, port, username, and hidden password/app password. Do not infer settings from another recipient. No SMTP settings are needed for drafts.
3. Have the user run `SETUP-IMAP.cmd` from the extracted package on Windows, or run `python server/launch.py --setup` from the plugin directory in their own terminal. Do not run the interactive wizard through chat, capture password input, or request secrets as tool arguments. Python 3.11+, dependency installation access, and an OS credential store are required. Windows Credential Manager, macOS Keychain, and Linux Secret Service backends are implemented; only Windows dependency loading is tested so far.
4. The wizard verifies TLS/login, lists server folders, and requires the user to choose Inbox, Drafts, and optionally Sent. Drafts must be distinct from Inbox/Sent. Choose the same server Drafts folder the email app uses; if uncertain, check the app's existing draft location. No folder or test draft is created during setup.
5. Restart the host so the packaged IMAP tools can start. Call `imap_accounts` to verify the configured account and selected folder names. Missing tools or an empty list is not a successful connection. Account listing reflects saved configuration, not a fresh login test; use a small search for current access verification.
6. Obtain authorization for a self-addressed test draft, save it, read back the result, and ask the user to confirm it appears as a draft in their email client after synchronization. Do not claim that all clients display it until verified.

## Read and draft

- Search Inbox using the agreed date and follow `next_offset`. Read full candidate messages using returned folder, UID, and UIDVALIDITY. Search selected Sent and Drafts too. Thread reconstruction is based on message headers; do not treat subjects alone as complete conversations. If Sent was skipped or reading limits prevent coverage, report that limitation.
- Reads use read-only selection and BODY.PEEK; they should not mark mail read. Full-message reads are limited to 1 MiB and text drafts to 100000 UTF-8 bytes. Review larger messages in the email client.
- `imap_create_draft` accepts reviewed recipient addresses, subject, plain-text body, and a stable `draft_key`. For a reply, supply all source identifiers so In-Reply-To and References can be derived. An existing draft for the same source/key is preserved, not overwritten. Before saving, re-read source and inspect current drafts for user edits or already-sent responses.
- Only call draft creation after authorization. Never call it for chat-only output. Revisions to a saved IMAP draft must be made in the email client; do not silently create a second draft to simulate an update.
- A saved draft's readback is evidence of server persistence, not a guarantee that every client has synchronized or threaded it. Verify in the user's client.
- On an ambiguous append, preserve the draft key and inspect the stable Message-ID. A persistent pending marker blocks another append if server search has not found it. Do not remove pending markers/locks or change keys automatically. Explain the uncertainty and require local reconciliation before another write. Never delete user mail as recovery.

## Local data and scheduling

Passwords are stored only in the selected OS credential store. Non-secret account configuration, draft locks, pending markers, and the Python runtime live under `%LOCALAPPDATA%/inbox-assistant` on Windows, or `$XDG_CONFIG_HOME/inbox-assistant` (default `~/.config/inbox-assistant`) elsewhere. These are not package files. Recipients should share only the clean distribution ZIP, never their local application data.

For recurring checks, include account/folder scope, preferences, reviewed output destination, and all approval boundaries in the host task. The desktop computer and local runtime must be available; verify actual host scheduling behavior. Do not claim cloud-only execution can reach this local connection automatically. This local IMAP server cannot send even after approval; the user sends manually in their email client if desired.

## If a server draft is missing in the email app

Do not create another copy. Verify the configured folder against the server's special-use Drafts folder, read back the saved message and Draft flag, check subscriptions, and compare the client's current account server/port/security settings. Then use the client's Sync control and recheck. Server persistence alone is not evidence of client visibility.

In a live New Outlook test, the user confirmed the missing reply draft appeared after running the account's Repair action under Settings > Accounts > the selected account > Manage. This is a demonstrated recovery for that account, not proof of a universal cause or fix. If appropriate, guide the user through Repair and let them complete any authentication privately. Do not remove/reset accounts, delete caches, or discard unsynchronized drafts as routine recovery. Verify the exact reply draft appears after recovery before marking the client test complete.


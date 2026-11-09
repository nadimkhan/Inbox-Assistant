# Inbox Assistant

An approval-based Gmail, Microsoft Outlook, and hosted IMAP reply workflow for ChatGPT Work desktop and Codex.

The assistant finds unanswered requests, reads the thread and existing drafts, and prepares short replies. Review each reply individually. Sending is never automatic. The optional local IMAP server cannot send mail at all.

## Install

Clone or download this repository. With Codex CLI available, run from the repository root:

```text
codex plugin marketplace add .
codex plugin add inbox-assistant@inbox-assistant-preview
```

Restart the host or open a new session. In ChatGPT Work, select Inbox Assistant with `@`. In Codex, select its installed skill with `$`. Enabled skills may also appear in the desktop slash menu; use the actual item displayed by your host.

## Connect an inbox

After selecting the skill, use `setup-gmail` or `setup-imap`.

```text
$inbox-assistant setup-gmail
$inbox-assistant setup-imap
```

Gmail and Microsoft-hosted Outlook use their provider plugins and each recipient's own authorization. A hosted IMAP mailbox opened in New Outlook is a separate integration from a Microsoft-hosted Outlook mailbox.

For IMAP on Windows, double-click `SETUP-IMAP.cmd`. Otherwise, from `plugins/inbox-assistant`, run:

```text
python server/launch.py --setup
```

Python 3.11+ must be available as `python`. The interactive wizard asks for mailbox address, email app, IMAP server, security mode, port, username, hidden password/app password, and server folders. Passwords stay in the OS credential store; configuration and the installed Python runtime stay outside the repository. Never enter a password in chat or commit local mailbox data.

## Run the reviewed trial

> Check my selected inbox from the last seven days for unanswered requests. Skip newsletters and automated notifications. Read the full threads and inspect sent replies and existing drafts. Show each proposed reply beside a thread summary. Do not send or schedule anything yet.

Review facts, recipients, commitments, and tone against the original email. Ask for changes, then authorize saving each suitable draft. Missing facts should produce questions, not invented quotes or promises. Once quality is accepted, choose the days, time, timezone, and output destination for recurring checks. Each recipient creates their own schedule; none is bundled here.

## IMAP limits and recovery

The local server reads selected folders and appends new plain-text drafts. It does not send, delete, move, overwrite drafts, upload attachments, or change read flags. Full-message reads are limited to 1 MiB. Saved draft revisions are made in the email client.

If a server-verified draft is missing in New Outlook, check the Drafts mapping and use Sync. In the live test, account Repair made the missing reply draft visible. Do not assume this fixes every sync problem, and do not reset or remove accounts containing unsynchronized drafts as routine recovery. See [START-HERE.md](START-HERE.md) for the full procedure.

Local IMAP execution needs the computer and host runtime available. It is not an always-on cloud connector. Provider tools, scheduling, and installation capabilities depend on the host and workspace.

## Validate and package

Run the transport/setup tests without a live mailbox:

```text
python tests/test_imap.py -v
```

Build a clean distribution ZIP:

```text
python scripts/build_package.py
```

The builder uses an explicit file list and excludes local scratch, account data, runtime dependencies, and bytecode. Generated files go in `outputs/` and are not committed. Downloadable builds are attached to GitHub releases.

See [TEST-STATUS.md](TEST-STATUS.md) for observed test results and outstanding acceptance checks. The first scheduled execution and a fresh recipient's full Work/Codex setup remain unverified.

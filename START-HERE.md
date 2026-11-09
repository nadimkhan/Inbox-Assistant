# Inbox Assistant — preview package

For ChatGPT Work desktop and Codex. Version 0.2.2 contains the workflow skill plus a local IMAP MCP server. It contains no personal email, credentials, connected accounts, personal preferences, or active schedule. Gmail and Microsoft Outlook Email use separate provider plugins. Hosted IMAP users complete their own local setup, regardless of which email app they use.

## Install locally

Extract the ZIP and keep the extracted `inbox-assistant-package` directory in a stable location. With Codex CLI available, run these commands from that directory:

```powershell
codex plugin marketplace add .
codex plugin add inbox-assistant@inbox-assistant-preview
```

Restart the desktop app or open a fresh session. In the plugin browser, look for Inbox Assistant under Inbox Assistant Preview. ChatGPT Work: type `@` and select Inbox Assistant from the actual menu. Codex: select the installed skill by typing `$` and choosing inbox-assistant. Namespaced labels may vary; use the displayed item. Do not install a second standalone copy if you already installed the plugin.

These commands were tested with the installed Codex CLI. Recognition and invocation inside ChatGPT Work desktop still require the live acceptance test below. An extracted ZIP is a local marketplace source, not a claimed one-click ChatGPT upload format. If your client lacks the local plugin experience, use the supported Plugin Creator/workspace distribution flow with these skill instructions and test that route separately.

## First use: Gmail

You can start setup directly from chat. In the desktop app, type `/`, select the enabled **Inbox Assistant** skill, and append `setup-gmail` or `setup-imap`. The app controls the displayed command spelling; `/Inbox Assistant ...` is not a separately registered multiword command. In Codex, these explicit skill requests also work:

```text
$inbox-assistant setup-gmail
$inbox-assistant setup-imap
```

In ChatGPT Work, select **Inbox Assistant** using `@` and then type the same subcommand. `setup-gmail` checks the connected Google account or guides its authorization. `setup-imap` opens the local interactive wizard on supported Windows hosts; it falls back to the packaged shortcut when local launching is unavailable. Passwords are never entered in chat. Setup commands do not start triage, draft creation, or scheduling.

Select Inbox Assistant, then send:

> Start fresh with Gmail only. Verify which account is accessible in this session. If Gmail is unavailable, help me install/connect its provider plugin. Review the last seven days and show up to three emails needing my reply with proposed replies in chat. Check existing sent replies and drafts. Do not save drafts, send messages, organize mail, or create a schedule yet.

Review facts, recipients, commitments, and tone. Give edits such as “Make reply 1 shorter” or “Friday is not confirmed; say I am checking.” For an agreed reply: “Save the reviewed reply 1 as an unsent Gmail draft. Do not send.” Re-run the check and verify that it does not duplicate that draft or overwrite any draft you wrote yourself.

After initial review, supply your own cadence, timezone, and output destination. For example:

> These reviewed drafts look right. Schedule Gmail checks on weekdays at 9 AM Asia/Kolkata. Show future drafts only in this chat; do not create mailbox drafts or send anything. Confirm the created schedule and tell me how to pause it.

This is an example, not a preconfigured schedule. Verify one scheduled execution in the chosen host and then pause the test task. Do not assume a local desktop run continues while the computer or app is off.

## Then Outlook

First distinguish Microsoft-hosted Outlook mail from a hosted IMAP mailbox opened in the Outlook app. For the latter, use the IMAP setup below; installing the Microsoft Outlook connector does not establish access to a third-party mailbox.

After completing the Gmail trial, install/connect Outlook Email using your own Microsoft account. Select Inbox Assistant and send:

> Set up Outlook separately from Gmail. Verify the Outlook account accessible here. Review the last seven days and show up to three proposed replies in chat. Preserve existing drafts. Do not send, save drafts, or create a schedule yet.

Repeat review, draft-save, duplicate checks, and one scheduled-run test for Outlook before relying on it. Keep provider/account scopes separate.

## Hosted IMAP — any compatible email app

On Windows, double-click `SETUP-IMAP.cmd`. On another desktop OS, open a terminal in `plugins/inbox-assistant` and run:

```text
python server/launch.py --setup
```

Python 3.11 or later must be available as `python`. Setup installs the pinned dependencies in a local virtual environment outside the package, then asks for:

- Mailbox email address and the email app used for review.
- Incoming IMAP hostname, port, and SSL/TLS or STARTTLS.
- IMAP username and hidden password/app password.
- Server Inbox, Drafts, and optionally Sent folders, selected from the server's actual list.

Use your provider's settings. No sender-specific values are prefilled. No SMTP settings are required because this connector cannot send. Password-based IMAP is supported; OAuth-only accounts need the appropriate provider connector. Credentials go to Windows Credential Manager, macOS Keychain, or Linux Secret Service; account settings/runtime stay in the user's local application data, outside this package. Linux/macOS credential-store flows have not been exercised here.

Restart the plugin host after setup. Select Inbox Assistant and ask it to verify the IMAP account and create one self-addressed, clearly labelled unsent test draft. Confirm that it appears in your email app's Drafts after synchronization. Reads are read-only; drafts are appended as plain text. Existing drafts are never overwritten. Edit saved IMAP drafts in your email app. Reply threading and folder synchronization require a live client test.

If a draft write times out, the connector keeps a pending marker and refuses another append until the existing result is reconciled. Do not delete markers or change draft keys to force a retry. No SMTP/send, delete, move, attachment upload, or flag-update tools are exposed. Scheduled IMAP checks require the local computer/runtime to be available to the host; this is not a cloud-only connection.

If an IMAP draft is verified on the server but missing in New Outlook, first check the selected Drafts folder and use Sync. In the live test, the user confirmed the draft appeared after Settings > Accounts > the account > Manage > Repair. That recovery does not establish a universal cause or fix. Preserve unsynchronized drafts and complete authentication privately; do not reset or remove accounts as a routine step. Recheck visibility before calling the client test complete.

## Live acceptance checklist before sharing as fully tested

- Fresh recipient-style installation appears and invokes correctly in ChatGPT Work desktop and Codex.
- Missing-connection onboarding works without reusing the sender's account or collecting credentials in chat.
- Gmail and Outlook each read the correct account, find a known outstanding request, and exclude an already-answered request.
- User reviews and edits a proposed reply; saving creates an unsent draft in the correct thread with correct recipients and no duplicate.
- Existing user-written drafts remain intact, including after a second run.
- A user-chosen schedule produces one observed run in each intended host; output destination, timezone, no-send behavior, and pause control are verified.
- Connection failure is reported as an incomplete check, not an empty inbox.

Use messages you control for these checks. No external sending is needed to validate a draft-only assistant. A self-addressed Gmail test draft has been saved and read back; Outlook writes, reply threading, and scheduled executions remain pending in this preview.

## Packaging and connection references

- https://developers.openai.com/plugins/build/plugins
- https://learn.chatgpt.com/docs/build-skills
- https://learn.chatgpt.com/use-cases/manage-your-inbox

Provider actions and scheduling depend on the host and account permissions. Installing this plugin does not grant additional inbox access.

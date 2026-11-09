"""Local IMAP transport: reads and append-only drafts; no send or delete operations."""
import base64
import contextlib
import email.policy
import email.utils
import getpass
import hashlib
import imaplib
import json
import os
from pathlib import Path
import re
import ssl
import sys
from email import message_from_bytes
from email.message import EmailMessage
from datetime import date, datetime, timezone

SERVICE = 'InboxAssistant.IMAP.v1'
MAX_MESSAGE = 1024 * 1024


class MailError(Exception):
    pass


def data_dir():
    if sys.platform == 'win32':
        base = Path(os.environ['LOCALAPPDATA'])
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    return base / 'inbox-assistant'


def vault():
    # Choose an OS-backed implementation explicitly. Never fall back to plaintext.
    if sys.platform == 'win32':
        from keyring.backends.Windows import WinVaultKeyring
        return WinVaultKeyring()
    if sys.platform == 'darwin':
        from keyring.backends.macOS import Keyring
        return Keyring()
    from keyring.backends.SecretService import Keyring
    return Keyring()


def configs():
    path = data_dir() / 'accounts.json'
    return json.loads(path.read_text('utf-8')) if path.exists() else {}


def clean(value, limit=500):
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise MailError('Invalid or multiline value.')
    return value


def account(value):
    cfg = configs().get(value)
    if not cfg:
        raise MailError('Account not configured. Run the local setup wizard; never provide passwords in chat.')
    return cfg


def quoted(value):
    return '"' + clean(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


@contextlib.contextmanager
def connect(cfg, password=None):
    conn = None
    try:
        ctx = ssl.create_default_context()
        # Add maintained public CA roots without weakening system trust,
        # certificate verification, or hostname checking.
        try:
            import certifi
        except ImportError:
            pass
        else:
            ctx.load_verify_locations(cafile=certifi.where())
        host = clean(cfg['host'], 253)
        if cfg['security'] == 'ssl':
            conn = imaplib.IMAP4_SSL(host, int(cfg['port']), ssl_context=ctx, timeout=30)
        elif cfg['security'] == 'starttls':
            conn = imaplib.IMAP4(host, int(cfg['port']), timeout=30)
            conn.starttls(ssl_context=ctx)
        else:
            raise MailError('Only verified SSL/TLS or STARTTLS is supported.')
        password = password if password is not None else vault().get_password(SERVICE, cfg['credential_id'])
        if not password:
            raise MailError('Local credential is missing. Re-run setup.')
        conn.login(cfg['username'], password)
        yield conn
    finally:
        if conn:
            try:
                conn.logout()
            except Exception:
                pass


def ok(result):
    typ, values = result
    if typ != 'OK':
        raise MailError('The mail server rejected the operation; no success is confirmed.')
    return values


def display_folder(raw):
    def decode(match):
        value = match.group(1)
        return base64.b64decode(value.replace(',', '/') + '=' * (-len(value) % 4)).decode('utf-16-be') if value else '&'
    return re.sub(r'&([A-Za-z0-9+,]*)-', decode, raw)


def folders(conn):
    result = []
    for line in ok(conn.list()):
        if not isinstance(line, bytes):
            raise MailError('Server uses unsupported literal folder names; manual adapter required.')
        match = re.fullmatch(rb'\((.*?)\) (?:NIL|"(?:[^"\\]|\\.)*") (.+)', line)
        if not match:
            raise MailError('Could not safely parse the server folder list.')
        name = match[2].decode('ascii')
        if name.startswith('"') and name.endswith('"'):
            name = re.sub(r'\\(.)', r'\1', name[1:-1])
        result.append({'name': name, 'display_name': display_folder(name),
                       'flags': match[1].decode('ascii').split()})
    return result


def select(conn, cfg, folder):
    if folder not in {cfg['inbox'], cfg['drafts'], cfg.get('sent')}:
        raise MailError('Folder is outside the folders selected during local setup.')
    ok(conn.select(quoted(folder), readonly=True))
    validity = conn.response('UIDVALIDITY')[1]
    if not validity or not validity[0]:
        raise MailError('Server did not provide UIDVALIDITY; refusing unstable message identifiers.')
    return validity[0].decode('ascii')


def checked_uid(conn, cfg, folder, uid, uidvalidity):
    if not re.fullmatch(r'[1-9][0-9]*', str(uid)):
        raise MailError('Invalid UID.')
    current = select(conn, cfg, folder)
    if str(uidvalidity) != current:
        raise MailError('Folder identifiers changed. Search again before reading or drafting.')


def fetch(conn, uid):
    meta = ok(conn.uid('FETCH', str(uid), '(RFC822.SIZE)'))
    sizes = [re.search(rb'RFC822.SIZE (\d+)', x) for x in meta if isinstance(x, bytes)]
    sizes = [int(x[1]) for x in sizes if x]
    if not sizes:
        raise MailError('Message no longer exists.')
    if max(sizes) > MAX_MESSAGE:
        raise MailError('Message exceeds the 1 MiB reading limit; review it in your email client.')
    rows = ok(conn.uid('FETCH', str(uid), '(BODY.PEEK[])'))
    for item in rows:
        if isinstance(item, tuple) and isinstance(item[1], bytes):
            if len(item[1]) > MAX_MESSAGE:
                raise MailError('Message exceeds the reading limit.')
            return message_from_bytes(item[1], policy=email.policy.default)
    raise MailError('Message content was not returned.')


def describe(msg, include_body=False):
    result = {key: str(msg.get(key, '')) for key in ('From', 'To', 'Cc', 'Subject', 'Date', 'Message-ID', 'In-Reply-To', 'References')}
    if include_body:
        part = msg.get_body(preferencelist=('plain', 'html'))
        result['body'] = part.get_content() if part else ''
        result['body_type'] = part.get_content_type() if part else 'none'
        result['attachments'] = [p.get_filename() for p in msg.iter_attachments()]
    return result


def search_messages(address, folder, since, limit=20, offset=0):
    cfg = account(address)
    day = date.fromisoformat(since)
    if not 1 <= limit <= 50 or not 0 <= offset <= 10000:
        raise MailError('Use limit 1–50 and offset 0–10000.')
    criterion = day.strftime('%d-') + ('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[day.month-1]) + day.strftime('-%Y')
    with connect(cfg) as conn:
        validity = select(conn, cfg, folder)
        ids = ok(conn.uid('SEARCH', None, 'SINCE', criterion))[0].split()[::-1]
        chosen = ids[offset:offset+limit]
        results = []
        for uid in chosen:
            rows = ok(conn.uid('FETCH', uid.decode(), '(BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE MESSAGE-ID IN-REPLY-TO REFERENCES)])'))
            for row in rows:
                if isinstance(row, tuple):
                    msg = message_from_bytes(row[1], policy=email.policy.default)
                    results.append({'uid': uid.decode(), 'uidvalidity': validity, 'folder': folder, **describe(msg)})
                    break
        return {'messages': results, 'matching_count': len(ids), 'next_offset': offset+limit if offset+limit < len(ids) else None,
                'coverage': 'Headers only; read full candidate messages and inspect Sent and Drafts before deciding.'}


def read_message(address, folder, uid, uidvalidity):
    cfg = account(address)
    with connect(cfg) as conn:
        checked_uid(conn, cfg, folder, uid, uidvalidity)
        return describe(fetch(conn, uid), True)


@contextlib.contextmanager
def draft_lock(cfg):
    path = data_dir() / (hashlib.sha256(cfg['credential_id'].encode()).hexdigest() + '.draft-lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise MailError('Another draft operation is active or its lock is stale. Inspect before retrying; do not force another append.')
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()


def create_draft(address, to, subject, body, draft_key, reply_folder=None, reply_uid=None, reply_uidvalidity=None):
    cfg = account(address)
    clean(subject, 998)
    if not isinstance(body, str) or not body.strip() or len(body.encode('utf-8')) > 100000:
        raise MailError('Draft body must contain 1–100000 UTF-8 bytes.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}', draft_key):
        raise MailError('Use a stable draft_key of 8–80 letters, digits, underscores, or hyphens.')
    if not isinstance(to, list) or not 1 <= len(to) <= 20:
        raise MailError('Provide 1–20 reviewed recipient addresses.')
    for recipient in to:
        clean(recipient, 254)
        if not re.fullmatch(r'[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+', recipient):
            raise MailError('Recipients must be plain email addresses.')
    reply_values = (reply_folder, reply_uid, reply_uidvalidity)
    if any(v is not None for v in reply_values) and not all(v is not None for v in reply_values):
        raise MailError('Supply all reply identifiers or none.')
    with draft_lock(cfg), connect(cfg) as conn:
        original = None
        identity = draft_key
        if reply_uid is not None:
            checked_uid(conn, cfg, reply_folder, reply_uid, reply_uidvalidity)
            original = fetch(conn, reply_uid)
            identity = f'{reply_folder}:{reply_uidvalidity}:{reply_uid}'
        digest = hashlib.sha256((cfg['credential_id']+'|'+identity).encode()).hexdigest()
        mid = f'<{digest}@inbox-assistant.invalid>'
        pending = data_dir() / (digest + '.pending-draft')
        validity = select(conn, cfg, cfg['drafts'])
        found = ok(conn.uid('SEARCH', None, 'HEADER', 'Message-ID', quoted(mid)))[0].split()
        if found:
            pending.unlink(missing_ok=True)
            return {'status':'existing_draft_preserved', 'uid':found[0].decode(), 'uidvalidity':validity, 'folder':cfg['drafts'],
                    'message_id':mid, 'note':'No draft was written or overwritten. Read the existing draft; revisions must be made in the email client.'}
        if pending.exists():
            raise MailError(f'A previous append is unresolved for Message-ID {mid}. No new append attempted. Inspect Drafts and reconcile locally before trying again.')
        msg = EmailMessage(policy=email.policy.SMTP)
        msg['From'], msg['To'], msg['Subject'] = address, ', '.join(to), subject
        msg['Date'] = email.utils.format_datetime(datetime.now(timezone.utc))
        msg['Message-ID'] = mid
        if original:
            source_mid = str(original.get('Message-ID', ''))
            if re.fullmatch(r'<[^\s<>]+>', source_mid):
                msg['In-Reply-To'] = source_mid
                refs = re.findall(r'<[^\s<>]+>', str(original.get('References', '')))[-15:]
                msg['References'] = ' '.join(refs+[source_mid])
        msg.set_content(body)
        # Persist intent before APPEND. Even a crash or delayed server search cannot
        # turn an uncertain result into an automatic duplicate on the next run.
        with pending.open('x', encoding='utf-8') as marker:
            marker.write(mid)
            marker.flush()
            os.fsync(marker.fileno())
        try:
            ok(conn.append(quoted(cfg['drafts']), '(\\Draft)', None, msg.as_bytes()))
        except Exception:
            raise MailError(f'Draft append result is uncertain for Message-ID {mid}. Do not change the draft key or retry blindly; inspect Drafts. Local pending state blocks another append.') from None
        # APPEND is the only mailbox mutation. Re-select read-only to verify persistence.
        try:
            validity = select(conn, cfg, cfg['drafts'])
            found = ok(conn.uid('SEARCH', None, 'HEADER', 'Message-ID', quoted(mid)))[0].split()
            if not found:
                return {'status':'append_accepted_readback_pending', 'message_id':mid, 'folder':cfg['drafts'], 'note':'Do not retry blindly; verify in the client.'}
            saved = describe(fetch(conn, found[0].decode()), True)
        except Exception:
            raise MailError(f'Append accepted but readback failed for Message-ID {mid}. The local pending marker is retained. Verify in Drafts; do not retry with a new key.') from None
        pending.unlink(missing_ok=True)
        return {'status':'draft_saved_unsent', 'uid':found[0].decode(), 'uidvalidity':validity,
                'folder':cfg['drafts'], 'message_id':mid, 'saved':saved}


def choose_folder(items, label, flag, optional=False):
    choices = [x for x in items if '\\Noselect' not in x['flags']]
    for i, item in enumerate(choices, 1):
        print(f'{i}. {item["display_name"]} {"(server special folder)" if flag in item["flags"] else ""}')
    while True:
        value = input(f'Select {label} folder number'+(' (blank to skip)' if optional else '')+': ').strip()
        if not value and optional:
            return None
        if value.isdigit() and 1 <= int(value) <= len(choices):
            selected = choices[int(value)-1]
            if flag == '\\Drafts' and flag not in selected['flags'] and any(flag in x['flags'] for x in choices):
                print('Warning: this is not the folder the server identifies as Drafts. Check the highlighted server Drafts folder.')
                if input('To intentionally use this custom folder, type use custom folder (otherwise choose again): ').strip() != 'use custom folder':
                    continue
            return selected['name']
        print('Choose a listed folder number.')


def setup():
    if not sys.stdin.isatty():
        raise MailError('Setup needs an interactive terminal for hidden password entry. Run it yourself, not through chat tools.')
    print('Inbox Assistant local IMAP setup. Passwords stay in your OS credential store. Nothing will be sent.')
    address = clean(input('Mailbox email address: ').strip(), 254)
    if not re.fullmatch(r'[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+', address):
        raise MailError('Enter a valid mailbox address.')
    client = clean(input('Email app used for review (e.g. New Outlook, Apple Mail, Thunderbird): ').strip())
    host = clean(input('IMAP server hostname (no URL): ').strip(), 253)
    if not re.fullmatch(r'[A-Za-z0-9.-]+', host) or '..' in host:
        raise MailError('Enter the hostname supplied by your mail provider.')
    security = input('Security [ssl/starttls] (default ssl): ').strip().lower() or 'ssl'
    if security not in ('ssl', 'starttls'):
        raise MailError('Unencrypted IMAP is not supported.')
    port = int(input(f'IMAP port (default {993 if security == "ssl" else 143}): ').strip() or (993 if security == 'ssl' else 143))
    if not 1 <= port <= 65535:
        raise MailError('Invalid port.')
    username = clean(input('IMAP username (blank = email address): ').strip() or address)
    password = getpass.getpass('Mailbox password/app password (hidden, never paste into chat): ')
    credential_id = hashlib.sha256((host+'|'+str(port)+'|'+username).encode()).hexdigest()
    cfg = dict(host=host, port=port, security=security, username=username, client=client, credential_id=credential_id)
    with connect(cfg, password) as conn:
        items = folders(conn)
        cfg['inbox'] = choose_folder(items, 'Inbox', '\\Inbox')
        cfg['drafts'] = choose_folder(items, 'Drafts used by your email app', '\\Drafts')
        cfg['sent'] = choose_folder(items, 'Sent', '\\Sent', optional=True)
        if cfg['drafts'] in (cfg['inbox'], cfg['sent']):
            raise MailError('Drafts must be distinct from Inbox and Sent.')
        for folder in (cfg['inbox'], cfg['drafts'], cfg['sent']):
            if folder:
                select(conn, cfg, folder)
    existing = configs()
    if address in existing and input('Replace this account configuration? Type yes: ').strip() != 'yes':
        print('Existing configuration kept.')
        return
    vault().set_password(SERVICE, credential_id, password)
    existing[address] = cfg
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = directory / 'accounts.json.tmp'
    temp.write_text(json.dumps(existing, indent=2)+'\n', encoding='utf-8')
    try:
        temp.chmod(0o600)
    except OSError:
        pass
    temp.replace(directory / 'accounts.json')
    print('Connection verified and saved locally. No draft created. Restart the plugin host, then request an unsent test draft and check it in your email app.')


if __name__ == '__main__':
    try:
        setup()
    except (Exception, KeyboardInterrupt):
        print('Setup did not complete. Check server, TLS, login, selected folders, and OS credential-store access. No password or server error was logged.', file=sys.stderr)
        sys.exit(1)

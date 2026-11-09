import contextlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import io
from unittest.mock import patch
from email import message_from_bytes
import email.policy

source = Path(__file__).resolve().parent
if not (source/'imap_transport.py').exists():
    source = source.parent/'plugins/inbox-assistant/server'
sys.path.insert(0, str(source))
import imap_transport as m

CFG = dict(host='imap.example.com', port=993, security='ssl', username='person@example.com',
           credential_id='test-key', inbox='INBOX', drafts='Drafts', sent='Sent', client='Any mail app')


class FakeIMAP:
    def __init__(self):
        self.events = []
        self.saved = {}
        self.append_count = 0
        self.timeout_after_append = False
        self.folder = None

    def select(self, folder, readonly=False):
        self.events.append(('select', folder, readonly))
        self.folder = folder.strip('"')
        return 'OK', [b'1']

    def list(self):
        return 'OK', [b'(\\HasNoChildren) "/" "INBOX"', b'(\\Drafts) "/" "Drafts"', b'(\\Sent) "/" "Sent"']

    def response(self, key):
        return key, [b'123']

    def uid(self, op, *args):
        self.events.append((op, args))
        if op == 'SEARCH':
            if 'HEADER' in args:
                mid = args[-1].strip('"')
                ids = [str(k).encode() for k,v in self.saved.items() if mid.encode() in v]
                return 'OK', [b' '.join(ids)]
            return 'OK', [b'1 2 3']
        if op == 'FETCH':
            uid, query = args
            raw = self.saved.get(int(uid), b'From: sender@example.com\r\nTo: person@example.com\r\nSubject: Request\r\nMessage-ID: <original@example.com>\r\n\r\nPlease review.')
            if query == '(RFC822.SIZE)':
                return 'OK', [f'1 (RFC822.SIZE {len(raw)})'.encode()]
            return 'OK', [(b'1 (BODY[] {100}', raw), b')']
        raise AssertionError(op)

    def append(self, folder, flags, date, raw):
        self.events.append(('append', folder, flags))
        self.append_count += 1
        self.saved[self.append_count] = raw
        if self.timeout_after_append:
            raise TimeoutError('server detail and secret must not leak')
        return 'OK', [b'APPEND complete']


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.imap = FakeIMAP()
        self.patches = [patch.object(m, 'data_dir', return_value=Path(self.tmp.name)),
                        patch.object(m, 'account', return_value=CFG),
                        patch.object(m, 'connect', return_value=contextlib.nullcontext(self.imap))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def draft(self, **kw):
        values = dict(address='person@example.com', to=['person@example.com'], subject='Test', body='A test draft.', draft_key='stable-key-001')
        values.update(kw)
        return m.create_draft(**values)

    def test_draft_saved_readback_and_idempotency(self):
        first = self.draft()
        second = self.draft()
        self.assertEqual(first['status'], 'draft_saved_unsent')
        self.assertEqual(second['status'], 'existing_draft_preserved')
        self.assertEqual(self.imap.append_count, 1)
        self.assertEqual(first['saved']['To'], 'person@example.com')
        self.assertEqual(first['saved']['body'].strip(), 'A test draft.')
        self.assertIn(('append', '"Drafts"', '(\\Draft)'), self.imap.events)

    def test_revisions_preserve_existing_draft(self):
        self.draft()
        result = self.draft(body='A changed version.')
        self.assertEqual(result['status'], 'existing_draft_preserved')
        self.assertEqual(self.imap.append_count, 1)

    def test_append_timeout_recheck_does_not_duplicate(self):
        self.imap.timeout_after_append = True
        with self.assertRaises(m.MailError):
            self.draft()
        self.imap.timeout_after_append = False
        self.assertEqual(self.draft()['status'], 'existing_draft_preserved')
        self.assertEqual(self.imap.append_count, 1)

    def test_uncertain_append_blocks_retry_when_search_is_delayed(self):
        self.imap.timeout_after_append = True
        with self.assertRaises(m.MailError) as exc:
            self.draft()
        self.assertIn('@inbox-assistant.invalid>', str(exc.exception))
        self.imap.saved.clear()  # Simulate a delayed server index, not a rejected append.
        self.imap.timeout_after_append = False
        with self.assertRaises(m.MailError):
            self.draft()
        self.assertEqual(self.imap.append_count, 1)

    def test_readonly_peek(self):
        m.read_message('person@example.com', 'INBOX', '1', '123')
        self.assertIn(('select', '"INBOX"', True), self.imap.events)
        self.assertTrue(any(x[0]=='FETCH' and 'BODY.PEEK[]' in x[1][-1] for x in self.imap.events))
        self.assertFalse(any(x[0] in ('STORE','EXPUNGE','COPY','MOVE','append') for x in self.imap.events))

    def test_stale_uidvalidity_rejected(self):
        with self.assertRaises(m.MailError):
            m.read_message('person@example.com', 'INBOX', '1', '999')
        self.assertFalse(any(x[0]=='FETCH' for x in self.imap.events))

    def test_reply_headers_and_key_bound_to_source(self):
        self.draft(reply_folder='INBOX', reply_uid='2', reply_uidvalidity='123')
        raw = next(iter(self.imap.saved.values()))
        msg = message_from_bytes(raw, policy=email.policy.default)
        self.assertEqual(msg['In-Reply-To'], '<original@example.com>')
        self.assertIn('<original@example.com>', msg['References'])
        self.draft(draft_key='different-key', reply_folder='INBOX', reply_uid='2', reply_uidvalidity='123')
        self.assertEqual(self.imap.append_count, 1)

    def test_injection_and_folder_scope(self):
        with self.assertRaises(m.MailError):
            self.draft(subject='Hello\r\nBcc: attacker@example.com')
        with self.assertRaises(m.MailError):
            self.draft(to=['person@example.com\nBcc: attacker@example.com'])
        with self.assertRaises(m.MailError):
            m.read_message('person@example.com', 'Unselected', '1', '123')
        self.assertEqual(self.imap.append_count, 0)

    def test_pagination_reports_remaining(self):
        result = m.search_messages('person@example.com', 'INBOX', '2026-11-01', 2)
        self.assertEqual(result['next_offset'], 2)
        self.assertEqual(result['matching_count'], 3)
        self.assertEqual([x['uid'] for x in result['messages']], ['3','2'])

    def test_concurrent_lock_refuses_second_append(self):
        with m.draft_lock(CFG):
            with self.assertRaises(m.MailError):
                self.draft()
        self.assertEqual(self.imap.append_count, 0)

    def test_tls_verified_before_login(self):
        events=[]
        class Conn:
            def __init__(self, *args, **kwargs):
                events.append('connect')
            def starttls(self, ssl_context):
                events.append('tls')
                self.context=ssl_context
            def login(self, *args): events.append('login')
            def logout(self): events.append('logout')
        self.patches[-1].stop()
        with patch.object(m.imaplib, 'IMAP4', Conn):
            with m.connect({**CFG, 'security':'starttls'}, 'synthetic-secret'):
                pass
        self.assertEqual(events, ['connect','tls','login','logout'])
        self.patches[-1].start()

    def test_setup_prompts_and_keeps_password_out_of_config_and_output(self):
        answers = ['person@example.com','Thunderbird','imap.example.com','ssl','','', '1','2','3']
        output = io.StringIO()
        with patch('builtins.input', side_effect=answers) as prompt, \
             patch.object(m.sys.stdin, 'isatty', return_value=True), \
             patch.object(m.getpass, 'getpass', return_value='synthetic-only-secret'), \
             patch.object(m, 'configs', return_value={}), \
             patch.object(m, 'vault') as store, contextlib.redirect_stdout(output):
            m.setup()
        cfg_path = Path(self.tmp.name)/'accounts.json'
        self.assertNotIn('synthetic-only-secret', cfg_path.read_text())
        self.assertNotIn('synthetic-only-secret', output.getvalue())
        self.assertEqual(store.return_value.set_password.call_args.args[-1], 'synthetic-only-secret')
        prompts = ' '.join(call.args[0] for call in prompt.call_args_list)
        for text in ('Mailbox email', 'Email app', 'hostname', 'Security', 'port', 'username', 'Drafts', 'Sent'):
            self.assertIn(text, prompts)

    def test_wrong_drafts_selection_warns_before_custom_override(self):
        choices = [{'name':'INBOX.Junk', 'display_name':'INBOX.Junk', 'flags':[]},
                   {'name':'INBOX.Drafts', 'display_name':'INBOX.Drafts', 'flags':['\\Drafts']}]
        with patch('builtins.input', side_effect=['1','','2']), contextlib.redirect_stdout(io.StringIO()):
            chosen = m.choose_folder(choices, 'Drafts', '\\Drafts')
        self.assertEqual(chosen, 'INBOX.Drafts')


if __name__ == '__main__':
    unittest.main()

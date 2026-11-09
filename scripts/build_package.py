"""Build the distributable plugin marketplace from public source files only."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'outputs'
PREFIX = Path('inbox-assistant-package')


def source_files():
    files = [ROOT / name for name in (
        '.agents/plugins/marketplace.json', 'README.md', 'START-HERE.md',
        'SETUP-IMAP.cmd', 'TEST-STATUS.md', 'SYNTHETIC-TESTS.md', 'tests/test_imap.py',
        'scripts/build_package.py')]
    files.extend(path for path in (ROOT / 'plugins/inbox-assistant').rglob('*')
                 if path.is_file() and '__pycache__' not in path.parts
                 and path.suffix not in ('.pyc', '.pyo'))
    return sorted(set(files))


def main():
    version = json.loads((ROOT / 'plugins/inbox-assistant/plugin.json').read_text('utf-8'))['version']
    OUTPUT.mkdir(exist_ok=True)
    archive = OUTPUT / 'inbox-assistant-preview.zip'
    files = source_files()
    for path in files:
        relative = path.relative_to(ROOT)
        if not path.is_file() or path.is_symlink() or '..' in relative.parts:
            raise RuntimeError(f'Unsafe or missing source: {relative}')
        if path.name in {'accounts.json', '.env', 'automation.toml'} or path.suffix in {'.key', '.pem', '.eml', '.log'}:
            raise RuntimeError(f'Local data is not distributable: {relative}')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        for path in files:
            output.write(path, PREFIX / path.relative_to(ROOT))
    with zipfile.ZipFile(archive) as output:
        assert output.testzip() is None
        assert len(output.namelist()) == len(files)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (OUTPUT / 'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    print(f'Built v{version}: {archive} ({len(files)} files)')
    print(f'SHA256: {digest}')


if __name__ == '__main__':
    main()

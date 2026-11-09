"""Dependency bootstrap and MCP launcher; runtime and secrets never live in the package."""
import os
from pathlib import Path
import subprocess
import sys
import venv


def main():
    if sys.version_info < (3, 11):
        raise RuntimeError('Python 3.11 or later is required.')
    directory = Path(__file__).resolve().parent
    base = Path(os.environ['LOCALAPPDATA']) if sys.platform == 'win32' else Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))
    runtime = base / 'inbox-assistant/runtime-v1'
    interpreter = runtime / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if '--setup' in sys.argv:
        if not sys.stdin.isatty():
            raise RuntimeError('Setup requires your own interactive terminal; never pass a password through chat.')
        if not interpreter.exists():
            venv.EnvBuilder(with_pip=True).create(runtime)
        subprocess.run([str(interpreter), '-m', 'pip', 'install', '-r', str(directory/'requirements.txt')], check=True)
        subprocess.run([str(interpreter), str(directory/'imap_transport.py')], check=True)
    else:
        if not interpreter.exists():
            raise RuntimeError('Run python server/launch.py --setup locally, then restart the plugin host.')
        # All MCP traffic remains newline-delimited stdio via the official SDK.
        raise SystemExit(subprocess.call([str(interpreter), str(directory/'server.py')]))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Inbox Assistant IMAP runtime unavailable. Run python server/launch.py --setup in your own terminal. Python 3.11+, package installation access, and an unlocked OS credential store are required.', file=sys.stderr)
        sys.exit(1)

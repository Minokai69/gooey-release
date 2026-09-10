#!/usr/bin/env python3
"""Verify built source deployment in a fresh profile; never load desktop code."""
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)


def main():
    with tempfile.TemporaryDirectory(prefix='gooey-clean-install-') as temporary:
        home = Path(temporary) / 'new user'
        config = home / '.config/omarchy/shell.json'
        config.parent.mkdir(parents=True)
        initial = {'version': 1, 'bar': {'layout': {'left': [{'id': 'omarchy.menu'}],
                   'center': [{'id': 'omarchy.clock'}], 'right': []}}, 'plugins': [],
                   'idle': {'lock': 600}}
        config.write_text(json.dumps(initial))
        hypr = home / '.config/hypr/hyprland.lua'
        hypr.parent.mkdir(parents=True)
        hypr.write_text('-- Fresh user configuration\n')
        for _ in range(2):
            run(ROOT / 'session/gooey-session', '--home', home, 'deploy')
            assert json.loads(config.read_text()) == initial
            assert hypr.read_text() == '-- Fresh user configuration\n'
            assert not (home / '.local/share/gooey/activation.json').exists()
            assert (home / '.local/bin/gooey').is_file()
        data = home / '.local/share/gooey'
        version = json.loads((data / 'staged.json').read_text())['version']
        release = data / 'releases' / version
        assert (release / 'companion/gooey.so').is_file()
        assert (release / 'LICENSE-COMPANION').is_file()
        for plugin in ('gooey.launcher', 'gooey.window-tools'):
            assert (release / 'plugins' / plugin / 'manifest.json').is_file()
        run(ROOT / 'gooey', 'activate', '--home', home)
        changed = json.loads(config.read_text())
        changed['idle']['lock'] = 900
        config.write_text(json.dumps(changed))
        run(ROOT / 'gooey', 'restore', '--home', home)
        initial['idle']['lock'] = 900
        assert json.loads(config.read_text()) == initial
        run(ROOT / 'gooey', 'uninstall', '--home', home)
        assert json.loads(config.read_text()) == initial
        assert not (data / 'releases').exists() or not list((data / 'releases').iterdir())
        assert hypr.read_text() == '-- Fresh user configuration\n'
        # The independent recovery command and backups are deliberately retained.
        assert (home / '.local/bin/gooey').is_file()
    print('PASS: fresh-profile deploy, repeat deploy, selection, restoration, and payload removal; paths with spaces supported.')


if __name__ == '__main__':
    main()

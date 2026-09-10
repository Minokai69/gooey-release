"""Installer sequencing and recovery, with no access to the actual desktop."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('gooey_installer', str(ROOT / 'install'))
spec = importlib.util.spec_from_loader(loader.name, loader)
installer = importlib.util.module_from_spec(spec)
loader.exec_module(installer)


class Installer(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'new user'
        self.home.mkdir()
        self.data = self.home / '.local/share/gooey'
        self.check = self.enterContext(mock.patch.object(installer, 'check'))
        self.run = self.enterContext(mock.patch.object(installer, 'run'))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def active(self):
        self.data.mkdir(parents=True)
        (self.data / 'activation.json').write_text('{}')
        (self.data / 'current').symlink_to('releases/0.1.0-dev-123456abcdef')

    def test_incompatible_host_never_builds_or_deploys(self):
        self.check.side_effect = RuntimeError('unsupported host')
        with self.assertRaisesRegex(RuntimeError, 'unsupported'):
            installer.install(self.home, True)
        self.run.assert_not_called()
        self.assertEqual(list(self.home.iterdir()), [])

    def test_fresh_install_only_stages_by_default(self):
        installer.install(self.home)
        calls = [call.args for call in self.run.call_args_list]
        self.assertEqual(calls[-1], ('./session/gooey-session', 'deploy'))
        self.assertNotIn('enable', [arg for call in calls for arg in call])
        self.assertIn(('./dev/run', 'integration-headless'), calls)

    def test_fresh_install_activation_follows_tests_and_preflight(self):
        installer.install(self.home, True)
        calls = [call.args for call in self.run.call_args_list]
        command = self.home / '.local/bin/gooey'
        self.assertEqual(calls[-3:], [('./session/gooey-session', 'deploy'),
                                     (command, 'enable', '--check'), (command, 'enable')])

    def test_active_install_requires_explicit_switch(self):
        self.active()
        with self.assertRaisesRegex(RuntimeError, '--enable'):
            installer.install(self.home)
        self.run.assert_not_called()

    def test_validation_failure_leaves_active_desktop_untouched(self):
        self.active()
        def fail(*args):
            if args == ('./dev/run', 'integration-headless'):
                raise subprocess.CalledProcessError(1, args)
        self.run.side_effect = fail
        with self.assertRaises(subprocess.CalledProcessError):
            installer.install(self.home, True)
        calls = [call.args for call in self.run.call_args_list]
        self.assertFalse(any('disable' in call or 'deploy' in call for call in calls))
        self.assertTrue((self.data / 'activation.json').exists())

    def test_update_disables_only_after_validation(self):
        self.active()
        installer.install(self.home, True)
        calls = [call.args for call in self.run.call_args_list]
        self.assertLess(calls.index(('./dev/run', 'integration-headless')),
                        calls.index((self.home / '.local/bin/gooey', 'disable')))

    def test_failed_enable_restores_old_release(self):
        self.active()
        enables = 0
        def fail(*args):
            nonlocal enables
            if args == (self.home / '.local/bin/gooey', 'enable'):
                enables += 1
                if enables == 1:
                    raise subprocess.CalledProcessError(1, args)
        self.run.side_effect = fail
        with self.assertRaises(subprocess.CalledProcessError):
            installer.install(self.home, True)
        self.assertEqual(enables, 2)
        self.assertEqual(json.loads((self.data / 'staged.json').read_text()),
                         {'version': '0.1.0-dev-123456abcdef'})

    def test_failed_disable_does_not_deploy(self):
        self.active()
        def fail(*args):
            if 'disable' in args:
                raise subprocess.CalledProcessError(1, args)
        self.run.side_effect = fail
        with self.assertRaises(subprocess.CalledProcessError):
            installer.install(self.home, True)
        self.assertNotIn(mock.call('./session/gooey-session', 'deploy'), self.run.call_args_list)

    def test_failed_fresh_install_does_not_attempt_old_release_recovery(self):
        def fail(*args):
            if 'deploy' in args:
                raise subprocess.CalledProcessError(1, args)
        self.run.side_effect = fail
        with self.assertRaises(subprocess.CalledProcessError):
            installer.install(self.home, True)
        self.assertFalse((self.data / 'staged.json').exists())


class Readiness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        for name, content in (('.config/omarchy/shell.json', '{"version":1}'),
                              ('.config/hypr/hyprland.lua', '-- user')):
            path = self.home / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        (self.root / 'HOST.json').write_text(json.dumps({'package': 'omarchy test',
                                                      'quickshell': 'qs test', 'files': {}}))
        pin = self.root / 'companions/hyprland/PIN.json'
        pin.parent.mkdir(parents=True)
        pin.write_text(json.dumps({'hyprlandVersion': 'test', 'hyprlandCommit': 'commit'}))
        header = self.root / 'version.h'
        header.write_text('#define GIT_COMMIT_HASH "commit"')
        self.enterContext(mock.patch.object(installer, 'ROOT', self.root))
        self.enterContext(mock.patch.object(installer, 'HEADER', header))
        self.enterContext(mock.patch.object(installer.os, 'geteuid', return_value=1000))
        self.which = self.enterContext(mock.patch.object(installer.shutil, 'which', return_value='/usr/bin/tool'))
        self.enterContext(mock.patch.dict(installer.os.environ,
                          {'HYPRLAND_INSTANCE_SIGNATURE': 'test', 'WAYLAND_DISPLAY': 'wayland-test'}))
        self.responses = {('pacman', '-Q', 'omarchy'): 'omarchy test',
                          ('quickshell', '--version'): 'qs test',
                          ('pkg-config', '--modversion', 'hyprland'): 'test',
                          ('hyprctl', '-j', 'version'): '{"version":"test","commit":"commit"}',
                          ('hyprctl', 'configerrors'): ''}
        self.enterContext(mock.patch.object(installer, 'output',
                          side_effect=lambda *args: self.responses.get(args, '')))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def snapshot(self):
        return {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_successful_check_writes_nothing(self):
        before = self.snapshot()
        installer.check(self.home)
        self.assertEqual(self.snapshot(), before)

    def test_reports_multiple_mismatches_without_changes(self):
        self.responses[('pacman', '-Q', 'omarchy')] = 'omarchy other'
        self.responses[('quickshell', '--version')] = 'qs other'
        before = self.snapshot()
        with self.assertRaises(RuntimeError) as result:
            installer.check(self.home)
        self.assertIn('Omarchy:', str(result.exception))
        self.assertIn('Quickshell:', str(result.exception))
        self.assertEqual(self.snapshot(), before)

    def test_missing_dependencies_are_named(self):
        self.which.side_effect = lambda tool: None if tool in ('c++', 'bwrap') else '/usr/bin/tool'
        with self.assertRaisesRegex(RuntimeError, r'Missing commands: c\+\+, bwrap'):
            installer.check(self.home)

    def test_running_compositor_must_match_headers(self):
        self.responses[('hyprctl', '-j', 'version')] = '{"version":"test","commit":"old"}'
        with self.assertRaisesRegex(RuntimeError, 'running Hyprland'):
            installer.check(self.home)


if __name__ == '__main__':
    unittest.main()

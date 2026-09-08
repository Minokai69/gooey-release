"""Behavior tests for private-home release staging and restoring user state."""
import copy
import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('gooey_cli', str(REPO / 'gooey'))
spec = importlib.util.spec_from_loader(loader.name, loader)
cli = importlib.util.module_from_spec(spec)
loader.exec_module(cli)


class Packaging(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gooey-package-')
        self.root = Path(self.temp.name) / 'source'
        self.home = Path(self.temp.name) / 'private home'
        self.home.mkdir()
        for plugin_id in cli.IDS:
            folder = self.root / 'experience/plugins' / plugin_id
            folder.mkdir(parents=True)
            (folder / 'manifest.json').write_text(json.dumps({'id': plugin_id, 'entryPoints': {'panel': 'Main.qml'}}))
            (folder / 'Main.qml').write_text('import QtQuick\nItem {}\n')
        build = self.root / 'companions/hyprland/build'
        build.mkdir(parents=True)
        (build / 'gooey.so').write_bytes(b'packaging fixture, never executed')
        (build / 'build-info.json').write_text(json.dumps({'hyprland': 'test', 'sha256': hashlib.sha256((build / 'gooey.so').read_bytes()).hexdigest()}))
        (self.root / 'LICENSE').write_text('test')
        cli.ROOT = self.root
        self.config_path = self.home / '.config/omarchy/shell.json'
        self.initial = {'version': 1, 'bar': {'position': 'bottom', 'layout': {'left': [{'id': 'omarchy.menu', 'custom': 7}, {'id': 'mine.clock'}], 'center': [], 'right': []}}, 'plugins': [{'id': 'mine.service'}], 'idle': {'lock': 500}}
        cli.atomic_json(self.config_path, self.initial)

    def tearDown(self):
        cli.ROOT = REPO
        self.temp.cleanup()

    def test_install_is_inactive_and_restore_preserves_later_edits(self):
        cli.install(self.home)
        self.assertEqual(cli.read(self.config_path), self.initial)
        cli.activate(self.home)
        config = cli.read(self.config_path)
        config['bar']['position'] = 'left'
        config['idle']['lock'] = 900
        config['bar']['layout']['right'].append({'id': 'mine.new'})
        cli.atomic_json(self.config_path, config)
        cli.restore(self.home)
        restored = cli.read(self.config_path)
        self.assertEqual(restored['bar']['position'], 'left')
        self.assertEqual(restored['idle']['lock'], 900)
        self.assertEqual(restored['bar']['layout']['left'], self.initial['bar']['layout']['left'])
        self.assertEqual(restored['bar']['layout']['right'], [{'id': 'mine.new'}])
        self.assertEqual(restored['plugins'], self.initial['plugins'])

    def test_stage_then_rollback_keeps_releases_independent(self):
        cli.install(self.home)
        cli.activate(self.home)
        data, _ = cli.locations(self.home)
        original = (data / 'current').resolve()
        file = self.root / 'experience/plugins/gooey.launcher/Main.qml'
        file.write_text(file.read_text() + '// another release\n')
        cli.install(self.home)
        self.assertEqual((data / 'current').resolve(), original)
        cli.activate(self.home)
        updated = (data / 'current').resolve()
        self.assertNotEqual(updated, original)
        cli.activate(self.home)  # idempotent selection must not destroy rollback
        self.assertEqual((data / 'previous').resolve(), original)
        cli.rollback(self.home)
        self.assertEqual((data / 'current').resolve(), original)

    def test_refuses_to_overwrite_other_plugin_directory(self):
        folder = self.home / '.config/omarchy/plugins/gooey.launcher'
        folder.mkdir(parents=True)
        (folder / 'keep.txt').write_text('user content')
        cli.install(self.home)
        with self.assertRaises(RuntimeError):
            cli.activate(self.home)
        self.assertEqual((folder / 'keep.txt').read_text(), 'user content')
        self.assertEqual(cli.read(self.config_path), self.initial)

    def test_uninstall_preserves_unowned_files(self):
        cli.install(self.home)
        cli.activate(self.home)
        data, _ = cli.locations(self.home)
        (data / 'notes.txt').write_text('keep')
        cli.uninstall(self.home)
        self.assertEqual(cli.read(self.config_path), self.initial)
        self.assertEqual((data / 'notes.txt').read_text(), 'keep')
        self.assertFalse((self.home / '.config/omarchy/plugins/gooey.launcher').exists())

    def profile_snapshot(self):
        return {str(p.relative_to(self.home)): ('link', p.readlink().as_posix()) if p.is_symlink() else ('file', p.read_bytes())
                for p in self.home.rglob('*') if p.is_symlink() or p.is_file()}

    def test_malformed_config_does_not_partially_activate(self):
        cli.install(self.home)
        for invalid in ({'version': 1, 'bar': {'layout': {'left': ['omarchy.menu']}}},
                        {'version': 1, 'bar': []}, {'version': 1, 'plugins': {}}):
            with self.subTest(config=invalid):
                cli.atomic_json(self.config_path, invalid)
                before = self.profile_snapshot()
                with self.assertRaises(RuntimeError):
                    cli.activate(self.home)
                self.assertEqual(self.profile_snapshot(), before)

    def test_config_write_failure_rolls_back_first_activation(self):
        cli.install(self.home)
        before = self.profile_snapshot()
        real_write = cli.atomic_json

        def failing_write(path, value):
            if path == self.config_path:
                raise OSError('simulated config write failure')
            return real_write(path, value)

        with mock.patch.object(cli, 'atomic_json', side_effect=failing_write):
            with self.assertRaises(OSError):
                cli.activate(self.home)
        self.assertEqual(self.profile_snapshot(), before)

    def test_config_write_failure_rolls_back_release_update(self):
        cli.install(self.home)
        cli.activate(self.home)
        file = self.root / 'experience/plugins/gooey.launcher/Main.qml'
        file.write_text(file.read_text() + '// updated\n')
        cli.install(self.home)
        before = self.profile_snapshot()
        real_write = cli.atomic_json

        def failing_write(path, value):
            if path == self.config_path:
                raise OSError('simulated config write failure')
            return real_write(path, value)

        with mock.patch.object(cli, 'atomic_json', side_effect=failing_write):
            with self.assertRaises(OSError):
                cli.activate(self.home)
        self.assertEqual(self.profile_snapshot(), before)

    def test_restore_preserves_preexisting_gooey_entries(self):
        config = copy.deepcopy(self.initial)
        config['bar']['layout']['right'] = [{'id': 'gooey.launcher', 'custom': 8}, {'id': 'gooey.window-tools'}]
        config['plugins'] += [{'id': 'gooey.launcher', 'custom': 9}, {'id': 'gooey.window-tools'}]
        cli.atomic_json(self.config_path, config)
        cli.install(self.home)
        cli.activate(self.home)
        cli.restore(self.home)
        self.assertEqual(cli.read(self.config_path), config)

    def test_restore_preserves_subsequently_edited_owned_entries(self):
        cli.install(self.home)
        cli.activate(self.home)
        edited = cli.read(self.config_path)
        edited['bar']['layout']['left'][0]['customAfterActivation'] = 'keep'
        next(e for e in edited['plugins'] if e['id'] == 'gooey.window-tools')['custom'] = 42
        cli.atomic_json(self.config_path, edited)
        cli.activate(self.home)  # Re-selecting must not adopt user edits as owned.
        cli.restore(self.home)
        restored = cli.read(self.config_path)
        self.assertIn({'id': 'gooey.launcher', 'customAfterActivation': 'keep'}, restored['bar']['layout']['left'])
        self.assertIn({'id': 'gooey.window-tools', 'custom': 42}, restored['plugins'])
        self.assertNotIn({'id': 'gooey.window-tools'}, restored['bar']['layout']['left'])

    def test_incomplete_existing_release_is_not_reused_or_activated(self):
        cli.install(self.home)
        data, _ = cli.locations(self.home)
        version = cli.read(data / 'staged.json')['version']
        (data / 'releases' / version / 'plugins/gooey.launcher/Main.qml').unlink()
        before = self.profile_snapshot()
        with self.assertRaisesRegex(RuntimeError, 'file set'):
            cli.install(self.home)
        with self.assertRaisesRegex(RuntimeError, 'file set'):
            cli.activate(self.home)
        self.assertEqual(self.profile_snapshot(), before)

    def test_modified_release_content_is_rejected(self):
        cli.install(self.home)
        data, _ = cli.locations(self.home)
        version = cli.read(data / 'staged.json')['version']
        (data / 'releases' / version / 'plugins/gooey.launcher/Main.qml').write_text('changed')
        before = self.profile_snapshot()
        with self.assertRaisesRegex(RuntimeError, 'integrity'):
            cli.activate(self.home)
        self.assertEqual(self.profile_snapshot(), before)

    def test_uninstall_keeps_dependencies_of_preserved_edited_entries(self):
        cli.install(self.home)
        cli.activate(self.home)
        config = cli.read(self.config_path)
        config['bar']['layout']['left'][0]['custom'] = 'keep'
        cli.atomic_json(self.config_path, config)
        cli.uninstall(self.home)
        self.assertIn({'id': 'gooey.launcher', 'custom': 'keep'}, cli.read(self.config_path)['bar']['layout']['left'])
        self.assertTrue((self.home / '.config/omarchy/plugins/gooey.launcher/Menu.qml').exists()
                        or (self.home / '.config/omarchy/plugins/gooey.launcher/Main.qml').exists())


if __name__ == '__main__':
    unittest.main()

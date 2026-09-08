"""Session safety contracts using temporary homes and mocked desktop IPC only."""
import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('gooey_session_tests', str(REPO / 'session/gooey-session'))
spec = importlib.util.spec_from_loader(loader.name, loader)
session = importlib.util.module_from_spec(spec)
loader.exec_module(session)


class SessionSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gooey-session-test-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'private home'
        self.source = Path(self.temp.name) / 'source'
        self.home.mkdir()
        # A missed mock is a test failure, never an accidental desktop operation.
        self.run = self.enterContext(mock.patch.object(session, 'run', side_effect=AssertionError('Unmocked desktop IPC')))
        self.enterContext(mock.patch.dict(session.os.environ, {'HYPRLAND_INSTANCE_SIGNATURE': 'test-instance'}))
        self.output = self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.data, self.main, self.module = session.paths(self.home)
        self.initial_main = '-- Personal config\nrequire("hypr.bindings")\n'
        session.write(self.main, self.initial_main, 0o644)
        self.config_path = self.home / '.config/omarchy/shell.json'
        self.initial_config = {'version': 1, 'bar': {'position': 'bottom', 'layout': {
            'left': [{'id': 'omarchy.menu', 'custom': 7}], 'center': [], 'right': [{'id': 'mine.power'}]}},
            'plugins': [{'id': 'mine.service'}], 'idle': {'lock': 900}}
        session.CORE['atomic_json'](self.config_path, self.initial_config)

    def stage_fixture(self):
        for plugin_id in session.CORE['IDS']:
            folder = self.source / 'experience/plugins' / plugin_id
            folder.mkdir(parents=True)
            (folder / 'manifest.json').write_text(json.dumps({'id': plugin_id, 'entryPoints': {'panel': 'Main.qml'}}))
            (folder / 'Main.qml').write_text('import QtQuick\nItem {}\n')
        build = self.source / 'companions/hyprland/build'
        build.mkdir(parents=True)
        binary = b'fixture only; never executed'
        (build / 'gooey.so').write_bytes(binary)
        self.build_info = {'hyprlandCommit': 'tested-commit', 'hyprlandVersion': 'test-version',
                           'sha256': hashlib.sha256(binary).hexdigest()}
        (build / 'build-info.json').write_text(json.dumps(self.build_info))
        (self.source / 'LICENSE').write_text('test fixture')
        with mock.patch.dict(session.CORE['install'].__globals__, {'ROOT': self.source}):
            session.CORE['install'](self.home)
        self.release = session.selected_release(self.home, staged=True)
        session.CORE['atomic_json'](self.data / 'runtime/compatibility.json', {
            'package': 'omarchy test', 'quickshell': 'quickshell test', 'files': {}})
        return self.release

    def preflight_mocks(self, loaded):
        self.enterContext(mock.patch.object(session, 'context'))
        self.enterContext(mock.patch.object(session, 'unlocked'))
        self.enterContext(mock.patch.object(session, 'compatible', return_value={'version': 'test-version'}))
        self.enterContext(mock.patch.object(session, 'plugin_list', return_value=loaded))

    def test_startup_block_round_trip_preserves_user_configuration(self):
        added = session.add_block(self.initial_main)
        self.assertEqual(session.add_block(added), added)
        self.assertEqual(session.remove_block(added), self.initial_main)
        later = added + '-- An unrelated later edit\n'
        self.assertEqual(session.remove_block(later), self.initial_main + '-- An unrelated later edit\n')

    def test_readiness_waits_for_native_and_ui_theme_acknowledgement(self):
        for mode, native_ready, ui_synced in ((mode, native, ui) for mode in ('corner-tab', 'centered-strip', 'full-width-strip', 'integrated-frame')
                                            for native, ui in ((False, False), (True, False), (False, True))):
            with self.subTest(mode=mode, native_ready=native_ready, ui_synced=ui_synced):
                attempts = [0]
                def reply(target, method):
                    if target == 'gooey.launcher':
                        attempts[0] += 1
                        return '{}'
                    return json.dumps({'ready': True, 'theme': {
                        'synced': ui_synced if attempts[0] == 1 else True}})
                def native(*args):
                    return json.dumps({'instance': 'test-instance', 'decorationMode': mode,
                        'theme': {'ready': native_ready if attempts[0] == 1 else True}})
                self.run.side_effect = native
                with mock.patch.object(session, 'shell', side_effect=reply), \
                     mock.patch.object(session.time, 'sleep') as sleep:
                    session.wait_ready()
                self.assertEqual(attempts[0], 2)
                sleep.assert_called_once_with(.25)

    def test_readiness_remains_compatible_with_previous_titlebar_release(self):
        self.run.side_effect = None
        self.run.return_value = json.dumps({'instance': 'test-instance'})
        with mock.patch.object(session, 'shell', side_effect=['{}', '{"ready":true}']), \
             mock.patch.object(session.time, 'sleep') as sleep:
            session.wait_ready()
        sleep.assert_not_called()

    def test_edited_or_duplicate_startup_markers_are_not_overwritten(self):
        for value in (session.BLOCK + session.BLOCK, session.BEGIN,
                      session.END, session.BLOCK.replace('hypr.gooey', 'hypr.mine')):
            with self.subTest(value=value):
                for transform in (session.add_block, session.remove_block):
                    with self.assertRaises(RuntimeError):
                        transform(value)

    def test_module_uses_quoted_user_path_and_only_right_super(self):
        module = session.module_text(Path('/tmp/a space/it\'s home'))
        self.assertIn('hl.unbind("SUPER + Super_R")', module)
        self.assertIn('release = true', module)
        self.assertIn('o.exec_on_start(', module)
        self.assertNotIn('SUPER + SPACE', module)
        self.assertNotIn('SUPER + ESCAPE', module)

    def test_explicit_unlocked_state_is_accepted(self):
        self.run.side_effect = None
        self.run.return_value = json.dumps([{'solitaryBlockedBy': []}])
        with mock.patch.object(session, 'shell', return_value=json.dumps({'secure': False, 'requested': False})):
            session.unlocked()

    def test_lock_or_pending_lock_prevents_switching(self):
        self.run.side_effect = None
        self.run.return_value = json.dumps([{'solitaryBlockedBy': []}])
        for key in ('secure', 'requested', 'locked', 'pending', 'sessionLocked'):
            with self.subTest(key=key):
                state = {'secure': False, 'requested': False, key: True}
                with mock.patch.object(session, 'shell', return_value=json.dumps(state)):
                    with self.assertRaises(RuntimeError):
                        session.unlocked()

    def test_unknown_lock_reply_fails_closed(self):
        self.run.side_effect = None
        self.run.return_value = json.dumps([{'solitaryBlockedBy': []}])
        for state in ({}, [], None, {'secure': False}, {'requested': False}, {'secure': None, 'requested': False}):
            with self.subTest(state=state):
                with mock.patch.object(session, 'shell', return_value=json.dumps(state)):
                    with self.assertRaises(RuntimeError):
                        session.unlocked()

    def test_missing_or_locked_monitor_state_fails_closed(self):
        self.run.side_effect = None
        for monitors in ([], [{}], [{'solitaryBlockedBy': ['LOCK']}], [{'solitaryBlockedBy': ['WORKSPACE']}]):
            with self.subTest(monitors=monitors):
                self.run.return_value = json.dumps(monitors)
                with mock.patch.object(session, 'shell') as shell:
                    with self.assertRaises(RuntimeError):
                        session.unlocked()
                    shell.assert_not_called()

    def test_recovery_tolerates_missing_shell_only_after_compositor_is_unlocked(self):
        self.run.side_effect = None
        self.run.return_value = json.dumps([{'solitaryBlockedBy': []}])
        with mock.patch.object(session, 'shell', side_effect=RuntimeError('shell not running')):
            session.unlocked(allow_missing_shell=True)
            with self.assertRaises(RuntimeError):
                session.unlocked()
        with mock.patch.object(session, 'shell', return_value='{}'):
            with self.assertRaises(RuntimeError):
                session.unlocked(allow_missing_shell=True)
        self.run.return_value = json.dumps([{'solitaryBlockedBy': ['LOCK']}])
        with mock.patch.object(session, 'shell') as shell:
            with self.assertRaises(RuntimeError):
                session.unlocked(allow_missing_shell=True)
            shell.assert_not_called()

    def test_refresh_waits_for_transient_lock_service_unavailability(self):
        self.run.side_effect = None
        self.run.return_value = json.dumps([{'solitaryBlockedBy': []}])
        responses = [RuntimeError('Target not found.'),
                     json.dumps({'secure': False, 'requested': False}), 'ok', '']
        with mock.patch.object(session, 'shell', side_effect=responses) as shell, \
                mock.patch.object(session.time, 'sleep') as sleep:
            session.refresh_shell()
        self.assertEqual(shell.call_args_list, [mock.call('lock', 'status'), mock.call('lock', 'status'),
                                               mock.call('shell', 'reloadConfig'), mock.call('shell', 'rescanPlugins')])
        sleep.assert_called_once()
        self.assertEqual(self.run.call_count, 2)  # Recheck compositor state on the retry.

    def test_refresh_never_retries_or_mutates_for_actual_or_unknown_lock_state(self):
        self.run.side_effect = None
        self.run.return_value = json.dumps([{'solitaryBlockedBy': []}])
        for state in ({'secure': True, 'requested': False}, {'secure': False, 'requested': True}, {}):
            with self.subTest(state=state):
                with mock.patch.object(session, 'shell', return_value=json.dumps(state)) as shell, \
                        mock.patch.object(session.time, 'sleep') as sleep:
                    with self.assertRaises(RuntimeError):
                        session.refresh_shell()
                    shell.assert_called_once_with('lock', 'status')
                    sleep.assert_not_called()

    def test_unavailable_lock_service_retry_has_a_deadline(self):
        with mock.patch.object(session, 'unlocked', side_effect=session.ShellUnavailable('Target not found.')) as unlocked, \
                mock.patch.object(session.time, 'monotonic', side_effect=[0, 10]), \
                mock.patch.object(session.time, 'sleep') as sleep:
            with self.assertRaises(session.ShellUnavailable):
                session.wait_unlocked()
            unlocked.assert_called_once_with()
            sleep.assert_not_called()

    def test_each_runtime_version_mismatch_is_rejected_before_loading(self):
        self.stage_fixture()
        valid = {'commit': 'tested-commit', 'version': 'test-version'}
        replies = [
            [json.dumps({**valid, 'commit': 'different'})],
            [json.dumps({**valid, 'version': 'different'})],
            [json.dumps(valid), 'omarchy different'],
            [json.dumps(valid), 'omarchy test', 'quickshell different'],
        ]
        for result in replies:
            with self.subTest(result=result):
                self.run.reset_mock(side_effect=True)
                self.run.side_effect = result
                with self.assertRaises(RuntimeError):
                    session.compatible(self.home, self.release)
                self.assertFalse(any('load' in call.args for call in self.run.call_args_list))

    def test_hyprbars_conflict_refuses_activation_without_writes(self):
        self.stage_fixture()
        self.preflight_mocks([{'name': 'hyprbars'}])
        with self.assertRaisesRegex(RuntimeError, 'hyprbars'):
            session.preflight(self.home)
        self.assertEqual(self.main.read_text(), self.initial_main)
        self.assertEqual(session.read(self.config_path), self.initial_config)
        self.assertFalse(self.module.exists())
        self.run.assert_not_called()

    def test_foreign_gooey_binary_is_not_adopted(self):
        self.stage_fixture()
        self.preflight_mocks([{'name': 'gooey'}])
        session.CORE['atomic_json'](self.data / 'session.json', {'loadedPath': '/tmp/unrelated.so'})
        with self.assertRaisesRegex(RuntimeError, 'different Gooey'):
            session.preflight(self.home)
        self.run.assert_not_called()

    def test_loaded_native_identity_requires_same_binary_and_compositor_instance(self):
        self.stage_fixture()
        binary = str(self.release / 'companion/gooey.so')
        with mock.patch.object(session, 'plugin_list', return_value=[{'name': 'gooey'}]):
            for record in ({}, {'loadedPath': binary, 'instance': 'old-instance'},
                           {'loadedPath': '/tmp/foreign.so', 'instance': 'test-instance'}):
                with self.subTest(record=record):
                    session.CORE['atomic_json'](self.data / 'session.json', record)
                    with self.assertRaises(RuntimeError):
                        session.load_native(self.home, self.release)
            session.CORE['atomic_json'](self.data / 'session.json', {
                'loadedPath': binary, 'instance': 'test-instance'})
            session.load_native(self.home, self.release)
        self.run.assert_not_called()

    def test_interrupted_native_load_keeps_marker_and_prevents_retry(self):
        self.stage_fixture()
        self.run.side_effect = RuntimeError('compositor disappeared')
        with mock.patch.object(session, 'plugin_list', return_value=[]):
            with self.assertRaisesRegex(RuntimeError, 'compositor disappeared'):
                session.load_native(self.home, self.release)
            pending = session.read(self.data / 'load-pending.json')
            self.assertEqual(pending['instance'], 'test-instance')
            self.assertEqual(pending['binary'], str(self.release / 'companion/gooey.so'))
            self.run.reset_mock()
            with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                session.load_native(self.home, self.release)
            self.run.assert_not_called()

    def test_existing_right_super_binding_is_preserved(self):
        self.stage_fixture()
        self.preflight_mocks([])
        self.run.side_effect = None
        self.run.return_value = json.dumps([{'key': 'Super_R', 'description': 'My launcher'}])
        with self.assertRaisesRegex(RuntimeError, 'Right Super'):
            session.preflight(self.home)
        self.assertEqual(self.main.read_text(), self.initial_main)

    def test_failed_enable_restores_files_and_unloads_new_native_companion(self):
        self.stage_fixture()
        existing = {'main': self.main.read_bytes(), 'config': self.config_path.read_bytes()}
        self.enterContext(mock.patch.object(session, 'preflight', return_value=(
            self.release, {'version': 'test-version'}, self.initial_config)))
        self.enterContext(mock.patch.object(session, 'plugin_list', return_value=[]))
        self.enterContext(mock.patch.object(session, 'unlocked'))
        load = self.enterContext(mock.patch.object(session, 'load_native'))
        unload = self.enterContext(mock.patch.object(session, 'unload_native'))
        reload = self.enterContext(mock.patch.object(session, 'reload_hypr'))
        refresh = self.enterContext(mock.patch.object(session, 'refresh_shell'))
        self.enterContext(mock.patch.object(session, 'wait_ready', side_effect=RuntimeError('readiness failure')))
        self.run.side_effect = lambda *args, **kwargs: '' if args == ('omarchy', 'restart', 'shell') else self.fail(f'Unexpected IPC: {args}')
        with self.assertRaisesRegex(RuntimeError, 'readiness failure'):
            session.enable(self.home)
        load.assert_called_once_with(self.home, self.release)
        unload.assert_called_once_with(self.home)
        self.assertEqual(self.main.read_bytes(), existing['main'])
        self.assertEqual(self.config_path.read_bytes(), existing['config'])
        self.assertEqual(self.main.stat().st_mode & 0o777, 0o644)
        self.assertFalse(self.module.exists())
        for name in ('session.json', 'activation.json', 'current'):
            self.assertFalse((self.data / name).exists(), name)
        for plugin_id in session.CORE['IDS']:
            self.assertFalse((self.home / '.config/omarchy/plugins' / plugin_id).is_symlink())
        self.assertGreaterEqual(reload.call_count, 2)
        self.assertGreaterEqual(refresh.call_count, 2)
        backups = list((self.data / 'backups').glob('*/hyprland.lua'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), existing['main'])
        self.run.assert_called_once_with('omarchy', 'restart', 'shell')

    def test_failed_unload_keeps_native_ownership_after_profile_rollback(self):
        self.stage_fixture()
        self.enterContext(mock.patch.object(session, 'preflight', return_value=(
            self.release, {'version': 'test-version'}, self.initial_config)))
        native = {'loaded': False, 'refuse_unload': True}
        self.enterContext(mock.patch.object(session, 'plugin_list', side_effect=lambda: (
            [{'name': 'gooey'}] if native['loaded'] else [])))
        self.enterContext(mock.patch.object(session, 'unlocked'))
        self.enterContext(mock.patch.object(session, 'reload_hypr'))
        self.enterContext(mock.patch.object(session, 'refresh_shell'))
        self.enterContext(mock.patch.object(session, 'wait_ready', side_effect=RuntimeError('readiness failure')))

        def native_ipc(*args, **kwargs):
            if args == ('omarchy', 'restart', 'shell'):
                return ''
            elif args[:3] == ('hyprctl', 'plugin', 'load'):
                native['loaded'] = True
            elif args[:3] == ('hyprctl', 'plugin', 'unload'):
                if native['refuse_unload']:
                    raise RuntimeError('native unload refused')
                native['loaded'] = False
            else:
                self.fail(f'Unexpected IPC: {args}')
            return 'ok'

        self.run.side_effect = native_ipc
        with self.assertRaisesRegex(RuntimeError, 'native unload refused'):
            session.enable(self.home)
        self.assertEqual(session.read(self.config_path), self.initial_config)
        self.assertEqual(self.main.read_text(), self.initial_main)
        self.assertFalse((self.data / 'session.json').exists())
        self.assertFalse((self.data / 'activation.json').exists())
        self.assertTrue(native['loaded'])
        self.assertEqual(session.read(self.data / 'native.json'), {
            'loadedPath': str(self.release / 'companion/gooey.so'), 'instance': 'test-instance'})
        # Recovery remains possible after the profile transaction removed session.json.
        native['refuse_unload'] = False
        session.unload_native(self.home)
        self.assertFalse(native['loaded'])
        self.assertFalse((self.data / 'native.json').exists())

    def test_enable_recovers_failed_component_loading_with_one_supported_shell_restart(self):
        self.stage_fixture()
        self.enterContext(mock.patch.object(session, 'preflight', return_value=(
            self.release, {'version': 'test-version'}, self.initial_config)))
        self.enterContext(mock.patch.object(session, 'plugin_list', return_value=[]))
        unlocked = self.enterContext(mock.patch.object(session, 'unlocked'))
        self.enterContext(mock.patch.object(session, 'load_native'))
        unload = self.enterContext(mock.patch.object(session, 'unload_native'))
        self.enterContext(mock.patch.object(session, 'reload_hypr'))
        self.enterContext(mock.patch.object(session, 'refresh_shell'))
        ready = self.enterContext(mock.patch.object(session, 'wait_ready', side_effect=[
            RuntimeError('stale failed QML component'), None]))

        def restart(*args, **kwargs):
            self.assertEqual(args, ('omarchy', 'restart', 'shell'))
            self.assertEqual(unlocked.call_count, 2)  # Fresh check after readiness failed.
            self.assertEqual(ready.call_count, 1)
            return ''

        self.run.side_effect = restart
        session.enable(self.home)
        self.run.assert_called_once_with('omarchy', 'restart', 'shell')
        self.assertEqual(ready.call_count, 2)
        unload.assert_not_called()
        self.assertTrue((self.data / 'activation.json').exists())
        self.assertIn(session.BLOCK, self.main.read_text())
        self.assertEqual((self.data / 'current').resolve(), self.release)
        self.assertEqual(session.read(self.config_path)['idle'], self.initial_config['idle'])

    def test_release_change_restarts_cached_qml_even_when_ready(self):
        self.stage_fixture()
        previous = self.data / 'releases/0.1.0-dev-000000000000'
        previous.mkdir()
        (self.data / 'current').symlink_to('releases/' + previous.name)
        self.enterContext(mock.patch.object(session, 'preflight', return_value=(
            self.release, {'version': 'test-version'}, self.initial_config)))
        self.enterContext(mock.patch.object(session, 'plugin_list', return_value=[]))
        unlocked = self.enterContext(mock.patch.object(session, 'wait_unlocked'))
        self.enterContext(mock.patch.object(session, 'unlocked'))
        self.enterContext(mock.patch.object(session, 'load_native'))
        self.enterContext(mock.patch.object(session, 'reload_hypr'))
        self.enterContext(mock.patch.object(session, 'refresh_shell'))
        ready = self.enterContext(mock.patch.object(session, 'wait_ready'))
        def restart(*args, **kwargs):
            self.assertEqual(args, ('omarchy', 'restart', 'shell'))
            unlocked.assert_called_once_with()
            ready.assert_not_called()
            return ''
        self.run.side_effect = restart
        session.enable(self.home)
        self.run.assert_called_once_with('omarchy', 'restart', 'shell')
        ready.assert_called_once_with()

    def test_enable_does_not_restart_shell_if_lock_starts_during_readiness_wait(self):
        self.stage_fixture()
        self.enterContext(mock.patch.object(session, 'preflight', return_value=(
            self.release, {'version': 'test-version'}, self.initial_config)))
        self.enterContext(mock.patch.object(session, 'plugin_list', return_value=[]))
        self.enterContext(mock.patch.object(session, 'unlocked', side_effect=[None, RuntimeError('Lock screen is active')]))
        self.enterContext(mock.patch.object(session, 'load_native'))
        unload = self.enterContext(mock.patch.object(session, 'unload_native'))
        self.enterContext(mock.patch.object(session, 'reload_hypr'))
        self.enterContext(mock.patch.object(session, 'refresh_shell'))
        ready = self.enterContext(mock.patch.object(session, 'wait_ready', side_effect=RuntimeError('not ready')))
        with self.assertRaisesRegex(RuntimeError, 'Lock screen is active'):
            session.enable(self.home)
        self.run.assert_not_called()
        ready.assert_called_once_with()
        unload.assert_called_once_with(self.home)
        self.assertEqual(session.read(self.config_path), self.initial_config)
        self.assertEqual(self.main.read_text(), self.initial_main)
        self.assertFalse((self.data / 'activation.json').exists())


class StyleToggle(unittest.TestCase):
    def test_preserves_jsonc_and_quotes_command(self):
        original = '// header {\n{\n // user setting\n "personal": {"label": "a,} // label"},\n}\n'
        updated, owned = session.style_menu(original, Path('/tmp/home with spaces/gooey'))
        parsed = session.parse_menu(updated)
        self.assertEqual(parsed['personal']['label'], 'a,} // label')
        self.assertIn("'/tmp/home with spaces/gooey' toggle --notify", parsed['style.gooey']['action'])
        self.assertIn('// user setting', updated)
        again, same = session.style_menu(updated, Path('/tmp/home with spaces/gooey'), owned)
        self.assertEqual((updated, owned), (again, same))

    def test_preserves_user_edited_owned_entry(self):
        text, owned = session.style_menu('{}', Path('/tmp/gooey'))
        with self.assertRaises(RuntimeError):
            session.style_menu(text.replace('Toggle mouse-friendly', 'My custom'), Path('/tmp/gooey'), owned)

    def test_rejects_unowned_entry(self):
        with self.assertRaises(RuntimeError):
            session.style_menu('{"style.gooey": {"label": "Mine"}}', Path('/tmp/gooey'))

    def test_toggle_uses_guarded_enable_disable(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            data, _, _ = session.paths(home)
            with mock.patch.object(session, 'enable') as enable, mock.patch.object(session, 'disable') as disable:
                session.toggle(home)
                enable.assert_called_once_with(home)
                disable.assert_not_called()
                data.mkdir(parents=True)
                (data / 'activation.json').write_text('{}')
                session.toggle(home)
                disable.assert_called_once_with(home)


if __name__ == '__main__':
    unittest.main()

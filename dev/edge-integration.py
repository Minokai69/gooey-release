"""Additional real-session checks; called only by the isolated integration runner.

No compositor is started here. ``run_checks(test)`` consumes the parent runner's
helpers and returns explicit limitations for unavailable virtual-output support.
"""
import json
import os
from pathlib import Path
import time


def _until(predicate, label, timeout=8):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                return result
        except (RuntimeError, ValueError, KeyError, StopIteration) as exc:
            last_error = exc
        time.sleep(.15)
    raise AssertionError(f'Timed out: {label}; {last_error}')


def _monitors(test):
    return json.loads(test.run('hyprctl', '-j', 'monitors'))


def _close_panels(test):
    test.ipc('gooey.launcher', 'close')
    test.ipc('gooey.window-tools', 'close')


def _focus(test, name):
    # Output names remain Lua string data; they never enter a command shell.
    test.run('hyprctl', 'dispatch',
             'hl.dsp.focus({ monitor = ' + json.dumps(name) + ' })')
    _until(lambda: any(m['name'] == name and m.get('focused')
                       for m in _monitors(test)), 'focus output ' + name)


def _client(test, address):
    key = address.lower().removeprefix('0x')
    return next((client for client in json.loads(test.run('hyprctl', '-j', 'clients'))
                 if str(client['address']).lower().removeprefix('0x') == key), None)


def _shelf_survives_reload(test):
    _close_panels(test)
    initial = test.state()
    owner = next((w for w in initial['windows'] if not w.get('grouped')
                  and w.get('capabilities', {}).get('shelf')), None)
    assert owner, 'A mapped ungrouped fixture is required for companion reload'
    owner_id = owner['id']
    was_shelved = owner['shelved']
    origin_selector = owner['workspaceName']
    companion = Path(os.environ['HOME']) / '.local/share/gooey/current/companion/gooey.so'
    assert companion.is_file(), 'Private staged companion is missing'
    unloaded = False
    try:
        if not was_shelved:
            test.check('Reload fixture can be sent to Shelf', test.action('shelf', owner_id)['ok'])
        _until(lambda: test.window(owner_id)['shelved'], 'reload fixture shelved')
        shelved_before = {w['id'] for w in test.state()['windows'] if w['shelved']}
        test.ipc('gooey.window-tools', 'shelf')
        _until(lambda: test.status('gooey.window-tools')['ready'], 'Shelf service before unload')

        test.run('hyprctl', 'plugin', 'unload', companion)
        unloaded = True
        _until(lambda: not test.status('gooey.window-tools')['ready'],
               'QML reports companion unavailable')
        client = _client(test, owner['address'])
        test.check('Unloading companion leaves the shelved application running',
                   client is not None and client['workspace']['name'] == 'special:scratchpad')
        test.check('QML disables actions while companion is unloaded',
                   not test.status('gooey.window-tools')['ready'])

        test.run('hyprctl', 'plugin', 'load', companion)
        unloaded = False
        recovered = _until(lambda: test.state() if test.state()['instance'] == initial['instance'] else None,
                           'native companion reloaded')
        _until(lambda: test.status('gooey.window-tools')['ready'], 'QML reconnects after reload')
        test.check('Companion reload preserves live Shelf membership and native IDs',
                   {w['id'] for w in recovered['windows'] if w['shelved']} == shelved_before)
        test.ipc('gooey.window-tools', 'shelf')
        _until(lambda: test.status('gooey.window-tools')['shelfCount'] == len(shelved_before),
               'Shelf list reconstructed after reload')
        test.check('QML Shelf list recovers without restarting the shell')
        _close_panels(test)
        if not was_shelved:
            # The original empty workspace may have disappeared while shelved.
            # This explicit, captured workspace move can recreate that selection.
            test.check('Reloaded companion can restore the original fixture workspace',
                       test.action('workspace', owner_id, '0 ' + origin_selector)['ok'])
            _until(lambda: not test.window(owner_id)['shelved'], 'restore fixture after companion reload')
    finally:
        if unloaded:
            test.run('hyprctl', 'plugin', 'load', companion)
            _until(lambda: test.status('gooey.window-tools')['ready'], 'reload cleanup')
        _close_panels(test)
        current = test.window(owner_id)
        if current and not was_shelved and current['shelved']:
            result = test.action('workspace', owner_id, '0 ' + origin_selector)
            assert result['ok'], 'Failed to restore Shelf test fixture: ' + str(result)


def _in_bounds(menu):
    card, screen = menu['card'], menu['screen']
    return (card['width'] > 0 and card['height'] > 0 and card['x'] >= 0 and card['y'] >= 0
            and card['x'] + card['width'] <= screen['width'] + 1
            and card['y'] + card['height'] <= screen['height'] + 1)


def _inward(menu):
    card, anchor, side = menu['card'], menu['anchor'], menu['barPosition']
    return {'top': card['y'] >= anchor['y'] + anchor['height'] - 1,
            'bottom': card['y'] + card['height'] <= anchor['y'] + 1,
            'left': card['x'] >= anchor['x'] + anchor['width'] - 1,
            'right': card['x'] + card['width'] <= anchor['x'] + 1}[side]


def _click_global(test, rect):
    """Virtual-pointer absolute coordinates span the entire logical desktop."""
    monitors = _monitors(test)
    left = min(m['x'] for m in monitors)
    top = min(m['y'] for m in monitors)
    right = max(m['x'] + m['width'] / m['scale'] for m in monitors)
    bottom = max(m['y'] + m['height'] / m['scale'] for m in monitors)
    x = round(rect['x'] + rect['width'] / 2 - left)
    y = round(rect['y'] + rect['height'] / 2 - top)
    test.run(test.ROOT / 'work/input/gooey-input',
             'move', x, y, round(right - left), round(bottom - top),
             'sleep', 100, 'down', 'sleep', 100, 'up')
    time.sleep(.35)


def _scaled_window_tab(test, scaled):
    """Use actual native pointer targets on the disposable scaled output."""
    scale_label = str(round(scaled["scale"] * 100)) + "%"
    _close_panels(test)
    owner = next((w for w in test.state()['windows'] if not w.get('grouped')
                  and not w.get('shelved') and w.get('buttons')
                  and w.get('capabilities', {}).get('workspace')), None)
    assert owner, 'A mapped fixture with a window strip is required'
    owner_id = owner['id']
    origin_selector, origin_monitor = owner['workspaceName'], owner['monitor']
    initial_anchor = dict(owner['anchor'])
    target = scaled['name']
    destination = str(scaled['activeWorkspace']['id'])
    try:
        _focus(test, target)
        result = test.action('workspace', owner_id, '0 ' + destination)
        assert result['ok'], 'Cannot move scaled-output fixture: ' + str(result)
        _until(lambda: test.window(owner_id)['monitor'] == target,
               'fixture moved to scaled output')
        time.sleep(.8)
        current = test.window(owner_id)
        anchor = current['anchor']
        actual_monitor = next(m for m in _monitors(test) if m['name'] == target)
        reserved = actual_monitor['reserved']
        usable_left = actual_monitor['x'] + reserved[0]
        usable_right = actual_monitor['x'] + actual_monitor['width'] / actual_monitor['scale'] - reserved[2]
        # Moving a tile to an otherwise empty output changes its client width.
        # The strip must span that new frame, while the theme height remains in
        # logical pixels. Each frame edge may include the fixture's 2px border.
        test.check(f'Full-width strip follows its client frame at {scale_label} with unchanged logical height',
                   current['decorationVisible']
                   and abs(anchor['height'] - initial_anchor['height']) <= 1
                   and abs(anchor['x'] - max(current['x'], usable_left)) <= 2.01
                   and abs(anchor['x'] + anchor['width']
                           - min(current['x'] + current['width'], usable_right)) <= 2.01
                   and anchor['x'] >= usable_left - .51
                   and anchor['x'] + anchor['width'] <= usable_right + .51
                   and anchor['y'] + anchor['height'] <= current['y'] + 1)
        test.check('Scaled full-width strip reports all hit targets inside its visible surface',
                   {'drag-grip', 'menu-actions', 'resize-grip', 'shelf', 'menu-workspace', 'fullscreen', 'close'}.issubset({b['action'] for b in current['buttons']})
                   and all(b['x'] >= anchor['x'] - 1 and b['y'] >= anchor['y'] - 1
                       and b['x'] + b['width'] <= anchor['x'] + anchor['width'] + 1
                       and b['y'] + b['height'] <= anchor['y'] + anchor['height'] + 1
                       for b in current['buttons']))
        button = next(b for b in current['buttons'] if b['action'] == 'menu-actions')
        _click_global(test, button)
        menu = _until(lambda: test.status('gooey.window-tools')
                      if test.status('gooey.window-tools')['opened']
                      and test.status('gooey.window-tools')['targetId'] == owner_id
                      and test.status('gooey.window-tools')['output'] == target else None,
                      'scaled window strip opens its owning window menu')
        time.sleep(.35)
        menu = test.status('gooey.window-tools')
        card = menu['card']
        test.check(f'Clicking the {scale_label} window strip opens its captured owner menu',
                   menu['targetId'] == owner_id and menu['output'] == target)
        test.check('Scaled window menu remains within logical output bounds',
                   card['x'] >= 0 and card['y'] >= 0
                   and card['width'] > 0 and card['height'] > 0
                   and card['x'] + card['width'] <= scaled['width'] / scaled['scale'] + 1
                   and card['y'] + card['height'] <= scaled['height'] / scaled['scale'] + 1)
        test.shot('gooey-window-menu-mixed-scale-' + scale_label)
        close = test.ui_button('close-menu')
        _click_global(test, {**close, 'x': close['x'] + scaled['x'],
                            'y': close['y'] + scaled['y']})
        _until(lambda: not test.status('gooey.window-tools')['opened'],
               'scaled window menu closes by mouse')
        test.check('Window menu mouse targets work on the scaled output')
        resize = next(b for b in test.window(owner_id)['buttons'] if b['action'] == 'resize-grip')
        _click_global(test, resize)
        _until(lambda: test.status('gooey.window-tools')['opened']
               and test.status('gooey.window-tools')['kind'] == 'layout'
               and test.status('gooey.window-tools')['targetId'] == owner_id
               and test.status('gooey.window-tools')['output'] == target,
               'scaled Resize click opens owner size controls')
        test.check(f'Clicking Resize opens the captured owner size controls at {scale_label}')
        def right_aligned():
            menu = test.status('gooey.window-tools')
            current = test.window(owner_id)
            output = next(m for m in _monitors(test) if m['name'] == target)
            margin = max(1, int(12 * menu['theme']['scale'] + .5))
            width = menu['card']['width']
            trigger = next(b for b in current['buttons'] if b['action'] == 'resize-grip')
            left = trigger['x'] - output['x']
            expected = max(margin, min(left,
                           output['width'] / output['scale'] - width - margin))
            return (menu['opened'] and menu['source'] == 'window'
                    and menu['targetId'] == owner_id
                    and abs(menu['card']['x'] - expected) <= 1)
        _until(right_aligned, 'scaled Resize popup follows the resize button')
        test.check(f'Resize popup aligns with the resize button inside screen margins at {scale_label}')
    finally:
        _close_panels(test)
        if test.window(owner_id):
            _focus(test, origin_monitor)
            result = test.action('workspace', owner_id, '0 ' + origin_selector)
            assert result['ok'], 'Failed to restore scaled fixture: ' + str(result)
            _until(lambda: test.window(owner_id)['monitor'] == origin_monitor
                   and test.window(owner_id)['workspaceName'] == origin_selector,
                   'scaled fixture restored to original workspace and output')


def _scaled_output(test):
    _close_panels(test)
    original = _monitors(test)
    original_names = {m['name'] for m in original}
    original_focus = next((m['name'] for m in original if m.get('focused')), original[0]['name'])
    created = []
    rules_changed = False
    limitations = []
    try:
        try:
            response = test.run('hyprctl', 'output', 'create', 'headless')
            fresh = _until(lambda: [m for m in _monitors(test) if m['name'] not in original_names],
                           'headless test output', timeout=4)
        except (RuntimeError, AssertionError) as exc:
            limitation = 'Headless output unavailable; mixed-scale/hotplug checks skipped: ' + str(exc)
            print('SKIP:', limitation, flush=True)
            limitations.append(limitation)
            return limitations
        created = [m['name'] for m in fresh]
        target = fresh[0]['name']
        right_edge = max(int(m['x'] + m['width'] / m['scale']) for m in original)
        # Configure only the disposable output; physical mode 1920×1200 yields
        # logical 1280×800 at 150%, beside the unchanged nested output.
        lua = ('hl.monitor({ output = ' + json.dumps(target)
               + ', mode = "1920x1200@60", position = '
               + json.dumps(f'{right_edge}x0') + ', scale = 1.5 })')
        test.run('hyprctl', 'eval', lua)
        rules_changed = True
        scaled = _until(lambda: next((m for m in _monitors(test)
                                     if m['name'] == target and abs(m['scale'] - 1.5) < .01
                                     and m['x'] == right_edge), None), '150% output mode')
        test.check('Created a second nested output at a different scale',
                   scaled['name'] not in original_names and abs(scaled['scale'] - 1.5) < .01)
        _focus(test, target)
        test.run(test.ROOT / 'work/input/gooey-keyboard', 'down',126,'sleep',120,'up',126)
        menu = _until(lambda: test.status() if test.status().get('visible')
                      and test.status().get('output') == target and test.status().get('anchorReady') else None,
                      'right Super chooses focused second output')
        time.sleep(.4)
        menu = test.status()
        test.check('Right Super chooses the button on the focused second output',
                   menu['output'] == target and menu['anchorReady'])
        test.check('Scaled-output launcher remains within logical output bounds', _in_bounds(menu))
        test.check('Scaled-output launcher opens inward from its actual button', _inward(menu))
        test.shot('gooey-launcher-mixed-scale')
        _scaled_window_tab(test, scaled)
        # Thirty logical pixels at 125% round to 38 physical pixels. This
        # previously dropped the third painted icon while leaving it clickable.
        private_theme = Path(os.environ['XDG_CONFIG_HOME']) / 'omarchy/shell.toml'
        original_theme = private_theme.read_text()
        previous_height = test.state()['theme']['height']
        def save_theme(text):
            temporary = private_theme.with_suffix('.scale-check')
            temporary.write_text(text)
            temporary.replace(private_theme)
        try:
            save_theme('[bar]\nsize-horizontal = 30\n[font]\nbase-size = 12\n')
            test.until(lambda: test.state()['theme']['height'] == 30, '125% test bar size')
            test.run('hyprctl', 'eval', 'hl.monitor({ output=' + json.dumps(target)
                     + ', mode="1600x1000@60", position=' + json.dumps(f'{right_edge}x0')
                     + ', scale=1.25 })')
            scaled = _until(lambda: next((m for m in _monitors(test)
                               if m['name'] == target and abs(m['scale'] - 1.25) < .01), None),
                            '125% output mode')
            _scaled_window_tab(test, scaled)
        finally:
            save_theme(original_theme)
            test.until(lambda: test.state()['theme']['height'] == previous_height, 'restore bar size after 125%')

        test.ipc('gooey.launcher', 'close')
        _focus(test, original_focus)
        test.ipc('gooey.launcher', 'summon', 'root')
        _until(lambda: test.status().get('visible') and test.status().get('output') == original_focus,
               'launcher follows focus back to original output')
        test.check('Keyboard launcher does not keep a stale second-output anchor')
        test.ipc('gooey.launcher', 'close')
        _focus(test, target)
        test.ipc('gooey.launcher', 'summon', 'root')
        _until(lambda: test.status().get('visible') and test.status().get('output') == target,
               'launcher opened before output removal')
        test.run('hyprctl', 'output', 'remove', target)
        _until(lambda: all(m['name'] != target for m in _monitors(test)), 'selected output removed')
        created.remove(target)
        _until(lambda: not test.status().get('visible') and not test.status().get('opened'),
               'launcher closes when its output disappears')
        test.check('Removing the selected output closes the launcher and releases its surface')
    finally:
        _close_panels(test)
        # Include an output that appeared just after a creation timeout, too.
        remaining = [m['name'] for m in _monitors(test) if m['name'] not in original_names]
        for name in remaining:
            test.run('hyprctl', 'output', 'remove', name)
        if rules_changed:
            # Drops the temporary monitor rule; retains existing output modes.
            test.run('hyprctl', 'reload', 'config-only')
        _until(lambda: {m['name'] for m in _monitors(test)} == original_names, 'restore original output inventory')
        _focus(test, original_focus)
        restored = {m['name']: m for m in _monitors(test)}
        test.check('Extra checks preserve original output scales and positions',
                   all(abs(restored[m['name']]['scale'] - m['scale']) < .01
                       and restored[m['name']]['x'] == m['x'] and restored[m['name']]['y'] == m['y']
                       for m in original))
    return limitations


def run_checks(test):
    """Run against the parent's nested compositor and return any explicit skips."""
    assert os.environ.get('OMARCHY_MOUSE_PREVIEW') == '1'
    assert os.environ.get('GOOEY_MODE') == 'integration'
    assert os.environ.get('WAYLAND_DISPLAY') not in (None, '', '/run/host-wayland')
    assert os.environ.get('OMARCHY_PATH') == '/opt/omarchy-mouse-shell/base'
    _shelf_survives_reload(test)
    return _scaled_output(test)

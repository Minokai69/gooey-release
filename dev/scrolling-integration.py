"""Exercise layout-specific mouse controls in the parent's isolated desktop.

Only temporary runtime values are changed. Every configuration value and fixture
workspace/floating state is restored before returning; no app rules are created.
The companion contract targets native columns rather than a focused-window
layout message, so the checks deliberately change focus behind an open menu.
"""
import json
import os
import time


def _menu(test):
    return test.status('gooey.window-tools')


def _close(test):
    test.ipc('gooey.launcher', 'close')
    test.ipc('gooey.window-tools', 'close')


def _config_value(test, key, kind):
    data = json.loads(test.run('hyprctl', '-j', 'getoption', key))
    if kind == 'bool':
        # 0.56's native Lua bool config values serialize under "bool";
        # retain the integer fallback for values supplied by older providers.
        return bool(data['bool'] if 'bool' in data else data['int'])
    return data[{'string': 'str', 'float': 'float', 'int': 'int'}[kind]]


def _lua(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return json.dumps(value)


def _configure(test, layout, scrolling):
    fields = ', '.join(key + '=' + _lua(value) for key, value in scrolling.items())
    test.run('hyprctl', 'eval', 'hl.config({ general={ layout=' + _lua(layout)
             + ' }, scrolling={ ' + fields + ' } })')


def _click_global(test, rect):
    monitors = json.loads(test.run('hyprctl', '-j', 'monitors'))
    left = min(m['x'] for m in monitors)
    top = min(m['y'] for m in monitors)
    right = max(m['x'] + m['width'] / m['scale'] for m in monitors)
    bottom = max(m['y'] + m['height'] / m['scale'] for m in monitors)
    test.run(test.ROOT / 'work/input/gooey-input',
             'move', round(rect['x'] + rect['width'] / 2 - left),
             round(rect['y'] + rect['height'] / 2 - top),
             round(right - left), round(bottom - top),
             'sleep', 100, 'down', 'sleep', 100, 'up')
    time.sleep(.3)


def _click_ui(test, action):
    # A width change animates its native owner and can move the anchored menu on
    # later service snapshots. Wait across two 350ms service polls, then send a
    # single click using one coherent menu snapshot, without an action retry.
    previous, since = None, 0
    def settled():
        nonlocal previous, since
        menu = _menu(test)
        rect = next((button for button in menu['buttons'] if button['action'] == action
                     and button['visible'] and button['enabled']), None)
        if not rect or menu['busy']:
            previous, since = None, 0
            return None
        key = (menu['targetId'], menu['output'], menu['kind'],
               rect['x'], rect['y'], rect['width'], rect['height'])
        if key != previous:
            previous, since = key, time.monotonic()
            return None
        return (menu, rect) if time.monotonic() - since >= .7 else None
    menu, rect = test.until(settled, 'stable visible mouse target ' + action, timeout=8)
    snapshot = test.state()
    output = next(m for m in snapshot['monitors'] if m['name'] == menu['output'])
    (test.CACHE / 'gooey-last-window-click.json').write_text(json.dumps({
        'action': action, 'rect': rect, 'menu': menu,
        'owner': next((w for w in snapshot['windows'] if w['id'] == menu['targetId']), None)
    }, indent=2))
    _click_global(test, {**rect, 'x': rect['x'] + output['x'], 'y': rect['y'] + output['y']})


def _visible_actions(test):
    return {button['action'] for button in _menu(test)['buttons'] if button['visible']}


def _pointer_to_menu_header(test):
    """Leave width-button tooltips before saving a settled, open-menu image."""
    previous, since = None, 0
    def settled():
        nonlocal previous, since
        menu = _menu(test)
        if not menu['opened'] or menu['busy']:
            return None
        card = menu['card']
        close = next(b for b in menu['buttons'] if b['action'] == 'close-menu' and b['visible'])
        point = (card['x'] + card['width'] / 3, close['y'] + close['height'] / 2)
        key = (menu['targetId'], menu['output'], *point)
        if key != previous:
            previous, since = key, time.monotonic()
            return None
        return (menu, point) if time.monotonic() - since >= .7 else None
    menu, (x, y) = test.until(settled, 'stable inert menu header')
    assert all(not (b['x'] <= x <= b['x'] + b['width']
                    and b['y'] <= y <= b['y'] + b['height'])
               for b in menu['buttons'] if b['visible']), 'Screenshot pointer must avoid menu controls'
    monitors = json.loads(test.run('hyprctl', '-j', 'monitors'))
    output = next(m for m in monitors if m['name'] == menu['output'])
    left, top = min(m['x'] for m in monitors), min(m['y'] for m in monitors)
    right = max(m['x'] + m['width'] / m['scale'] for m in monitors)
    bottom = max(m['y'] + m['height'] / m['scale'] for m in monitors)
    test.run(test.ROOT / 'work/input/gooey-input', 'move',
             round(x + output['x'] - left), round(y + output['y'] - top),
             round(right - left), round(bottom - top), 'sleep', 200)


def _open_owner(test, owner_id, layout=False):
    _close(test)
    owner = test.window(owner_id)
    if owner.get('capabilities', {}).get('columnCenter'):
        assert test.action('column-center', owner_id)['ok']
    assert test.action('focus', owner_id)['ok']
    time.sleep(.7)
    button_action = 'resize-grip' if layout else 'menu-actions'
    button = next(b for b in test.window(owner_id)['buttons'] if b['action'] == button_action)
    _click_global(test, button)
    test.until(lambda: _menu(test)['opened'] and _menu(test)['targetId'] == owner_id,
               'scrolling test captured owner menu')
    if layout:
        test.until(lambda: _menu(test)['kind'] == 'layout', 'layout submenu')
        def right_aligned():
            menu = _menu(test)
            owner = test.window(owner_id)
            output = next(m for m in test.state()['monitors'] if m['name'] == owner['monitor'])
            margin = max(1, int(12 * menu['theme']['scale'] + .5))
            width = menu['card']['width']
            trigger = next(b for b in owner['buttons'] if b['action'] == 'resize-grip')
            left = trigger['x'] - output['x']
            expected = max(margin, min(left, output['width'] - width - margin))
            return (menu['opened'] and menu['source'] == 'window'
                    and menu['targetId'] == owner_id
                    and abs(menu['card']['x'] - expected) <= 1)
        test.until(right_aligned, 'full-width Resize popup follows the resize button')
        test.check('Resize popup follows its scrolling frame button inside screen margins')


def _width(test, owner_id):
    return test.window(owner_id)['scrolling']['columnWidth']


def _fully_visible(test, owner_id):
    win = test.window(owner_id)
    monitor = next(m for m in test.state()['monitors'] if m['name'] == win['monitor'])
    return (win['x'] >= monitor['x'] - 1 and win['y'] >= monitor['y'] - 1
            and win['x'] + win['width'] <= monitor['x'] + monitor['width'] + 1
            and win['y'] + win['height'] <= monitor['y'] + monitor['height'] + 1)


def _settled_snapshot(test, stage):
    previous, since = None, 0
    def settled():
        nonlocal previous, since
        snapshot = test.state()
        key = tuple((w['id'], w['monitor'], w['workspaceId'],
                     w['x'], w['y'], w['width'], w['height'], w['decorationVisible'])
                    for w in snapshot['windows'])
        if key != previous:
            previous, since = key, time.monotonic()
            return None
        return snapshot if time.monotonic() - since >= .6 else None
    snapshot = test.until(settled, 'settled scrolling geometry ' + stage)
    snapshot['hyprlandMonitors'] = json.loads(test.run('hyprctl', '-j', 'monitors'))
    (test.CACHE / ('gooey-scrolling-bounds-' + stage + '.json')).write_text(
        json.dumps(snapshot, indent=2))
    return snapshot


def _check_visible_strip_bounds(test, stage, hidden_id=None):
    """Full-width strips span the visible client frame without spilling over."""
    snapshot = _settled_snapshot(test, stage)
    monitors = {monitor['name']: monitor for monitor in snapshot['monitors']}
    usable_edges = {}
    for monitor in snapshot['hyprlandMonitors']:
        reserved = monitor['reserved']
        usable_edges[monitor['name']] = (
            monitor['x'] + reserved[0], monitor['y'] + reserved[1],
            monitor['x'] + monitor['width'] / monitor['scale'] - reserved[2],
            monitor['y'] + monitor['height'] / monitor['scale'] - reserved[3])
    slivers = []
    for win in snapshot['windows']:
        monitor = monitors[win['monitor']]
        usable_left, usable_top, usable_right, usable_bottom = usable_edges[win['monitor']]
        left = max(win['x'], usable_left)
        right = min(win['x'] + win['width'], usable_right)
        anchor = win['anchor']
        # The fixture rule has decorations enabled. A complete frame and its
        # reserved top edge inside the viewport must not silently lose its strip,
        # even when this peer is unfocused and no menu is open for it.
        if (win['title'] in ('Gooey · Notes', 'Gooey · Files')
                and win['workspaceId'] == monitor['activeWorkspaceId']
                and not win['floating'] and not win['shelved'] and not win['grouped']
                and win['fullscreen'] == 0
                and win['x'] - 2 >= usable_left - .51
                and win['x'] + win['width'] + 2 <= usable_right + .51
                and win['y'] - snapshot['theme']['height'] - 2 >= usable_top - .51
                and win['y'] - 2 <= usable_bottom + .51):
            assert win['decorationVisible'] and win['buttons'], \
                'A fully visible fixture lost its full-width strip: ' + json.dumps(win)
        if win['decorationVisible']:
            # Native TOP assignment can include the fixture's 2px frame border.
            # Check both edges, rather than only a center that a compact strip
            # would also satisfy. Clipping follows the visible client region.
            assert anchor['width'] > 0 and anchor['height'] > 0 \
                and abs(anchor['x'] - left) <= 2.01 \
                and abs(anchor['x'] + anchor['width'] - right) <= 2.01 \
                and anchor['x'] >= usable_left - .51 \
                and anchor['x'] + anchor['width'] <= usable_right + .51 \
                and anchor['y'] >= usable_top - .51 \
                and anchor['y'] + anchor['height'] <= usable_bottom + .51 \
                and anchor['y'] + anchor['height'] <= win['y'] + 1 \
                and win['reservedTop'] >= anchor['height'] \
                and win['appName'], \
                'Visible strip overlaps or leaves its own reserved area: ' + json.dumps(win)
            assert win['buttons'] and all(
                b['width'] > 0 and b['height'] > 0
                and b['x'] >= anchor['x'] - .51 and b['y'] >= anchor['y'] - .51
                and b['x'] + b['width'] <= anchor['x'] + anchor['width'] + .51
                and b['y'] + b['height'] <= anchor['y'] + anchor['height'] + .51
                for b in win['buttons']), 'Full-width strip exposes input beyond its visible surface'
        else:
            assert not win['buttons'] and anchor['width'] == 0 and anchor['height'] == 0, \
                'Unavailable strip retains pointer targets: ' + json.dumps(win)
        # A visible frame fragment narrower than one control is inert. Include
        # border tolerance when selecting such fragments from client geometry.
        height = snapshot['theme']['height']
        if win['workspaceId'] == monitor['activeWorkspaceId'] and 0 < right - left + 4 < height:
            slivers.append(win)
    test.check('Full-width scrolling strips span their visible client frame without overlap')
    # Half-width columns can both fit. If a sliver exists it must still be inert;
    # the required hidden-owner case below uses two explicitly full columns.
    assert all(not win['decorationVisible'] and not win['buttons']
               and win['anchor']['width'] == 0 for win in slivers), \
        'A thin scrolling-window sliver retains strip input'
    if hidden_id is not None:
        hidden = next(w for w in snapshot['windows'] if w['id'] == hidden_id)
        monitor = monitors[hidden['monitor']]
        usable_left, _, usable_right, _ = usable_edges[hidden['monitor']]
        visible_width = min(hidden['x'] + hidden['width'], usable_right) \
            - max(hidden['x'], usable_left)
        # Full columns occupy a viewport each. Depending on output gaps, their
        # neighbor is fully outside or leaves a narrow edge fragment, neither of
        # which may expose a named strip or native menu targets.
        test.check('Adjacent full-width column has no visible strip or pointer targets (' + stage + ')',
                   hidden['workspaceId'] == monitor['activeWorkspaceId']
                   and abs(hidden['scrolling']['columnWidth'] - 1) < .001
                   and visible_width + 4 < snapshot['theme']['height']
                   and not hidden['decorationVisible'] and not hidden['buttons']
                   and hidden['anchor']['width'] == 0 and hidden['anchor']['height'] == 0)
        target_before = _menu(test)['targetId']
        opened_before = _menu(test)['opened']
        test.check('Native menu rejects the offscreen column (' + stage + ')',
                   not test.action('menu-actions', hidden_id)['ok']
                   and _menu(test)['targetId'] == target_before
                   and _menu(test)['opened'] == opened_before)


def run_checks(test):
    """Called before the parent closes either Notes or Files; returns no skips."""
    assert os.environ.get('OMARCHY_MOUSE_PREVIEW') == '1'
    assert os.environ.get('GOOEY_MODE') == 'integration'
    assert os.environ.get('WAYLAND_DISPLAY') not in (None, '', '/run/host-wayland')
    assert os.environ.get('OMARCHY_PATH') == '/opt/omarchy-mouse-shell/base'
    _close(test)
    originals = [dict(w) for w in test.state()['windows']
                 if w['title'] in ('Gooey · Notes', 'Gooey · Files')]
    assert len(originals) == 2 and all(not w['grouped'] and not w['shelved'] for w in originals), \
        'Two unshelved, ungrouped fixtures are required'
    original_layout = _config_value(test, 'general:layout', 'string')
    setting_types = {'column_width': 'float', 'fullscreen_on_one_column': 'bool',
                     'follow_focus': 'bool', 'focus_fit_method': 'int', 'direction': 'string'}
    original_scrolling = {key: _config_value(test, 'scrolling:' + key, kind)
                          for key, kind in setting_types.items()}
    focus_id = next((w['id'] for w in test.state()['windows'] if w['focused']), originals[0]['id'])
    owner_id, other_id = [w['id'] for w in originals]
    target_workspace = originals[0]['workspaceName']
    try:
        for original in originals:
            if original['floating']:
                assert test.action('float', original['id'])['ok']
            if original['workspaceName'] != target_workspace:
                assert test.action('workspace', original['id'], '0 ' + target_workspace)['ok']
        _configure(test, 'dwindle', original_scrolling)
        test.until(lambda: all(test.window(w['id'])['layout'] == 'dwindle'
                               and not test.window(w['id'])['floating'] for w in originals),
                   'dwindle test fixture layout')
        _open_owner(test, owner_id)
        test.check('Dwindle main controls omit scrolling-only width presets',
                   'column-width-half' not in _visible_actions(test)
                   and 'column-width-85' not in _visible_actions(test)
                   and 'column-width-full' not in _visible_actions(test))
        _click_ui(test, 'layout-menu')
        test.until(lambda: 'split' in _visible_actions(test), 'dwindle split control')
        test.check('Dwindle exposes its split control and rejects column sizing',
                   test.window(owner_id)['capabilities']['split']
                   and not test.action('column-width', owner_id, 'full')['ok'])
        _close(test)

        # Explicit test-only values make real geometry comparable. In particular,
        # one-column fullscreen would mask a half-width result after a move.
        _configure(test, 'scrolling', {'column_width': .5,
                   'fullscreen_on_one_column': False, 'follow_focus': False,
                   'focus_fit_method': 1, 'direction': 'right'})
        test.until(lambda: all(test.window(w['id'])['layout'] == 'scrolling'
                               and test.window(w['id'])['scrolling'] for w in originals),
                   'scrolling test fixture layout')
        original_fraction = _width(test, owner_id)
        assert test.action('focus', owner_id)['ok']
        time.sleep(.7)
        _click_global(test, next(b for b in test.window(owner_id)['buttons'] if b['action'] == 'fullscreen'))
        test.until(lambda: test.window(owner_id)['fullscreen'] == 2, 'scrolling frame enters true fullscreen')
        test.check('Scrolling fullscreen hides the frame without using maximized mode',
                   not test.window(owner_id)['buttons'] and not test.window(owner_id)['maximized'])
        assert test.action('fullscreen', owner_id)['ok']
        test.until(lambda: test.window(owner_id)['fullscreen'] == 0 and bool(test.window(owner_id)['buttons']),
                   'scrolling fullscreen restores frame')
        test.check('Leaving fullscreen preserves the scrolling column width',
                   abs(_width(test, owner_id) - original_fraction) < .001)
        test.check('Single-app scrolling columns allow width but hide ineffective height resizing',
                   test.window(owner_id)['capabilities']['resizeHorizontal']
                   and not test.window(owner_id)['capabilities']['resizeVertical'])
        test.check('Scrolling reports separate native columns for both fixtures',
                   test.window(owner_id)['scrolling']['columnCount'] == 2
                   and test.window(owner_id)['scrolling']['columnIndex']
                   != test.window(other_id)['scrolling']['columnIndex'])
        time.sleep(.8)
        for preset, fraction in (('full', 1), ('85', .85), ('half', .5)):
            owner = test.window(owner_id)
            buttons = owner['buttons']
            test.check('Scrolling frame exposes column sizing without dwindle arrows (' + preset + ')',
                {'column-half','column-85','column-full'}.issubset({b['action'] for b in buttons})
                and not any(b['action'].startswith('tile-') for b in buttons))
            peer_width = _width(test, other_id)
            assert test.action('focus', other_id)['ok']
            _click_global(test, next(b for b in buttons if b['action'] == 'column-' + preset))
            test.until(lambda: abs(_width(test, owner_id) - fraction) < .001, 'direct column ' + preset)
            time.sleep(.7)
            test.check('Left frame sets column ' + preset + ' without changing its neighbor', abs(_width(test, other_id)-peer_width) < .001)
        _open_owner(test, owner_id)
        test.until(lambda: 'column-width-half'  in _visible_actions(test)
                   and 'column-width-85' in _visible_actions(test)
                   and 'column-width-full' in _visible_actions(test), 'scrolling manual width controls')
        test.check('Scrolling exposes manual Half width, 85%, and Full width controls')
        initial_width = test.window(owner_id)['width']
        other_width = _width(test, other_id)
        assert test.action('focus', other_id)['ok']
        _click_ui(test, 'column-width-full')
        test.until(lambda: abs(_width(test, owner_id) - 1) < .001
                   and not _menu(test)['busy'], 'full-width column action')
        test.until(lambda: test.window(owner_id)['width'] > initial_width * 1.7,
                   'full-width native client geometry')
        test.check('Full width resizes the captured column without maximizing or changing its neighbor',
                   abs(_width(test, other_id) - other_width) < .001
                   and not test.window(owner_id)['maximized']
                   and test.window(owner_id)['fullscreen'] == 0)
        full_width = test.window(owner_id)['width']
        assert test.action('focus', other_id)['ok']
        _click_ui(test, 'column-width-85')
        test.until(lambda: abs(_width(test, owner_id) - .85) < .001
                   and not _menu(test)['busy'], '85-percent column action')
        test.until(lambda: initial_width + 40 < test.window(owner_id)['width'] < full_width - 40,
                   '85-percent native client geometry lies between half and full')
        test.check('85% resizes the captured column between half and full without changing its neighbor',
                   _menu(test)['targetId'] == owner_id
                   and _menu(test)['lastActionId'] == owner_id
                   and abs(_width(test, other_id) - other_width) < .001
                   and not test.window(owner_id)['floating']
                   and not test.window(owner_id)['maximized']
                   and test.window(owner_id)['fullscreen'] == 0)
        _pointer_to_menu_header(test)
        test.shot('gooey-scrolling-85')
        _click_ui(test, 'column-width-half')
        test.until(lambda: abs(_width(test, owner_id) - .5) < .001
                   and not _menu(test)['busy'], 'half-width column action')
        test.until(lambda: test.window(owner_id)['width'] < full_width * .65,
                   'half-width native client geometry')
        test.check('Half width restores a regular tiled column by mouse',
                   not test.window(owner_id)['floating'] and not test.window(owner_id)['maximized'])
        test.check('Unknown width presets are rejected without changing the column',
                   not test.action('column-width', owner_id, 'invalid-preset')['ok']
                   and abs(_width(test, owner_id) - .5) < .001)
        test.shot('gooey-scrolling-widths')
        _check_visible_strip_bounds(test, 'half')
        _click_ui(test, 'layout-menu')
        test.until(lambda: 'column-center' in _visible_actions(test), 'scrolling navigation controls')
        test.check('Scrolling shows column navigation and omits dwindle split and swap controls',
                   not any(action == 'split' or action.startswith('swap-')
                           for action in _visible_actions(test))
                   and not test.action('split', owner_id)['ok']
                   and not test.action('swap', owner_id, 'l')['ok'])
        test.shot('gooey-scrolling-controls')

        # Full-width columns force a real tape move to reach the neighbor. With
        # follow_focus off, native navigation must still bring its target in view.
        _close(test)
        for original in originals:
            assert test.action('column-width', original['id'], 'full')['ok']
        ordered = sorted((test.window(w['id']) for w in originals),
                         key=lambda w: w['scrolling']['columnIndex'])
        first_id, last_id = [w['id'] for w in ordered]
        _open_owner(test, first_id, layout=True)
        _check_visible_strip_bounds(test, 'before-next', hidden_id=last_id)
        _click_ui(test, 'column-next')
        test.until(lambda: test.window(last_id)['focused'] and _fully_visible(test, last_id),
                   'next full-width column focused and visible')
        test.until(lambda: not _menu(test)['opened'], 'navigation closes owner menu')
        test.check('Next column reaches an offscreen window with follow-focus disabled')
        _check_visible_strip_bounds(test, 'after-next', hidden_id=first_id)
        _open_owner(test, last_id, layout=True)
        test.check('The last column disables Next and rejects advancing beyond the tape',
                   not test.window(last_id)['capabilities']['columnNext']
                   and any(b['action'] == 'column-next' and b['visible'] and not b['enabled']
                           for b in _menu(test)['buttons'])
                   and not test.action('column-focus', last_id, 'next')['ok'])
        _click_ui(test, 'column-previous')
        test.until(lambda: test.window(first_id)['focused'] and _fully_visible(test, first_id),
                   'previous full-width column focused and visible')
        test.check('Previous column returns across all fixture windows by mouse')

        _open_owner(test, first_id)
        _configure(test, 'dwindle', original_scrolling)
        test.until(lambda: all(test.window(w['id'])['layout'] == 'dwindle'
                               for w in originals), 'return to dwindle')
        test.until(lambda: 'column-width-half' not in _visible_actions(test)
                   and 'column-width-85' not in _visible_actions(test)
                   and 'column-width-full' not in _visible_actions(test),
                   'open menu adapts back to dwindle')
        test.check('An open menu drops scrolling controls when the layout changes to dwindle',
                   not test.window(first_id)['capabilities']['columnWidth']
                   and not test.action('column-center', first_id)['ok'])
    finally:
        _close(test)
        _configure(test, original_layout, original_scrolling)
        for original in originals:
            current = test.window(original['id'])
            if not current:
                continue
            if current['workspaceName'] != original['workspaceName']:
                assert test.action('workspace', original['id'], '0 ' + original['workspaceName'])['ok']
            if current['floating'] != original['floating']:
                assert test.action('float', original['id'])['ok']
        if test.window(focus_id):
            assert test.action('focus', focus_id)['ok']
        test.until(lambda: _config_value(test, 'general:layout', 'string') == original_layout,
                   'restore original layout setting')
        test.check('Layout checks restore the original scrolling preferences',
                   all(_config_value(test, 'scrolling:' + key, kind) == original_scrolling[key]
                       for key, kind in setting_types.items()))
    return []

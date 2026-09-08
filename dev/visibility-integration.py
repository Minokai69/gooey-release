"""Regression for invisible native strip input, only inside dev/run integration.

True fullscreen and decorate=false hide the decoration. Former strip coordinates
must then deliver pointer events to the application, including drag gestures.
The named test rule is disabled in finally; all fixture state is restored.
"""
import json
import os
import time


def _close(test):
    test.ipc('gooey.launcher', 'close')
    test.ipc('gooey.window-tools', 'close')


def _fullscreen(test, address, mode, enabled):
    test.run('hyprctl', 'dispatch', 'hl.dsp.window.fullscreen({ window='
             + json.dumps('address:' + address) + ', mode=' + json.dumps(mode)
             + ', action=' + json.dumps('set' if enabled else 'unset')
             + ', layout_aware=false })')


def _move(test, address, x, y):
    test.run('hyprctl', 'dispatch', 'hl.dsp.window.move({ window='
             + json.dumps('address:' + address) + ', x=' + str(round(x))
             + ', y=' + str(round(y)) + ', relative=false })')


def _restore_float_geometry(test, original):
    test.run('hyprctl', 'dispatch', 'hl.dsp.window.resize({ window='
             + json.dumps('address:' + original['address'])
             + ', x=' + str(round(original['width']))
             + ', y=' + str(round(original['height'])) + ', relative=false })')
    _move(test, original['address'], original['x'], original['y'])


def _pointer(test, x, y, drag=False):
    monitors = json.loads(test.run('hyprctl', '-j', 'monitors'))
    left = min(m['x'] for m in monitors)
    top = min(m['y'] for m in monitors)
    width = round(max(m['x'] + m['width'] / m['scale'] for m in monitors) - left)
    height = round(max(m['y'] + m['height'] / m['scale'] for m in monitors) - top)
    x, y = round(x - left), round(y - top)
    steps = ['move', x, y, width, height, 'sleep', 100, 'down', 'sleep', 120]
    if drag:
        steps.extend(['move', x + 7, y + 4, width, height, 'sleep', 100,
                      'move', x + 14, y + 8, width, height, 'sleep', 120])
    steps.extend(['up'])
    test.run(test.ROOT / 'work/input/gooey-input', *steps)
    time.sleep(.3)


def _fixture(test, title):
    data = json.loads(test.run('qs', 'ipc', '-p', test.ROOT / 'dev/fixtures',
                               'call', 'fixtures', 'status'))
    return next(w for w in data['windows'] if w['title'] == title)


def _geometry(window):
    return tuple(window[key] for key in ('x', 'y', 'width', 'height'))


def _settled_window(test, owner_id):
    previous, since = None, 0
    def settled():
        nonlocal previous, since
        window = test.window(owner_id)
        geometry = _geometry(window)
        if geometry != previous:
            previous, since = geometry, time.monotonic()
            return None
        return window if time.monotonic() - since >= .6 else None
    return test.until(settled, 'client geometry settles after decoration changes')


def _probe_hidden(test, owner_id, former_buttons, label):
    win = _settled_window(test, owner_id)
    test.check(label + ' releases native strip space and input targets',
               win['decorationVisible'] is False and not win['buttons']
               and win['reservedTop'] == 0
               and win['anchor']['width'] == 0 and win['anchor']['height'] == 0)
    geometry = _geometry(win)
    header = _fixture(test, win['title'])['headerRect']
    for button in former_buttons:
        x = button['x'] + button['width'] / 2
        y = button['y'] + button['height'] / 2
        # This must exercise actual client content, not empty desktop above it.
        assert win['x'] < x < win['x'] + header['width'] \
            and win['y'] < y < win['y'] + header['height'], \
            label + ' former strip point must lie in the fixture header'
        count = _fixture(test, win['title'])['headerClicks']
        _pointer(test, x, y)
        test.until(lambda: _fixture(test, win['title'])['headerClicks'] == count + 1,
                   label + ' former ' + button['action'] + ' reaches the client')
    test.check(label + ' passes former menu and grip clicks to the application',
               not test.status('gooey.window-tools')['opened'])
    for action in ('drag-grip', 'resize-grip'):
        grip = next(b for b in former_buttons if b['action'] == action)
        count = _fixture(test, win['title'])['headerClicks']
        _pointer(test, grip['x'] + grip['width'] / 2,
                 grip['y'] + grip['height'] / 2, drag=True)
        test.until(lambda: _fixture(test, win['title'])['headerClicks'] == count + 1,
                   label + ' former ' + action + ' delivers the press and release')
    test.check(label + ' cannot start an invisible native move or resize grab',
               not test.status('gooey.window-tools')['opened']
               and all(abs(a - b) <= 1 for a, b in zip(geometry, _geometry(test.window(owner_id)))))


def run_checks(test):
    assert os.environ.get('OMARCHY_MOUSE_PREVIEW') == '1'
    assert os.environ.get('GOOEY_MODE') == 'integration'
    assert os.environ.get('WAYLAND_DISPLAY') not in (None, '', '/run/host-wayland')
    assert os.environ.get('OMARCHY_PATH') == '/opt/omarchy-mouse-shell/base'
    _close(test)
    original = next((dict(w) for w in test.state()['windows']
                     if w['title'] == 'Gooey · Notes' and not w['shelved'] and not w['grouped']), None)
    assert original and original['fullscreen'] == 0, 'A regular Notes fixture is required'
    owner_id, address = original['id'], original['address']
    focus_id = next((w['id'] for w in test.state()['windows'] if w['focused']), owner_id)
    peer_ids = [w['id'] for w in test.state()['windows']
                if w['id'] != owner_id and w['title'] in ('Gooey · Notes', 'Gooey · Files')
                and w['monitor'] == original['monitor']
                and w['workspaceId'] == original['workspaceId']
                and w['floating'] and not w['shelved'] and not w['grouped']]
    tiled_peers = []
    rule_created = False
    try:
        # The earlier launcher shortcut check may leave Files floating across
        # Notes. Tile those peer fixtures temporarily so a genuine application
        # overlay cannot intercept the no-decoration header probes.
        for peer_id in peer_ids:
            peer = dict(_settled_window(test, peer_id))
            assert peer['fullscreen'] == 0, 'A regular peer fixture is required'
            tiled_peers.append(peer)
            assert test.action('float', peer_id)['ok']
            test.until(lambda: not test.window(peer_id)['floating'], 'tile interfering peer fixture')
        # Tiled clients regain the strip's reserved area when decorations are
        # disabled, making those former hit targets observable in real content.
        if original['floating']:
            assert test.action('float', owner_id)['ok']
            test.until(lambda: not test.window(owner_id)['floating'], 'tiled visibility fixture')
        assert test.action('focus', owner_id)['ok']
        _fullscreen(test, address, 'maximized', True)
        test.until(lambda: test.window(owner_id)['maximized']
                   and test.window(owner_id)['decorationVisible'], 'maximized eligible strip')
        maximized = _settled_window(test, owner_id)
        former_maximized_buttons = [dict(b) for b in maximized['buttons']]
        test.check('Maximize keeps the named strip above the application and interactive',
                   {b['action'] for b in former_maximized_buttons} == {'drag-grip', 'menu-actions', 'resize-grip', 'shelf', 'menu-workspace', 'fullscreen', 'close'}
                   and maximized['appName'] and maximized['reservedTop'] > 0
                   and maximized['anchor']['width'] > 0
                   and maximized['anchor']['y'] + maximized['anchor']['height'] <= maximized['y'] + 1)
        menu_button = next(b for b in former_maximized_buttons if b['action'] == 'menu-actions')
        _pointer(test, menu_button['x'] + menu_button['width'] / 2,
                 menu_button['y'] + menu_button['height'] / 2)
        test.until(lambda: test.status('gooey.window-tools')['opened']
                   and test.status('gooey.window-tools')['targetId'] == owner_id,
                   'maximized native menu still opens')
        _fullscreen(test, address, 'fullscreen', True)
        test.until(lambda: test.window(owner_id)['fullscreen'] == 2
                   and not test.window(owner_id)['decorationVisible'], 'true fullscreen removes strip')
        test.until(lambda: not test.status('gooey.window-tools')['opened'],
                   'fullscreen dismisses the previously open owner menu')
        test.check('Entering fullscreen closes the owner menu with its hidden strip')
        # Maximized's strip sits in reserved space at the work-area top. True
        # fullscreen returns that space to the client, so these points become
        # part of its actual application header.
        _probe_hidden(test, owner_id, former_maximized_buttons, 'True fullscreen')
        _fullscreen(test, address, 'fullscreen', False)
        test.until(lambda: test.window(owner_id)['fullscreen'] == 0
                   and test.window(owner_id)['decorationVisible'], 'fullscreen exit restores strip')
        before_rule = _settled_window(test, owner_id)
        former_buttons = [dict(b) for b in before_rule['buttons']]
        assert not before_rule['floating'] and before_rule['reservedTop'] > 0 \
            and before_rule['anchor']['y'] + before_rule['anchor']['height'] <= before_rule['y'] + 1, \
            'No-decoration probe needs a tiled strip in reserved space'
        title_pattern = '^Gooey · Notes$'
        test.run('hyprctl', 'eval', '_gooey_visibility_test_rule = hl.window_rule({ '
                 'name="gooey-visibility-integration", match={ title='
                 + json.dumps(title_pattern, ensure_ascii=False) + ' }, decorate=false })')
        rule_created = True
        test.until(lambda: not test.window(owner_id)['decorationVisible'], 'decorate=false removes strip')
        _probe_hidden(test, owner_id, former_buttons, 'Disabled decorations')
    finally:
        _close(test)
        if rule_created:
            test.run('hyprctl', 'eval', '_gooey_visibility_test_rule:set_enabled(false); '
                     '_gooey_visibility_test_rule = nil')
        if test.window(owner_id):
            _fullscreen(test, address, 'fullscreen', False)
            _fullscreen(test, address, 'maximized', False)
            if test.window(owner_id)['floating'] != original['floating']:
                assert test.action('float', owner_id)['ok']
            if original['floating']:
                _restore_float_geometry(test, original)
            test.until(lambda: test.window(owner_id)['decorationVisible']
                       and bool(test.window(owner_id)['buttons']), 'restore eligible fixture strip')
        for peer in tiled_peers:
            if not test.window(peer['id']):
                continue
            if test.window(peer['id'])['floating'] != peer['floating']:
                assert test.action('float', peer['id'])['ok']
            _restore_float_geometry(test, peer)
            _settled_window(test, peer['id'])
        if test.window(focus_id):
            assert test.action('focus', focus_id)['ok']
        test.check('Visibility checks restore the fixture and disable their temporary rule',
                   test.window(owner_id)['fullscreen'] == 0
                   and test.window(owner_id)['floating'] == original['floating']
                   and all(test.window(peer['id'])['floating'] == peer['floating']
                           and test.window(peer['id'])['workspaceId'] == peer['workspaceId']
                           and all(abs(a - b) <= 1 for a, b in zip(
                               _geometry(test.window(peer['id'])), _geometry(peer)))
                           for peer in tiled_peers))
    return []

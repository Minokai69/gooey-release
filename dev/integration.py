#!/usr/bin/env python3
"""Exercise the actual compositor and mouse input, only inside dev/run."""
import json
import base64
import importlib.util
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time

assert os.environ.get('OMARCHY_MOUSE_PREVIEW') == '1'
assert os.environ['WAYLAND_DISPLAY'] != '/run/host-wayland'
ROOT = Path(os.environ['GOOEY_ROOT'])
CACHE = Path(os.environ['XDG_CACHE_HOME'])
SHELL = os.environ['OMARCHY_PATH'] + '/shell'
checks = []
limitations = []


def run(*args):
    p = subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=8)
    if p.returncode:
        raise RuntimeError(f'{args}: {p.stdout} {p.stderr}')
    return p.stdout.strip()


def until(fn, label, timeout=12):
    end = time.monotonic() + timeout
    error = None
    while time.monotonic() < end:
        try:
            value = fn()
            if value:
                return value
        except (RuntimeError, ValueError, KeyError) as exc:
            error = exc
        time.sleep(.15)
    raise AssertionError(f'Timed out: {label}; {error}')


def ipc(target, method, *args):
    return run('qs', 'ipc', '-p', SHELL, 'call', target, method, *args)


def state():
    return json.loads(run('hyprctl', 'gooey:state'))


def status(target='gooey.launcher'):
    return json.loads(ipc(target, 'status'))


def check(label, condition=True):
    assert condition, label
    checks.append(label)
    print('PASS:', label, flush=True)


def shot(name):
    time.sleep(.5)
    run('grim', CACHE / (name + '.png'))


def window(window_id):
    return next((w for w in state()['windows'] if w['id'] == window_id), None)


def action(name, window_id, args='', instance=None):
    result = json.loads(run('hyprctl', 'gooey:window',
        f' --instance {instance or state()["instance"]} {name} {window_id} {args}'))
    return result


def pointer(*steps):
    run(ROOT / 'work/input/gooey-input', *steps)
    time.sleep(.35)


def point(rect):
    return round(rect['x'] + rect['width']/2), round(rect['y'] + rect['height']/2)


def click(rect):
    x, y = point(rect)
    # The Wayland preview may be resized by the parent desktop, including after
    # a disposable output is removed. Absolute pointer normalization must use
    # its live desktop dimensions rather than the requested startup mode.
    monitors = json.loads(run('hyprctl', '-j', 'monitors'))
    left, top = min(m['x'] for m in monitors), min(m['y'] for m in monitors)
    width = round(max(m['x'] + m['width'] / m['scale'] for m in monitors) - left)
    height = round(max(m['y'] + m['height'] / m['scale'] for m in monitors) - top)
    pointer('move', x-left, y-top, width, height, 'sleep', 80, 'down', 'sleep', 80, 'up')


def native_click(window_id, name):
    time.sleep(.5)
    win = window(window_id)
    click(next(b for b in win['buttons'] if b['action'] == name))


def ui_button(name, destination=None, window_id=None):
    def find():
        data = status('gooey.window-tools')
        return next((b for b in data.get('buttons', []) if b['action'] == name
            and (destination is None or b['destination'] == destination)
            and (window_id is None or b['windowId'] == window_id)
            and b['visible'] and b['enabled']), None)
    return until(find, f'visible enabled UI action {name} {destination}')


def window_menu_click(window_id, name, leave_open=False):
    ipc('gooey.window-tools', 'close')
    native_click(window_id, 'menu-actions')
    until(lambda: status('gooey.window-tools')['opened'] and status('gooey.window-tools')['targetId']==window_id, 'captured strip owner')
    click(ui_button(name))
    if not leave_open:
        ipc('gooey.window-tools', 'close')


def exercise_strip_geometry():
    """Prove native reservation, centered placement, and stable hover geometry."""
    companion = Path(os.environ['HOME']) / '.local/share/gooey/current/companion/gooey.so'
    def geometry():
        return {w['address']: w['at']+w['size'] for w in json.loads(run('hyprctl','-j','clients'))}
    def settled_geometry():
        last, equal = None, 0
        def settled():
            nonlocal last, equal
            current = geometry()
            equal = equal + 1 if current == last else 0
            last = current
            return current if equal >= 6 else None
        return until(settled, 'client geometry settles after startup or decoration reload')
    before = settled_geometry()
    reserved = state()['reservedTop']
    unloaded = False
    try:
        run('hyprctl', 'plugin', 'unload', companion)
        unloaded = True
        without = settled_geometry()
        (CACHE / 'gooey-strip-geometry.json').write_text(json.dumps({'with':before,'without':without}, indent=2))
        check('Hyprland reserves one strip height without changing the outer tile',
              reserved > 0 and before.keys() == without.keys() and all(
                  abs(before[k][0] - without[k][0]) <= 1
                  and abs(before[k][2] - without[k][2]) <= 1
                  and abs(before[k][1] - without[k][1] - reserved) <= 1
                  and abs(without[k][3] - before[k][3] - reserved) <= 1 for k in before))
    finally:
        if unloaded: run('hyprctl', 'plugin', 'load', companion)
    until(lambda: state()['theme']['ready'] and status('gooey.window-tools')['ready'], 'same-instance theme recovery')
    after = settled_geometry()
    check('Reattaching strips restores the same client geometry', before==after)
    current = state()
    launcher = status()
    desktop_bar_height = launcher['bar']['height']
    check('Each strip spans the full app width above content and below the desktop bar', all(
        {'drag-grip','menu-actions','resize-grip','shelf','menu-workspace','fullscreen','close'}.issubset({b['action'] for b in w['buttons']})
        and abs(w['anchor']['x'] + w['anchor']['width']/2 - w['x'] - w['width']/2) <= 1
        and w['anchor']['y'] + w['anchor']['height'] <= w['y'] + 1
        and w['anchor']['y'] >= desktop_bar_height - 1
        and w['width'] - 1 <= w['anchor']['width'] <= w['width'] + 5
        and bool(w['appName']) for w in current['windows']))
    for w in current['windows']:
        grip = next(b for b in w['buttons'] if b['action'] == 'resize-grip')
        check('Resize grip sits beside the central app label',
              abs(grip['x'] + grip['width']/2 - (w['anchor']['x'] + w['anchor']['width']/2)) < w['anchor']['width'] / 4)
        ordered = sorted(w['buttons'], key=lambda b: b['x'])
        check('Centered resize grip has its own non-overlapping pointer target',
              all(a['x'] + a['width'] <= b['x'] + .01 for a,b in zip(ordered, ordered[1:])))
    first, second = current['windows']
    for target, other in ((first, second), (second, first)):
        pointer('move', round(target['x'] + target['width']/2), round(target['y'] + 90), 1280, 800)
        until(lambda: window(target['id'])['controlsShown'] and not window(other['id'])['controlsShown'],
              'controls follow the pointer into the owning client')
    check('Pointer context reveals the owner controls without moving either tile', geometry() == after)
    for win in current['windows']:
        def fixture():
            return next(w for w in json.loads(run('qs','ipc','-p',ROOT/'dev/fixtures','call','fixtures','status'))['windows'] if w['title']==win['title'])
        successful = 0
        for sample in fixture()['headerPoints']:
            live=window(win['id']); x,y=live['x']+sample['x'],live['y']+sample['y']; tab=live['anchor']
            if tab['x']<=x<=tab['x']+tab['width'] and tab['y']<=y<=tab['y']+tab['height']:
                continue
            count=fixture()['headerClicks']
            pointer('move',round(x),round(y),1280,800,'down','sleep',50,'up')
            until(lambda: fixture()['headerClicks']==count+1,'application receives header click')
            successful+=1
        check('Application header below its strip receives pointer clicks: '+win['appId'],successful>=2)
    check('Application header clicks do not open a window menu', not status('gooey.window-tools')['opened'])


def exercise_theme():
    """Use Omarchy's actual applyTheme IPC and watched user override hierarchy."""
    theme_dir=Path(os.environ['HOME'])/'.local/state/omarchy/current/theme'
    original_colors=(theme_dir/'colors.toml').read_text()
    original_shell=(theme_dir/'shell.toml').read_text() if (theme_dir/'shell.toml').exists() else ''
    user_path=Path(os.environ['HOME'])/'.config/omarchy/shell.toml'
    original_user=user_path.read_text() if user_path.exists() else None
    def save_user(text):
        if text is None:
            user_path.unlink(missing_ok=True)
        else:
            temp=user_path.with_suffix('.corner-next');temp.write_text(text);temp.replace(user_path)
    def apply(colors,shell_values):
        ipc('shell','applyTheme',base64.b64encode(colors.encode()).decode(),base64.b64encode(shell_values.encode()).decode())
    def theme(): return state()['theme']
    ipc('gooey.launcher','close')
    ipc('gooey.window-tools','close')
    start=theme()
    try:
        bad=json.loads(run('hyprctl','gooey:theme',' --instance stale background ffffffff'))
        check('Theme updates refuse a stale compositor identity',not bad['ok'] and theme()['revision']==start['revision'])
        bad=json.loads(run('hyprctl','gooey:theme',' --instance '+state()['instance']+' height nan'))
        check('Malformed theme updates leave the palette unchanged',not bad['ok'] and theme()['revision']==start['revision'])
        save_user('[bar]\nsize-horizontal = 30\nsize-vertical = 34\n[font]\nbase-size = 12\n')
        light='background = "#faf4ed"\nforeground = "#575279"\naccent = "#907aa9"\nmuted = "#797593"\ncolor1 = "#b4637a"\n'
        shell_values='[bar]\nbackground = "#fffaf3"\ntext = "#575279"\nsize-horizontal = 26\n[popups]\nbackground = "#faf4ed"\ntext = "#575279"\n[controls]\nhover-cursor-color = "accent"\nhover-cursor-fill-alpha = 0.2\n'
        apply(light,shell_values)
        until(lambda: theme()['background']=='fffffaf3' and theme()['foreground']=='ff575279' and theme()['height']==30,'light palette and user size override')
        check('Native strip follows resolved light bar colors through Omarchy theme IPC',theme()['accent']=='ff907aa9' and theme()['danger']=='ffb4637a')
        check('User bar thickness overrides the theme thickness',theme()['height']==30)
        check('Native hover state follows Omarchy control tokens',theme()['hover']=='33907aa9')
        check('Native app-name font follows the resolved Omarchy font',
              theme()['fontFamily'] == status('gooey.window-tools')['theme']['fontFamily']
              and theme()['fontSize'] == status('gooey.window-tools')['theme']['fontSize'])
        owner=state()['windows'][0]['id']
        native_click(owner,'menu-actions')
        shot('gooey-corner-light')
        ipc('gooey.window-tools','close')
        ipc('gooey.launcher','summon','root')
        until(lambda: status()['visible'] and status()['anchorReady'], 'light launcher ready')
        shot('gooey-launcher-light')
        ipc('gooey.launcher','close')
        save_user('[bar]\nsize-horizontal = 30\nsize-vertical = 34\n[font]\nbase-size = 18\n')
        until(lambda: theme()['height']==45,'font-scaled Omarchy bar thickness')
        # The theme ack precedes native layout/position animations. A floating
        # strip may briefly be outside the new usable area while clearance runs.
        def enlarged_strips():
            snapshot = state()
            (CACHE / 'gooey-scaled-strip-state.json').write_text(json.dumps(snapshot, indent=2))
            return snapshot if all(abs(w['anchor']['height']-45)<=1
                for w in snapshot['windows']) else None
        enlarged = until(enlarged_strips, 'reserved strips settle at the scaled bar height')
        check('Font scaling changes strip thickness and its app-name font with Omarchy',
              enlarged['theme']['fontSize'] > start['fontSize'])
        # The launcher chord fixture is floating over the tiled app. Its strip
        # must retain topmost ownership even where the two strips overlap.
        floating_owner = next(w for w in enlarged['windows'] if w['floating'])
        floating_id = floating_owner['id']
        time.sleep(.7)
        grip = next(b for b in window(floating_id)['buttons'] if b['action'] == 'menu-actions')
        x, y = point(grip)
        pointer('move', x, y, 1280, 800)
        until(lambda: window(floating_id)['controlsShown'], 'floating strip owns hover above another tile')
        native_click(floating_id, 'menu-actions')
        until(lambda: status('gooey.window-tools')['opened']
              and status('gooey.window-tools')['targetId'] == floating_id,
              'topmost floating strip opens its own actions')
        check('Floating strip retains pointer ownership above an underlying tile')
        ipc('gooey.window-tools', 'close')
        shot('gooey-corner-large')
        dark='background = "#181818"\nforeground = "#eeeeee"\naccent = "#99ccff"\nmuted = "#999999"\ncolor1 = "#ff7777"\n'
        apply(dark,'')
        until(lambda: theme()['background']=='ff181818' and theme()['foreground']=='ffeeeeee','dark palette')
        check('Native palette updates live without reloading the companion',theme()['revision']>start['revision'])
    finally:
        save_user(original_user)
        apply(original_colors,original_shell)
        until(lambda: theme()['background']==start['background'] and theme()['height']==start['height'],'restore original theme and size')
    check('Theme test restores original palette and bar sizing')


def exercise_windows(baseline):
    a, b = [w['id'] for w in baseline['windows']]
    check('Old compositor identities are rejected', not action('close', a, instance='stale')['ok'])
    check('Missing windows are rejected', not action('close', '9999999999')['ok'])
    for name in ('resize-grip', 'fullscreen', 'shelf', 'menu-workspace', 'menu-actions', 'tile-wider', 'close', 'drag-grip'):
        button = next(b for b in window(a)['buttons'] if b['action'] == name)
        x, y = point(button)
        pointer('move', x, y, 1280, 800)
        hint = until(lambda: (lambda t: t if t and t['visible'] and t['action'] == name else None)(
            status('gooey.window-tools').get('tooltip')), 'hover tooltip ' + name)
        check('Hover explains ' + name, bool(hint['text']))
        if name == 'resize-grip':
            check('Resize tooltip explains click and drag', 'Click' in hint['text'] and 'drag' in hint['text'])
            shot('gooey-tooltip')
    pointer('move', 640, 400, 1280, 800)
    until(lambda: not status('gooey.window-tools')['tooltip']['visible'], 'tooltip hides away from controls')
    check('Hover tooltips do not open an action menu', not status('gooey.window-tools')['opened'])
    sizes = {w['id']: w['width'] for w in state()['windows']}
    frame = window(a)
    left = [button for button in frame['buttons'] if button['action'].startswith('tile-')]
    check('Side-by-side dwindle tiles expose only horizontal sizing icons', {button['action'] for button in left} == {'tile-narrower', 'tile-wider'}
          and all(button['x'] + button['width'] < frame['x'] + frame['width']/2 for button in left)
          and not any(button['action'].startswith('column-') for button in frame['buttons']))
    action('focus', b)
    native_click(a, 'tile-wider')
    until(lambda: window(a)['width'] > sizes[a] + 175, 'direct wider tile')
    time.sleep(.7)
    check('Left tile sizing changes its owner and shares space with the neighboring tile', window(b)['width'] < sizes[b] - 175)
    native_click(a, 'tile-narrower')
    time.sleep(.7)
    check('Opposite tile sizing restores the original widths', all(abs(window(key)['width'] - value) <= 1 for key,value in sizes.items()))
    for tiled in sorted(state()['windows'], key=lambda w: w['x']):
        owner = tiled['id']
        side = 'left' if tiled['x'] < 640 else 'right'
        before = window(owner)
        x, y = point(next(r for r in before['buttons'] if r['action'] == 'resize-grip'))
        delta = 80 if side == 'left' else -80
        pointer('move', x, y, 1280, 800, 'down', 'sleep', 150,
            'move', x + delta//8, y, 1280, 800, 'sleep', 80,
            'move', x + delta//2, y, 1280, 800, 'sleep', 80,
            'move', x + delta, y, 1280, 800, 'sleep', 150, 'up')
        time.sleep(.7)
        check('Resize grip expands the ' + side + ' tile at its interior split',
              window(owner)['width'] > before['width'] + 35)
        check('Tiled resize drag does not open the menu: ' + side,
              not status('gooey.window-tools')['opened'])
        action('resize', owner, str(round(before['width'] - window(owner)['width'])) + ' 0')
        time.sleep(.7)
    action('focus', b)
    native_click(a, 'resize-grip')
    until(lambda: status('gooey.window-tools')['opened']
          and status('gooey.window-tools')['targetId'] == a
          and status('gooey.window-tools')['kind'] == 'layout', 'resize short-click opens the owner size controls')
    check('Clicking the diagonal resize icon opens layout and size controls for its owner',
          any(button['action'] == 'resize' and button['visible'] and button['enabled']
              for button in status('gooey.window-tools')['buttons']))
    check('Resize menu hides height controls for a full-height tile',
          {button['text'] for button in status('gooey.window-tools')['buttons']
           if button['action'] == 'resize' and button['visible']} == {'Narrower', 'Wider'})
    shot('gooey-resize')
    ipc('gooey.window-tools', 'close')
    action('focus', b)
    native_click(a, 'shelf')
    until(lambda: window(a)['shelved'], 'owner sent to Shelf')
    check('Clicking an inactive window Shelf button affects only that owner', not window(b)['shelved'])
    until(lambda: not window(b)['capabilities']['resizeHorizontal']
          and not window(b)['capabilities']['resizeVertical'], 'single tile has no resize split')
    check('A lone dwindle tile hides both axis button pairs',
          not any(button['action'].startswith('tile-') for button in window(b)['buttons']))
    ipc('gooey.window-tools', 'shelf')
    until(lambda: status('gooey.window-tools')['shelfCount'] == 1, 'Shelf list')
    shot('gooey-shelf')
    click(ui_button('take-off-shelf', window_id=a))
    until(lambda: not window(a)['shelved'], 'Shelf restore')
    check('Shelf list restores its selected window by mouse', window(a)['workspaceId'] == 1)
    ipc('gooey.window-tools', 'close')
    window_menu_click(a, 'shelf')
    until(lambda: window(a)['shelved'], 'Shelf second send')
    run('hyprctl', 'gooey:shelf')
    time.sleep(.7)
    window_menu_click(a, 'shelf')
    until(lambda: not window(a)['shelved'], 'native Shelf restore')
    check('Window menu reverses into Take off shelf')
    # Hyprland may close an empty special workspace automatically.
    special = json.loads(run('hyprctl', '-j', 'monitors'))[0]['specialWorkspace']['id']
    if special: run('hyprctl', 'gooey:shelf')
    time.sleep(.7)
    native_click(a, 'menu-workspace')
    until(lambda: status('gooey.window-tools')['opened'] and status('gooey.window-tools')['kind'] == 'workspace', 'workspace picker')
    picker = status('gooey.window-tools')
    trigger = next(b for b in window(a)['buttons'] if b['action'] == 'menu-workspace')
    expected_x = max(12, min(trigger['x'] + trigger['width'] - picker['card']['width'], 1280 - picker['card']['width'] - 12))
    check('Workspace popup anchors to its direct frame button', abs(picker['card']['x'] - expected_x) <= 1)
    shot('gooey-workspaces')
    check('Workspace picker starts with Follow window off', not status('gooey.window-tools')['followWindow'])
    action('focus', b)
    click(ui_button('workspace', destination='2'))
    until(lambda: window(a)['workspaceId'] == 2, 'workspace mouse move')
    check('Workspace click retains captured owner and leaves current workspace', window(b)['workspaceId'] == 1 and state()['monitors'][0]['activeWorkspaceId'] == 1)
    check('Named workspace accepts spaces safely', action('workspace', a, '0 name:Design desk')['ok'])
    until(lambda: window(a)['workspaceName'] == 'name:Design desk', 'named workspace')
    check('Named workspace has its actual negative identity', window(a)['workspaceId'] < 0)
    action('workspace', a, '0 1')
    time.sleep(.7)
    window_menu_click(a, 'workspace-menu', leave_open=True)
    click(ui_button('follow-window'))
    until(lambda: status('gooey.window-tools')['followWindow'], 'Follow switch enabled')
    click(ui_button('workspace', destination='2'))
    until(lambda: window(a)['workspaceId']==2 and state()['monitors'][0]['activeWorkspaceId']==2, 'Follow destination')
    check('Follow switch moves the selected window and changes workspace', window(b)['workspaceId']==1)
    action('workspace', a, '1 1')
    time.sleep(.7)
    window_menu_click(a, 'float')
    until(lambda: window(a)['floating'], 'float toolbar action')
    check('Float button uses native floating state', not window(b)['floating'])
    time.sleep(.7)
    floating = window(a)
    run('hyprctl', 'dispatch', 'hl.dsp.window.move({ window='
        + json.dumps('address:' + floating['address'])
        + ', x=180, y=8, relative=false })')
    bar_height = status()['bar']['height']
    until(lambda: window(a)['decorationVisible']
          and window(a)['anchor']['y'] >= bar_height - 1,
          'floating strip clears the desktop bar through native position adjustment')
    time.sleep(.7)
    corrected = window(a)
    check('Floating clearance exposes the strip above content without resizing the app',
          abs(corrected['x'] - 180) <= 1
          and corrected['anchor']['y'] + corrected['anchor']['height'] <= corrected['y'] + 1
          and abs(corrected['width'] - floating['width']) <= 1
          and abs(corrected['height'] - floating['height']) <= 1)
    native_click(a, 'resize-grip')
    until(lambda: status('gooey.window-tools')['opened']
          and status('gooey.window-tools')['kind'] == 'layout', 'floating size menu opens by short-click')
    wider = until(lambda: next((button for button in status('gooey.window-tools')['buttons']
        if button['action'] == 'resize' and button['text'] == 'Wider'
        and button['visible'] and button['enabled']), None), 'visible Wider control')
    click(wider)
    until(lambda: window(a)['width'] >= corrected['width'] + 190, 'Wider changes the selected floating app')
    check('Resize menu changes the selected app width through native Hyprland sizing')
    ipc('gooey.window-tools', 'close')
    time.sleep(.7)
    before = window(a)
    x, y = point(next(r for r in before['buttons'] if r['action']=='drag-grip'))
    pointer('move', x, y, 1280, 800, 'down', 'sleep', 150,
        'move', x+10, y+10, 1280, 800, 'sleep', 80,
        'move', x+45, y+35, 1280, 800, 'sleep', 80,
        'move', x+90, y+70, 1280, 800, 'sleep', 150, 'up')
    after = window(a)
    check('Holding the app-name region drags through Hyprland', abs(after['x']-before['x']) > 50 or abs(after['y']-before['y']) > 40)
    before = window(a)
    grip = next(r for r in before['buttons'] if r['action']=='resize-grip')
    x,y = point(grip)
    pointer('move', x,y,1280,800,'down','sleep',150,
        'move',x+10,y+10,1280,800,'sleep',80,
        'move',x+35,y+25,1280,800,'sleep',80,
        'move',x+65,y+45,1280,800,'sleep',150,'up')
    after = window(a)
    check('Resize grip uses Hyprland resizing', abs(after['width']-before['width']) > 20 or abs(after['height']-before['height']) > 20)
    check('Dragging Resize does not also open its click menu', not status('gooey.window-tools')['opened'])
    # Keep the enlarged floating size from leaking into later display fixtures.
    resized = window(a)
    assert action('resize', a, str(round(corrected['width'] - resized['width']))
                  + ' ' + str(round(corrected['height'] - resized['height'])))['ok']
    time.sleep(.7)
    window_menu_click(a, 'float')
    until(lambda: not window(a)['floating'], 'retile')
    native_click(a, 'menu-actions')
    until(lambda: status('gooey.window-tools')['opened'], 'tiling menu')
    shot('gooey-actions')
    ipc('gooey.window-tools', 'close')
    native_click(a, 'fullscreen')
    until(lambda: window(a)['fullscreen'] == 2, 'direct true fullscreen')
    check('Fullscreen button uses Super+F mode, not maximized mode', not window(a)['maximized'])
    check('True fullscreen hides the attached strip', not window(a)['buttons'])
    assert action('fullscreen', a)['ok']
    until(lambda: window(a)['fullscreen'] == 0 and bool(window(a)['buttons']), 'fullscreen restore')
    check('Fullscreen restores the native tiled state and controls', not window(a)['floating'])
    time.sleep(.7)
    native_click(a, 'menu-actions')
    click(ui_button('layout-menu'))
    click(ui_button('split'))
    until(lambda: status('gooey.window-tools')['lastAction']=='split' and not status('gooey.window-tools')['busy'], 'split action acknowledged')
    check('Change split accepted by dwindle', status('gooey.window-tools')['lastActionMessage'] == '')
    split_setting = json.loads(run('hyprctl', '-j', 'getoption', 'dwindle:preserve_split'))
    preserve_split = split_setting.get('bool', split_setting.get('int', False))
    try:
        run('hyprctl', 'eval', 'hl.config({ dwindle={ preserve_split=true } })')
        if not window(a)['capabilities']['resizeVertical']:
            action('split', a)
        until(lambda: window(a)['capabilities']['resizeVertical']
              and not window(a)['capabilities']['resizeHorizontal'], 'stacked tile resize axes update')
        check('Stacked dwindle tiles expose only vertical sizing icons',
              {button['action'] for button in window(a)['buttons'] if button['action'].startswith('tile-')}
              == {'tile-shorter', 'tile-taller'})
        until(lambda: {button['text'] for button in status('gooey.window-tools')['buttons']
               if button['action'] == 'resize' and button['visible']} == {'Shorter', 'Taller'},
              'open resize menu follows the vertical split')
        check('Resize menu hides width controls for a full-width tile')
    finally:
        if window(a)['capabilities']['resizeVertical']:
            action('split', a)
        time.sleep(.7)
        run('hyprctl', 'eval', 'hl.config({ dwindle={ preserve_split='
            + ('true' if preserve_split else 'false') + ' } })')
    menu = status('gooey.window-tools')
    if menu['scroll']['contentHeight'] > menu['scroll']['height']:
        x,y = point(menu['card'])
        pointer('move',x,y,1280,800,'wheel',300)
        until(lambda: status('gooey.window-tools')['scroll']['y'] > 0, 'window action scrolling')
        check('Close stays visible while window actions scroll', ui_button('close-menu')['visible'])
    click(ui_button('close-menu'))
    time.sleep(.7)
    anchor = window(a)['anchor']
    x,y = point(next(r for r in window(a)['buttons'] if r['action']=='drag-grip'))
    pointer('move',x,y,1280,800,'rightdown','sleep',100,
        'move',x+2,y+1,1280,800,'sleep',100,'rightup')
    until(lambda: status('gooey.window-tools')['opened'], 'right-click title menu')
    check('Right-click with natural pointer jitter opens owner actions', status('gooey.window-tools')['targetId']==a)
    check('Reopened window menu starts at the top', status('gooey.window-tools')['scroll']['y']==0)
    ipc('gooey.window-tools', 'close')
    time.sleep(.5)
    close = next(r for r in window(a)['buttons'] if r['action']=='menu-actions')
    x,y=point(close)
    pointer('move',x,y,1280,800,'down','sleep',100,'move',x-60,y+80,1280,800,'sleep',100,'up')
    check('Dragging away cancels opening the window menu', not status('gooey.window-tools')['opened'])
    native_click(a, 'menu-actions')
    close = ui_button('close')
    x,y = point(close)
    pointer('move',x,y,1280,800,'down','sleep',100,'move',x-120,y-80,1280,800,'sleep',100,'up')
    check('Dragging away cancels Close in the owner menu', window(a) is not None)
    ipc('gooey.window-tools', 'close')
    return a,b


def exercise_launcher():
    config_path = Path(os.environ['XDG_CONFIG_HOME']) / 'omarchy/shell.json'
    original = config_path.read_text()
    def save(text):
        temp = config_path.with_suffix('.integration-next')
        temp.write_text(text)
        temp.replace(config_path)
    try:
        ipc('gooey.launcher', 'summon', 'root')
        time.sleep(.6)
        check('Launcher opens ready for normal text editing', status()['searchFocused'])
        click(status()['controls']['search'])
        until(lambda: status()['searchFocused'], 'clickable search focus')
        keyboard = ROOT / 'work/input/gooey-keyboard'
        run(keyboard, 'down',30,'up',30,'down',48,'up',48,'down',46,'up',46)
        until(lambda: status()['filter']=='abc', 'search text entry')
        run(keyboard, 'down',102,'up',102,'down',111,'up',111)
        until(lambda: status()['filter']=='bc', 'search Delete at caret')
        check('Mouse-focused search supports caret editing without uninstall', not status()['deleteConfirmation'])
        run(keyboard, 'down',29,'down',30,'up',30,'up',29,'down',45,'up',45)
        until(lambda: status()['filter']=='x', 'search select-all replacement')
        check('Search supports normal text selection and replacement')
        click(status()['controls']['clear'])
        until(lambda: status()['filter']=='', 'clear search')
        check('Visible Clear control resets search')
        apps = until(lambda: next((item for item in status()['items'] if item['itemId']=='apps'),None), 'Apps row')
        click(apps['rect'])
        until(lambda: status()['menu']=='apps', 'mouse Apps navigation')
        click(status()['controls']['back'])
        until(lambda: status()['menu']=='root', 'mouse Back navigation')
        check('Mouse browsing and Back preserve launcher navigation')
        click(status()['controls']['close'])
        until(lambda: not status()['visible'], 'visible close button')
        check('Visible Close control dismisses the launcher')
        ipc('gooey.launcher', 'close')
        time.sleep(.4)
        run(ROOT / 'work/input/gooey-keyboard', 'down',126,'sleep',120,'up',126)
        until(lambda: status()['visible'], 'right Super launcher')
        until(lambda: status()['searchFocused'], 'keyboard launcher focuses search')
        check('Right Super opens the same anchored launcher')
        ipc('gooey.launcher', 'close')
        run(ROOT / 'work/input/gooey-keyboard', 'down',126,'sleep',80,'down',20,'sleep',80,'up',20,'up',126)
        time.sleep(.5)
        check('Normal Super chord does not open launcher', not status()['visible'])
        for side in ('top', 'bottom', 'left', 'right'):
            config = json.loads(original)
            config['bar']['position'] = side
            save(json.dumps(config))
            ipc('gooey.launcher', 'summon', 'root')
            menu = until(lambda: status() if status()['barPosition'] == side and status()['visible'] else None, f'launcher {side}')
            time.sleep(.7)
            menu = status()
            c,s,a = menu['card'],menu['screen'],menu['anchor']
            check(f'Launcher stays inside screen on {side} bar', c['x']>=0 and c['y']>=0 and c['x']+c['width']<=s['width'] and c['y']+c['height']<=s['height'])
            attached = {'top':c['y'] >= a['y']+a['height'], 'bottom':c['y']+c['height'] <= a['y'], 'left':c['x']>=a['x']+a['width'], 'right':c['x']+c['width']<=a['x']}[side]
            check(f'Launcher opens inward from {side} logo', attached)
            shot('gooey-launcher-'+side)
        config = json.loads(original)
        logo = config['bar']['layout']['left'].pop(0)
        config['bar']['layout']['right'].append(logo)
        save(json.dumps(config))
        until(lambda: status()['barPosition']=='top' and status()['anchor']['x']>900, 'reordered logo follows')
        check('Open launcher follows logo reordered to other end of bar')
        ipc('gooey.launcher', 'close')
        save(original)
        time.sleep(.7)
        ipc('gooey.launcher', 'summon', 'root')
        anchor = status()['anchor']
        ipc('gooey.launcher', 'close')
        time.sleep(.5)
        click(anchor)
        until(lambda: status()['visible'], 'logo mouse launcher')
        check('Logo mouse click opens anchored launcher')
    finally:
        save(original)
        ipc('gooey.launcher', 'close')


def exercise_unload_during_grab(owner_id):
    """Unload while one virtual pointer still holds an actual native grab."""
    ipc('gooey.launcher', 'close')
    ipc('gooey.window-tools', 'close')
    initial = state()
    owner = window(owner_id)
    original_floating = owner['floating']
    companion = Path(os.environ['HOME']) / '.local/share/gooey/current/companion/gooey.so'
    assert companion.is_file(), 'Private staged companion is missing'

    def client():
        return next((w for w in json.loads(run('hyprctl', '-j', 'clients'))
                     if w['address'].lower() == owner['address'].lower()), None)

    def geometry(current):
        return tuple(current['at'] + current['size'])

    unloaded = False
    held_pointer = None
    try:
        if not original_floating:
            assert action('float', owner_id)['ok']
        until(lambda: window(owner_id)['floating'], 'floating unload fixture')
        for kind in ('title drag', 'resize drag'):
            assert action('focus', owner_id)['ok']
            # Earlier maximize/resize checks can leave a large floating restore
            # rectangle at an edge. Keep the grab-recovery fixture inside the
            # viewport so reconnect is not confused with intentionally hidden
            # offscreen tabs.
            run('hyprctl', 'dispatch', 'hl.dsp.window.move({ window='
                + json.dumps('address:' + owner['address'])
                + ', x=180, y=140, relative=false })')
            until(lambda: abs(window(owner_id)['x'] - 180) < 1
                  and abs(window(owner_id)['y'] - 140) < 1
                  and bool(window(owner_id)['buttons']), 'visible settled grab fixture')
            time.sleep(.3)
            before = window(owner_id)
            if kind == 'title drag':
                x, y = point(next(r for r in before['buttons'] if r['action']=='drag-grip'))
            else:
                x, y = point(next(b for b in before['buttons'] if b['action'] == 'resize-grip'))
            dx = -70 if before['x'] + before['width'] > 1160 else 70
            dy = -55 if before['y'] + before['height'] > 700 else 55
            # Keep this pointer connection and its button down alive throughout
            # unloading. The later motion must not continue the removed grab.
            steps = ['move', x, y, 1280, 800, 'down', 'sleep', 150,
                     'move', x + dx // 7, y + dy // 7, 1280, 800, 'sleep', 100,
                     'move', x + dx, y + dy, 1280, 800, 'sleep', 4500,
                     'move', x + dx + dx // 2, y + dy + dy // 2, 1280, 800,
                     'sleep', 300, 'up']
            held_pointer = subprocess.Popen(
                [str(ROOT / 'work/input/gooey-input'), *map(str, steps)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            changed_keys = ('x', 'y') if kind == 'title drag' else ('width', 'height')
            until(lambda: any(abs(window(owner_id)[key] - before[key]) > 20
                              for key in changed_keys), kind + ' active', timeout=3)
            check('Native ' + kind + ' is active before companion unload', held_pointer.poll() is None)
            assert run('hyprctl', 'plugin', 'unload', companion) == 'ok'
            unloaded = True
            time.sleep(.7)
            after_unload = client()
            check('Unloading during ' + kind + ' keeps compositor and application alive',
                  after_unload is not None and bool(json.loads(run('hyprctl', '-j', 'monitors'))))
            stationary = geometry(after_unload)
            stdout, stderr = held_pointer.communicate(timeout=8)
            assert held_pointer.returncode == 0, 'Virtual pointer failed: ' + stdout + stderr
            held_pointer = None
            time.sleep(.3)
            after_release = client()
            check('Unloading during ' + kind + ' ends the grab before pointer release',
                  after_release is not None and all(abs(a - b) <= 1
                      for a, b in zip(stationary, geometry(after_release))))
            assert run('hyprctl', 'plugin', 'load', companion) == 'ok'
            unloaded = False
            until(lambda: state()['instance'] == initial['instance'] and window(owner_id),
                  'native companion after ' + kind)
            until(lambda: status('gooey.window-tools')['ready'] and state()['theme']['ready']
                  and bool(window(owner_id)['buttons']), 'QML and visible strip after ' + kind)
            check('Companion and window service reconnect after ' + kind,
                  bool(window(owner_id)['buttons']))
    finally:
        if held_pointer is not None:
            try:
                held_pointer.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                held_pointer.kill()
                held_pointer.communicate()
        if unloaded:
            assert run('hyprctl', 'plugin', 'load', companion) == 'ok'
            until(lambda: status('gooey.window-tools')['ready'], 'unload test recovery')
        current = window(owner_id)
        if current and current['floating'] != original_floating:
            assert action('float', owner_id)['ok']
            until(lambda: window(owner_id)['floating'] == original_floating,
                  'restore unload fixture floating state')


def main():
    until(lambda: ipc('shell', 'ping') == 'ok', 'shell ready')
    baseline = until(lambda: state() if len(state()['windows']) >= 2 else None, 'native windows')
    (CACHE / 'gooey-state.json').write_text(json.dumps(baseline, indent=2))
    check('Native companion enumerates two attached application windows', len(baseline['windows']) == 2)
    until(lambda: status('gooey.window-tools')['ready'], 'window service ready')
    check('Window menu service connected to native companion')
    until(lambda: state()['theme']['ready'], 'Omarchy native theme sync')
    exercise_strip_geometry()
    time.sleep(1)
    shot('gooey-prototype')
    ipc('gooey.launcher', 'summon', 'root')
    menu = until(lambda: status() if status()['visible'] else None, 'launcher open')
    (CACHE / 'gooey-launcher-state.json').write_text(json.dumps(menu, indent=2))
    shot('gooey-launcher')
    check('Launcher opens from owned IPC', menu['anchorReady'])
    ipc('gooey.launcher', 'close')
    pointer('move', *point(menu['anchor']), 1280, 800, 'down', 'sleep', 80, 'up')
    until(lambda: status()['opened'] and status()['anchorReady'], 'logo click opens launcher')
    check('Menu-bar logo click opens the anchored launcher')
    pointer('move', *point(status()['anchor']), 1280, 800, 'down', 'sleep', 80, 'up')
    until(lambda: not status()['opened'], 'second logo click closes launcher')
    check('Second menu-bar logo click closes the launcher')
    a,b = exercise_windows(baseline)
    exercise_unload_during_grab(a)
    exercise_launcher()
    exercise_theme()
    spec = importlib.util.spec_from_file_location('visibility_integration', ROOT / 'dev/visibility-integration.py')
    visibility = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(visibility)
    limitations.extend(visibility.run_checks(sys.modules[__name__]))
    spec = importlib.util.spec_from_file_location('scrolling_integration', ROOT / 'dev/scrolling-integration.py')
    scrolling = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scrolling)
    limitations.extend(scrolling.run_checks(sys.modules[__name__]))
    spec = importlib.util.spec_from_file_location('edge_integration', ROOT / 'dev/edge-integration.py')
    edge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(edge)
    limitations.extend(edge.run_checks(sys.modules[__name__]))
    # The Super+T chord test intentionally changes native floating state.
    # Restore tiled fixtures before testing an exposed inactive Close button.
    for win in state()['windows']:
        if win['floating']: action('float', win['id'])
    time.sleep(.7)
    action('focus', b)
    x, y = point(next(button for button in window(a)['buttons'] if button['action'] == 'close'))
    pointer('move',x,y,1280,800,'down','sleep',100,'move',x-60,y+80,1280,800,'sleep',100,'up')
    check('Dragging away cancels the direct frame Close button', window(a) is not None and window(b) is not None)
    action('focus', b)
    native_click(a, 'close')
    until(lambda: window(a) is None, 'close exact owner')
    check('Close affects only its owning window', window(b) is not None)
    errors = run('hyprctl', 'configerrors')
    check('Hyprland configuration has no errors', not errors)
    (CACHE / 'gooey-integration-report.json').write_text(json.dumps({'checks':checks}, indent=2))


if __name__ == '__main__':
    succeeded = False
    try:
        main()
        succeeded = True
    except Exception:
        for key,fn in [('native',state),('menu',lambda:status('gooey.window-tools')),('launcher',status)]:
            try: (CACHE / ('gooey-failure-'+key+'.json')).write_text(json.dumps(fn(), indent=2))
            except Exception: pass
        try: shot('gooey-failure')
        except Exception: pass
        raise
    finally:
        release = Path(os.environ['HOME']) / '.local/share/gooey/current'
        (CACHE / 'gooey-integration-report.json').write_text(json.dumps({
            'passed': succeeded, 'checks': checks, 'limitations': limitations,
            'verifiedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'display': 'headless' if os.environ.get('GOOEY_HEADLESS') == '1' else 'nested-wayland',
            'release': release.resolve().name,
            'companionSha256': hashlib.sha256((release / 'companion/gooey.so').read_bytes()).hexdigest()
        }, indent=2) + '\n')

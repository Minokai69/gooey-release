#!/usr/bin/env python3
"""Verify successive live owner popups against native button rectangles."""
import json
from pathlib import Path
import runpy
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]

def run(*args):
    return subprocess.check_output(args, text=True, timeout=12).strip()

def status():
    return json.loads(run('omarchy', 'shell', 'gooey.window-tools', 'status'))

def close():
    run('omarchy', 'shell', 'gooey.window-tools', 'close')

runpy.run_path(str(ROOT / 'session/gooey-session'))['wait_unlocked']()
native = json.loads(run('hyprctl', 'gooey:state'))
owner = max((w for w in native['windows'] if w['decorationVisible']
    and {'menu-actions','menu-workspace','resize-grip'}.issubset({b['action'] for b in w['buttons']})),
    key=lambda w:w['anchor']['x'])
results = []
try:
    for action, kind, button_name in [('menu-layout','layout','resize-grip'),
        ('menu-actions','actions','menu-actions'),('menu-workspace','workspace','menu-workspace')]:
        close()
        response = json.loads(run('hyprctl', 'gooey:window',
            ' --instance ' + native['instance'] + ' ' + action + ' ' + owner['id']))
        assert response['ok'], response
        deadline = time.monotonic() + 8
        while True:
            menu = status()
            fresh = json.loads(run('hyprctl', 'gooey:state'))
            current = next(w for w in fresh['windows'] if w['id'] == owner['id'])
            output = next(m for m in fresh['monitors'] if m['name'] == current['monitor'])
            button = next(b for b in current['buttons'] if b['action'] == button_name)
            margin = max(1, int(12 * menu['theme']['scale'] + .5))
            gap = max(1, int(8 * menu['theme']['scale'] + .5))
            card = menu['card']
            x = button['x'] - output['x']
            if button_name != 'resize-grip': x += button['width'] - card['width']
            x = max(margin, min(x, output['width'] - card['width'] - margin))
            y = button['y'] - output['y'] + button['height'] + gap
            above = button['y'] - output['y'] - card['height'] - gap
            if y + card['height'] > output['height'] - margin and above >= margin: y = above
            y = max(margin, min(y, output['height'] - card['height'] - margin))
            if (menu['opened'] and menu['kind'] == kind and menu['targetId'] == owner['id']
                    and abs(card['x'] - x) <= 1 and abs(card['y'] - y) <= 1):
                results.append({'popup': kind, 'button': button_name, 'card': card, 'expected': {'x': x, 'y': y}})
                break
            assert time.monotonic() < deadline, (action, card, {'x':x,'y':y})
            time.sleep(.2)
finally:
    close()
report = {'verifiedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'release': (Path.home()/'.local/share/gooey/current').resolve().name,
    'passed': True, 'popups': results}
(ROOT/'docs/popup-anchor-report.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))

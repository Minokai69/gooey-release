#!/usr/bin/env python3
"""Capture real UI regions in the isolated fixture desktop; never host content."""
import json
import hashlib
import struct
import math
import os
from pathlib import Path
import runpy
import time
import integration as t

assert os.environ.get('GOOEY_CAPTURE_RELEASE') == '1'
out = t.CACHE / 'release-media'
out.mkdir(exist_ok=True)
for old in out.glob('*.png'): old.unlink()
(out/'capture.json').unlink(missing_ok=True)
records = []

def grab(name, rect=None, pad=0):
    args = ['grim']
    if rect:
        x, y = max(0, math.floor(rect['x']-pad)), max(0, math.floor(rect['y']-pad))
        w = min(1280-x, math.ceil(rect['width']+2*pad))
        h = min(800-y, math.ceil(rect['height']+2*pad))
        args += ['-g', f'{x},{y} {w}x{h}']
    t.run(*args, out / (name+'.png'))
    raw=(out/(name+'.png')).read_bytes()
    width,height=struct.unpack('>II',raw[16:24])
    records.append({'file':name+'.png', 'region':rect, 'padding':pad,
                    'pixelWidth':width, 'pixelHeight':height, 'sha256':hashlib.sha256(raw).hexdigest()})

def body(owner):
    w=t.window(owner)
    t.pointer('move', round(w['x']+w['width']/2), round(w['y']+80),1280,800)
    time.sleep(.5)

def frame(owner, prefix):
    body(owner)
    w=t.window(owner)
    grab(prefix+'-frame', w['anchor'])
    for b in w['buttons']:
        if b['action']!='drag-grip': grab('icon-'+b['action'], b, 2)

def window_menu(owner, action, filename):
    t.native_click(owner,action)
    m=t.until(lambda: (lambda s:s if s['opened'] else None)(t.status('gooey.window-tools')), filename)
    time.sleep(.6)
    m=t.status('gooey.window-tools')
    grab(filename,m['card'])
    t.ipc('gooey.window-tools','close');time.sleep(.4)

t.until(lambda:t.ipc('shell','ping')=='ok','shell')
t.until(lambda:len(t.state()['windows'])==2 and t.state()['theme']['ready'],'fixtures')
t.run('hyprctl','eval','hl.monitor({ output="HEADLESS-GOOEY", mode="2560x1600@60", position="0x0", scale=2 })')
time.sleep(2)
a,b=[w['id'] for w in t.state()['windows']]
frame(a,'dwindle')
grab('desktop')
grab('bar-navigation',{'x':0,'y':0,'width':180,'height':t.state()['theme']['height']})
window_menu(a,'menu-actions','window-actions')
window_menu(a,'menu-workspace','workspaces')
window_menu(a,'resize-grip','dwindle-resize')
# Capture the real hover card, using its own reported logical geometry.
w=t.window(a); grip=next(x for x in w['buttons'] if x['action']=='resize-grip')
x,y=t.point(grip);t.pointer('move',x,y,1280,800)
h=t.until(lambda:(lambda s:s if s and s['visible'] else None)(t.status('gooey.window-tools')['tooltip']),'tooltip')
grab('resize-tooltip',h)
body(a)
# Register the same owned Style row used by deployment, only in this private home.
api=runpy.run_path(str(t.ROOT/'session/gooey-session'))
command=Path.home()/'.local/bin/gooey';command.parent.mkdir(parents=True,exist_ok=True)
command.write_text('#!/bin/sh\nexec python3 /opt/omarchy-mouse-shell/session/gooey-session "$@"\n');command.chmod(0o755)
menu=Path.home()/'.config/omarchy/extensions/omarchy-menu.jsonc';menu.parent.mkdir(parents=True,exist_ok=True)
original=menu.read_text() if menu.exists() else None
try:
    text,_=api['style_menu'](original or '{}\n',str(command))
    menu.write_text(text);time.sleep(1)
    for route,filename in [('root','launcher'),('style','style-gooey')]:
        t.ipc('gooey.launcher','summon',route)
        m=t.until(lambda:(lambda s:s if s['visible'] and s['menu']==route else None)(t.status()),route)
        time.sleep(.8);m=t.status()
        if route == 'style':
            t.pointer('move',round(m['card']['x']+m['card']['width']/2),round(m['card']['y']+m['card']['height']-50),1280,800,'wheel',600)
            time.sleep(.6);m=t.status()
        grab(filename,m['card'])
        if route=='root': grab('bar-launcher',m['anchor'],2)
        if route=='style':
            row=next(r for r in m['items'] if 'Gooey' in r.get('label',''))
            assert '✓' in row['label'], row
            grab('style-gooey-toggle',row['rect'])
        t.ipc('gooey.launcher','close');time.sleep(.5)
finally:
    if original is None: menu.unlink(missing_ok=True)
    else: menu.write_text(original)
# Height controls only exist with a vertical split; capture that real state too.
t.run('hyprctl','eval','hl.config({dwindle={preserve_split=true}})')
if not t.window(a)['capabilities']['resizeVertical']: assert t.action('split',a)['ok']
t.until(lambda:t.window(a)['capabilities']['resizeVertical'],'vertical split')
frame(a,'dwindle-vertical')
assert t.action('split',a)['ok']
t.run('hyprctl','eval','hl.config({dwindle={preserve_split=false}})')
# Scrolling presets are captured from actual controls at an 85% column width.
t.run('hyprctl','eval','hl.config({general={layout="scrolling"}, scrolling={column_width=0.5, fullscreen_on_one_column=false, follow_focus=false, direction="right"}})')
t.until(lambda:t.window(a)['layout']=='scrolling','scrolling')
assert t.action('column-width',a,'85')['ok']; assert t.action('focus',a)['ok'];time.sleep(1)
frame(a,'scrolling')
window_menu(a,'resize-grip','scrolling-controls')
assert t.action('shelf',a)['ok'];time.sleep(1)
t.run('hyprctl','dispatch','hl.dsp.workspace.toggle_special("scratchpad")')
time.sleep(.7);body(a)
grip=next(x for x in t.window(a)['buttons'] if x['action']=='shelf');grab('icon-unshelf',grip,2)
t.run('hyprctl','dispatch','hl.dsp.workspace.toggle_special("scratchpad")')
time.sleep(.4)
t.ipc('gooey.window-tools','shelf')
m=t.until(lambda:(lambda s:s if s['opened'] else None)(t.status('gooey.window-tools')),'shelf');time.sleep(.6)
grab('shelf',t.status('gooey.window-tools')['card']);t.ipc('gooey.window-tools','close')
assert t.action('shelf',a)['ok']
(out/'capture.json').write_text(json.dumps({'source':'isolated Gooey fixture desktop','scale':2,'release':(Path.home()/'.local/share/gooey/current').resolve().name,'images':list({r['file']:r for r in records}.values())},indent=2)+'\n')
print(f'Captured {len(records)} UI regions in {out}',flush=True)

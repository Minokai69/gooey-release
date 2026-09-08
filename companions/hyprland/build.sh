#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
python3 - <<'PY_CHECK'
import json,pathlib,re
pin=json.loads(pathlib.Path('PIN.json').read_text())
header=pathlib.Path('/usr/include/hyprland/src/version.h').read_text()
match=re.search(r'#define GIT_COMMIT_HASH\s+"(.*?)"',header)
if not match or match.group(1) != pin['hyprlandCommit']:
    raise SystemExit('Gooey: installed headers do not match PIN.json; use a tested companion source revision.')
PY_CHECK
mkdir -p build
cxx=${CXX:-c++}
read -r -a includes <<< "$(pkg-config --cflags pixman-1 libdrm hyprland libinput libudev wayland-server xkbcommon cairo pangocairo)"
read -r -a libs <<< "$(pkg-config --libs cairo pangocairo)"
"$cxx" -O1 -g1 -shared -fPIC -fno-gnu-unique -std=c++23 -Wno-narrowing "${includes[@]}" main.cpp barDeco.cpp BarPassElement.cpp gooey.cpp "${libs[@]}" -o build/gooey.so.tmp
mv -f build/gooey.so.tmp build/gooey.so
python3 - <<'PY'
import json,hashlib,pathlib,re,subprocess
header=pathlib.Path('/usr/include/hyprland/src/version.h').read_text()
hash=re.search(r'#define GIT_COMMIT_HASH\s+"(.*?)"',header).group(1)
p=pathlib.Path('build/gooey.so')
info={'name':'gooey','version':'0.1.0-dev','protocolVersion':1,'hyprlandVersion':subprocess.check_output(['pkg-config','--modversion','hyprland'],text=True).strip(),'hyprlandCommit':hash,'upstreamPluginCommit':'7644cecdb947060682891a0db2a0cdc5c0b9e704','sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'runtimeGuard':'Hyprland API and header hash equality; no host activation'}
pathlib.Path('build/build-info.json').write_text(json.dumps(info,indent=2)+'\n')
PY

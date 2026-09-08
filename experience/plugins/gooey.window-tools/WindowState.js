function validId(value) {
    return /^[0-9]+$/.test(String(value || ""));
}

function destination(value) {
    var text = String(value === undefined || value === null ? "" : value).trim();
    if (/^[1-9][0-9]*$/.test(text)) return text;
    if (text.indexOf("name:") === 0) text = text.slice(5);
    if (!text || text.length > 128 || /[\x00-\x1f\x7f]/.test(text) || text.indexOf("special:") === 0) return "";
    return "name:" + text;
}

function normalWorkspace(workspace) {
    return !!workspace && workspace.special !== true && String(workspace.name || "").indexOf("special:") !== 0
        && (Number(workspace.id) > 0 || String(workspace.name || "") !== "");
}

function workspaceSelector(workspace) {
    if (workspace.selector) return destination(workspace.selector);
    return Number(workspace.id) > 0 ? String(workspace.id) : destination(workspace.name);
}

function workspaceOptions(snapshot, configured) {
    var result = [];
    var seen = {};
    var live = snapshot && Array.isArray(snapshot.workspaces) ? snapshot.workspaces : [];
    function add(value, label, existing, id) {
        var dest = destination(value);
        if (!dest || seen[dest]) return;
        seen[dest] = true;
        result.push({ destination: dest, label: String(label || value), existing: existing, id: id || 0 });
    }
    // Resolve configured names against live IDs so the current destination
    // stays recognizable when a workspace has a numeric internal identity.
    var choices = Array.isArray(configured) ? configured.slice() : [1,2,3,4,5,6,7,8,9,10];
    var rules = snapshot && Array.isArray(snapshot.configuredWorkspaces) ? snapshot.configuredWorkspaces : [];
    for (var r = 0; r < rules.length; r++) {
        var rule = rules[r];
        if (rule && rule.selector) choices.push({value: rule.selector, label: rule.name || rule.selector});
    }
    for (var i = 0; i < choices.length; i++) {
        var choice = choices[i];
        var value = choice && typeof choice === "object" ? choice.value : choice;
        var label = choice && typeof choice === "object" ? choice.label : value;
        var matched = null;
        for (var j = 0; j < live.length; j++) {
            if (!normalWorkspace(live[j])) continue;
            if (String(live[j].id) === String(value) || destination(live[j].name) === destination(value) || workspaceSelector(live[j]) === destination(value)) { matched = live[j]; break; }
        }
        if (matched) add(workspaceSelector(matched), choice && typeof choice === "object" && choice.label ? choice.label : matched.name || label, true, Number(matched.id));
        else add(value, label, false, 0);
    }
    for (var k = 0; k < live.length; k++) {
        var ws = live[k];
        if (normalWorkspace(ws)) add(workspaceSelector(ws), ws.name || String(ws.id), true, Number(ws.id));
    }
    return result;
}

function owner(snapshot, id) {
    var windows = snapshot && Array.isArray(snapshot.windows) ? snapshot.windows : [];
    for (var i = 0; i < windows.length; i++) if (String(windows[i].id) === String(id)) return windows[i];
    return null;
}

function shelfWindows(snapshot) {
    var windows = snapshot && Array.isArray(snapshot.windows) ? snapshot.windows : [];
    return windows.filter(function(w) { return w.shelved === true || w.workspaceName === "special:scratchpad"; });
}

function monitor(snapshot, name) {
    var outputs = snapshot && Array.isArray(snapshot.monitors) ? snapshot.monitors : [];
    for (var i = 0; i < outputs.length; i++) if (String(outputs[i].name) === String(name)) return outputs[i];
    return null;
}

function restoreDestination(snapshot, outputName) {
    var output = monitor(snapshot, outputName);
    if (output && Number(output.activeWorkspaceId) > 0) return String(output.activeWorkspaceId);
    if (output && output.activeWorkspaceName && String(output.activeWorkspaceName).indexOf("special:") !== 0) return destination(output.activeWorkspaceName);
    var outputs = snapshot && Array.isArray(snapshot.monitors) ? snapshot.monitors : [];
    for (var i = 0; i < outputs.length; i++) {
        if (Number(outputs[i].activeWorkspaceId) > 0) return String(outputs[i].activeWorkspaceId);
        if (outputs[i].activeWorkspaceName && String(outputs[i].activeWorkspaceName).indexOf("special:") !== 0) return destination(outputs[i].activeWorkspaceName);
    }
    return "";
}

function can(snapshot, window, action) {
    if (!window || !validId(window.id)) return false;
    // Whole-group movement is deliberately unavailable in the first release.
    if (window.grouped && ["workspace", "shelf", "swap", "split", "column-width", "column-center", "column-focus", "column-previous", "column-next"].indexOf(action) !== -1) return false;
    var caps = window.capabilities || (snapshot && snapshot.capabilities) || {};
    if (action === "column-focus") return caps.columnPrevious === true || caps.columnNext === true;
    var columnActions = {
        "column-width": "columnWidth",
        "column-center": "columnCenter",
        "column-previous": "columnPrevious",
        "column-next": "columnNext"
    };
    if (columnActions[action]) return caps[columnActions[action]] === true;
    return caps[action] === true;
}

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "WindowState.js" as State

Item {
    id: root
    property var shelfWidgets: []
    function registerShelf(widget) {
        if (shelfWidgets.indexOf(widget) < 0) shelfWidgets = shelfWidgets.concat([widget]);
    }
    function unregisterShelf(widget) {
        shelfWidgets = shelfWidgets.filter(function(item) { return item !== widget; });
    }
    property var shell: null
    property var manifest: null
    property string omarchyPath: Quickshell.env("OMARCHY_PATH")
    property var snapshot: ({
            protocolVersion: 1,
            instance: "",
            windows: [],
            workspaces: [],
            monitors: []
        })
    property bool ready: false
    property bool menuOpen: false
    property bool busy: false
    property string error: "Connecting to window controls…"
    property string lastAction: ""
    property string lastActionId: ""
    property string lastActionMessage: ""
    property string lastActionInstance: ""
    property int revision: 0
    property bool refreshPending: false
    property bool awaitingActionSnapshot: false
    property int completedActionVersion: 0
    property int stateActionVersion: 0
    property var configuredWorkspaces: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    readonly property var shelves: State.shelfWindows(snapshot)
    readonly property var destinations: State.workspaceOptions(snapshot, configuredWorkspaces)
    readonly property string instance: String(snapshot.instance || "")
    readonly property bool hasCompositor: Quickshell.env("HYPRLAND_INSTANCE_SIGNATURE") !== ""
    readonly property var themeStatus: ({
        synced: nativeTheme.synced,
        error: nativeTheme.lastError,
        payload: nativeTheme.payload,
        height: nativeTheme.barHeight,
        radius: nativeTheme.cornerRadius,
        scale: nativeTheme.spacingScale,
        fontSize: nativeTheme.fontSize,
        fontFamily: nativeTheme.fontFamily
    })
    readonly property var tooltipStatus: hoverTip.status
    FrameToolTip { id: hoverTip; backend: root }
    Connections {
        target: Hyprland
        function onRawEvent(event) {
            if (event.name === "gooeyhover") {
                hoverTip.dismiss();
                root.refresh();
            }
        }
    }
    signal updated
    signal actionFinished(string action, string windowId, bool success, string message)

    NativeThemeBridge {
        id: nativeTheme
        bar: root.shell ? root.shell.bar : null
        available: root.ready
        instance: root.instance
    }

    function findWindow(id) {
        return State.owner(snapshot, id);
    }
    function findMonitor(name) {
        return State.monitor(snapshot, name);
    }
    function restoreDestination(output) {
        return State.restoreDestination(snapshot, output);
    }
    function supports(window, action) {
        return ready && State.can(snapshot, window, action);
    }

    function refresh() {
        if (!hasCompositor) {
            ready = false;
            error = "Window controls require the Gooey Hyprland companion.";
            return;
        }
        if (stateProcess.running) {
            refreshPending = true;
            return;
        }
        stateActionVersion = completedActionVersion;
        stateProcess.running = true;
    }

    function failAction(action, id, message) {
        lastActionMessage = message;
        actionFinished(action, String(id), false, message);
        return false;
    }

    // Every action retains its captured native identity and compositor instance.
    // Process argv avoids a shell: titles and workspace names never become code.
    function perform(action, id, arg, expectedInstance) {
        var key = String(id || "");
        if (busy)
            return false;
        if (!ready || !expectedInstance || String(expectedInstance) !== instance)
            return failAction(action, key, "Window controls reconnected. Open this menu again.");
        var win = findWindow(key);
        if (!win)
            return failAction(action, key, "This window is no longer available.");
        if (!supports(win, action))
            return failAction(action, key, win.grouped ? "This action is unavailable for grouped windows." : "This layout does not support that action.");
        if (!/^[A-Za-z0-9_.-]+$/.test(instance))
            return failAction(action, key, "The compositor connection has an invalid identity.");
        // hyprctl scans argv for flags even after its command name. A leading
        // space keeps this one argument positional; the companion trims it.
        var command = " --instance " + instance + " " + action + " " + key;
        if (action === "workspace") {
            var dest = State.destination(arg && arg.destination);
            if (!dest)
                return failAction(action, key, "Choose a valid normal workspace.");
            if (dest === String(win.workspaceId))
                return true;
            command += " " + (arg && arg.follow ? "1" : "0") + " " + dest;
        } else if (action === "shelf" && win.shelved) {
            var restore = State.destination(arg);
            if (!restore)
                return failAction(action, key, "Choose a workspace to take this window off the Shelf.");
            command += " " + restore;
        } else if (action === "swap") {
            if (["l", "r", "u", "d"].indexOf(String(arg)) === -1)
                return false;
            command += " " + String(arg);
        } else if (action === "column-width") {
            if (["quarter", "half", "85", "full"].indexOf(String(arg)) === -1)
                return failAction(action, key, "Choose 25%, half, 85%, or full column width.");
            command += " " + String(arg);
        } else if (action === "column-focus") {
            if (["previous", "next"].indexOf(String(arg)) === -1)
                return failAction(action, key, "Choose a neighboring column.");
            if (!supports(win, "column-" + String(arg)))
                return failAction(action, key, "There is no column in that direction.");
            command += " " + String(arg);
        } else if (action === "resize") {
            var dx = Math.round(Number(arg && arg.x) || 0);
            var dy = Math.round(Number(arg && arg.y) || 0);
            if (Math.abs(dx) > 200 || Math.abs(dy) > 200 || (!dx && !dy))
                return false;
            command += " " + dx + " " + dy;
        } else if (["close", "shelf", "float", "maximize", "focus", "split", "column-center"].indexOf(action) === -1) {
            return failAction(action, key, "This action is not available yet.");
        }
        busy = true;
        lastAction = action;
        lastActionId = key;
        lastActionInstance = instance;
        lastActionMessage = "";
        actionProcess.command = ["timeout", "3s", "hyprctl", "gooey:window", command];
        actionProcess.running = true;
        return true;
    }

    function toggleShelf() {
        if (busy || !ready)
            return false;
        busy = true;
        lastAction = "show-shelf";
        lastActionId = "";
        lastActionInstance = instance;
        lastActionMessage = "";
        actionProcess.command = ["timeout", "3s", "hyprctl", "gooey:shelf"];
        actionProcess.running = true;
        return true;
    }

    FileView {
        path: Quickshell.env("HOME") + "/.config/gooey/windows.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            try {
                var config = JSON.parse(text());
                if (Array.isArray(config.configuredWorkspaces))
                    root.configuredWorkspaces = config.configuredWorkspaces;
            } catch (e) {
                console.warn("Gooey workspace preferences are invalid:", e);
            }
        }
    }

    Timer {
        interval: root.menuOpen ? 350 : 1500
        repeat: true
        running: root.hasCompositor
        triggeredOnStart: true
        onTriggered: root.refresh()
    }
    Process {
        id: stateProcess
        command: ["timeout", "3s", "hyprctl", "gooey:state"]
        stdout: StdioCollector {
            id: stateOutput
        }
        stderr: StdioCollector {
            id: stateErrors
        }
        onExited: function (exitCode) {
            try {
                var data = JSON.parse(stateOutput.text.trim());
                if (exitCode !== 0 || data.protocolVersion !== 1 || !data.instance || !Array.isArray(data.windows) || !Array.isArray(data.workspaces) || !Array.isArray(data.monitors))
                    throw new Error("unavailable");
                root.snapshot = data;
                root.ready = true;
                root.error = "";
                root.revision++;
                nativeTheme.schedule(data.theme && data.theme.ready === false);
            } catch (e) {
                root.ready = false;
                root.error = "Attached window controls are unavailable. Load a compatible Gooey companion.";
            }
            root.updated();
            if (root.awaitingActionSnapshot && root.stateActionVersion === root.completedActionVersion) {
                root.awaitingActionSnapshot = false;
                root.busy = false;
            }
            if (root.refreshPending) {
                root.refreshPending = false;
                Qt.callLater(root.refresh);
            }
        }
    }
    Process {
        id: actionProcess
        stdout: StdioCollector {
            id: actionOutput
        }
        stderr: StdioCollector {
            id: actionErrors
        }
        onExited: function (exitCode) {
            var success = false;
            var message = "Window action failed. The window may have changed.";
            try {
                var result = JSON.parse(actionOutput.text.trim());
                success = exitCode === 0 && result.ok === true && root.lastActionInstance === root.instance;
                if (result.error)
                    message = String(result.error);
            } catch (e) {
                if (actionOutput.text.trim() === "ok" && exitCode === 0)
                    success = true;
            }
            root.lastActionMessage = success ? "" : message;
            root.awaitingActionSnapshot = success;
            if (success)
                root.completedActionVersion++;
            if (!success)
                root.busy = false;
            root.actionFinished(root.lastAction, root.lastActionId, success, success ? "" : message);
            root.refresh();
        }
    }
}

import QtQuick
import Quickshell.Io
import qs.Commons

// Use the host's already-resolved palette and layout tokens. Its theme IPC and
// watched user shell.toml update these bindings; Gooey needs no theme hook,
// second file parser, or generated Hyprland configuration.
Item {
    id: root
    property var bar: null
    property bool available: false
    property string instance: ""
    property string acknowledged: ""
    property string submitted: ""
    property string lastError: ""
    property bool pending: false
    readonly property color foreground: Color.bar.text
    readonly property var normalSpec: Border.controlSpec("normal", foreground, Color.accent, Color.urgent)
    readonly property var hoverSpec: Border.controlSpec("hover-cursor", foreground, Color.accent, Color.urgent)
    readonly property var borderSpec: Border.surfaceSpec("popups", "border", Color.accent, Style.normalBorderWidth)
    readonly property real barHeight: Math.max(1, bar ? Number(bar.barSize) || Style.bar.sizeHorizontal : Style.bar.sizeHorizontal)
    readonly property real cornerRadius: Style.cornerRadius
    readonly property real spacingScale: Math.max(0.01, Style.effectiveSpacingScale)
    readonly property real fontSize: Style.font.body
    readonly property string fontFamily: {
        var family = String(bar && bar.fontFamily ? bar.fontFamily : Style.font.family);
        // Omarchy's bar uses its fontconfig monospace alias. Use the host's
        // resolved family for the compositor's separate text renderer too.
        return family === "monospace" ? String(Style.resolvedFontFamily || family) : family;
    }
    readonly property string payload: [
        "background", argb(Color.bar.background),
        "foreground", argb(foreground),
        "accent", argb(Color.accent),
        "muted", argb(Color.muted),
        "danger", argb(Color.urgent),
        "border", argb(Border.color(borderSpec)),
        "normal", argb(Style.normalFillFor(foreground, Color.accent, Color.urgent)),
        "hover", argb(Style.hoverFillFor(foreground, Color.accent, Color.urgent)),
        "pressed", argb(Style.pressedFillFor(foreground, Color.accent, Color.urgent)),
        "normalBorder", argb(Border.color(normalSpec)),
        "hoverBorder", argb(Border.color(hoverSpec)),
        "normalBorderWidth", maxBorderWidth(normalSpec),
        "hoverBorderWidth", maxBorderWidth(hoverSpec),
        "radius", cornerRadius,
        "scale", spacingScale,
        "height", barHeight,
        "fontSize", fontSize,
        "fontFamilyHex", utf8Hex(fontFamily)
    ].join(" ")
    readonly property string identity: instance + " " + payload
    readonly property bool synced: available && acknowledged === identity

    function argb(value) {
        var color = typeof value === "string" ? Qt.color(value) : value;
        function byte(part) {
            return ("0" + Math.max(0, Math.min(255, Math.round(part * 255))).toString(16)).slice(-2);
        }
        return byte(color.a === undefined ? 1 : color.a) + byte(color.r) + byte(color.g) + byte(color.b);
    }

    function maxBorderWidth(spec) {
        return Math.max(Border.top(spec), Border.right(spec), Border.bottom(spec), Border.left(spec));
    }

    function utf8Hex(value) {
        // Font families may contain spaces and non-ASCII names. One hex token
        // preserves their UTF-8 bytes without introducing a quoting grammar.
        return encodeURIComponent(String(value)).replace(/%([0-9a-fA-F]{2})|./g, function (part, encoded) {
            return encoded ? encoded.toLowerCase() : ("0" + part.charCodeAt(0).toString(16)).slice(-2);
        });
    }

    function schedule(force) {
        if (force)
            acknowledged = "";
        if (!available || !/^[A-Za-z0-9_.-]+$/.test(instance))
            return;
        if (process.running) {
            pending = true;
            return;
        }
        if (!synced)
            debounce.restart();
    }

    function sync() {
        if (!available || !/^[A-Za-z0-9_.-]+$/.test(instance) || synced)
            return;
        if (process.running) {
            pending = true;
            return;
        }
        pending = false;
        submitted = identity;
        process.command = ["timeout", "3s", "hyprctl", "gooey:theme", " --instance " + submitted];
        process.running = true;
    }

    onIdentityChanged: schedule(false)
    onAvailableChanged: {
        if (!available)
            acknowledged = "";
        else
            schedule(false);
    }
    Timer {
        id: debounce
        interval: 100
        onTriggered: root.sync()
    }
    Process {
        id: process
        stdout: StdioCollector { id: output }
        stderr: StdioCollector { id: errors }
        onExited: function(exitCode) {
            var ok = false;
            try {
                ok = exitCode === 0 && JSON.parse(output.text.trim()).ok === true;
            } catch (e) {}
            if (ok) {
                root.acknowledged = root.submitted;
                root.lastError = "";
            } else {
                root.lastError = "Window appearance could not be synchronized with Omarchy.";
            }
            // A theme may change while hyprctl is running. Only the latest
            // resolved state is submitted after the preceding request finishes.
            if (root.pending || root.submitted !== root.identity)
                root.schedule(false);
        }
    }
}

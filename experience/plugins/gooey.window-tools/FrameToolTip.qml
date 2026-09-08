import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.Commons
import qs.Ui

Item {
    id: root
    required property var backend
    readonly property var owner: backend.ready && !backend.menuOpen && !backend.busy
        ? backend.snapshot.windows.find(w => w.hoverAction && w.hoverText) || null : null
    readonly property var anchor: owner ? owner.buttons.find(b => b.action === owner.hoverAction) || null : null
    readonly property var output: owner ? backend.findMonitor(owner.monitor) : null
    readonly property var targetScreen: owner ? Quickshell.screens.find(s => s.name === owner.monitor) || null : null
    readonly property string key: owner && anchor ? owner.id + ":" + owner.hoverAction + ":" + owner.monitor : ""
    property bool shown: false
    readonly property var borderSpec: Border.surfaceSpec("tooltip", "border", Color.tooltip.border, Style.normalBorderWidth)
    readonly property var status: ({ visible: tip.visible, action: owner ? owner.hoverAction : "", text: label.text,
        output: owner ? owner.monitor : "", x: tip.margins.left, y: tip.margins.top, width: tip.width, height: tip.height })
    function dismiss() { shown = false; delay.stop(); }
    onKeyChanged: { dismiss(); if (key) delay.restart(); }
    Timer { id: delay; interval: 400; onTriggered: root.shown = !!root.key }
    PanelWindow {
        id: tip
        screen: root.targetScreen
        visible: root.shown && !!root.anchor && !!root.targetScreen && !!root.output
        color: "transparent"
        anchors { top: true; left: true }
        implicitWidth: Math.min(label.implicitWidth + Style.space(24), screen ? screen.width - Style.space(16) : 400)
        implicitHeight: label.implicitHeight + Style.space(16)
        margins.left: root.anchor && root.output ? Math.max(Style.space(8), Math.min(
            root.anchor.x - root.output.x + root.anchor.width / 2 - width / 2,
            (screen ? screen.width : 0) - width - Style.space(8))) : 0
        margins.top: root.anchor && root.output ? Math.max(Style.space(8), Math.min(
            root.anchor.y - root.output.y + root.anchor.height + Style.space(6),
            (screen ? screen.height : 0) - height - Style.space(8))) : 0
        exclusionMode: ExclusionMode.Ignore
        mask: Region {}
        WlrLayershell.namespace: "gooey-frame-tooltip"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        BorderSurface {
            anchors.fill: parent
            color: Color.tooltip.background
            borderSpec: root.borderSpec
            radius: Style.cornerRadius
        }
        Text {
            id: label
            anchors.centerIn: parent
            width: Math.min(implicitWidth, tip.width - Style.space(24))
            text: root.owner ? root.owner.hoverText : ""
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
            color: Color.tooltip.text
            font.family: Style.font.family
            font.pixelSize: Style.font.bodySmall
        }
    }
}

import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

BorderSurface {
    id: root
    property string text: ""
    property string subtitle: ""
    property string iconName: ""
    property string hint: ""
    property string actionKey: ""
    property string destination: ""
    property string windowId: ""
    objectName: "gooey-window-action"
    property bool selected: false
    property bool destructive: false
    property bool compact: false
    property bool quiet: false
    property bool toggle: false
    property bool alignLeft: iconName !== "" || toggle
    property real textSize: Style.font.body
    readonly property color ink: destructive ? Color.urgent : selected ? Style.selectedStateColor(Color.popups.text, Color.accent, Color.urgent) : Color.popups.text
    signal clicked
    implicitHeight: Math.max(Style.space(compact ? 40 : 44), content.implicitHeight + Style.space(20))
    implicitWidth: Math.max(Style.space(80), label.implicitWidth + Style.space(28) + (iconName ? Style.space(30) : 0))
    radius: Style.cornerRadius
    readonly property bool hot: mouse.containsMouse && enabled
    color: mouse.pressed && enabled ? Style.pressedFillFor(ink, Color.accent, Color.urgent)
        : activeFocus ? Style.focusFillFor(ink, Color.accent, Color.urgent)
        : hot ? Style.hoverFillFor(ink, Color.accent, Color.urgent)
        : selected ? Style.selectedFillFor(ink, Color.accent, Color.urgent)
        : quiet ? "transparent" : Style.normalFillFor(ink, Color.accent, Color.urgent)
    borderSpec: activeFocus ? Border.controlSpec("focus", ink, Color.accent, Color.urgent)
        : hot ? Border.controlSpec("hover-cursor", ink, Color.accent, Color.urgent)
        : selected ? Border.controlSpec("selected", ink, Color.accent, Color.urgent)
        : quiet ? Border.none() : Border.controlSpec("normal", ink, Color.accent, Color.urgent)
    opacity: enabled || selected ? 1 : 0.42
    activeFocusOnTab: enabled
    Accessible.role: toggle ? Accessible.CheckBox : Accessible.Button
    Accessible.name: text
    Accessible.description: hint || subtitle
    Accessible.checkable: toggle
    Accessible.checked: toggle && selected
    Accessible.onPressAction: if (enabled)
        clicked()
    Keys.onReturnPressed: if (enabled)
        clicked()
    Keys.onEnterPressed: if (enabled)
        clicked()
    Keys.onSpacePressed: if (enabled)
        clicked()
    Behavior on color {
        ColorAnimation {
            duration: 90
        }
    }
    RowLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: Style.space(12)
        anchors.rightMargin: Style.space(12)
        spacing: Style.space(10)
        ActionIcon {
            visible: root.iconName !== ""
            name: root.iconName
            stroke: root.ink
            Layout.preferredWidth: Style.space(20)
            Layout.preferredHeight: Style.space(20)
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Style.space(3)
            Text {
                id: label
                Layout.fillWidth: true
                text: root.text
                textFormat: Text.PlainText
                color: root.ink
                font.family: Style.font.menuFamily
                font.pixelSize: root.textSize
                font.weight: root.selected ? Font.DemiBold : Font.Normal
                horizontalAlignment: root.alignLeft ? Text.AlignLeft : Text.AlignHCenter
                elide: Text.ElideRight
            }
            Text {
                Layout.fillWidth: true
                visible: root.subtitle !== ""
                text: root.subtitle
                textFormat: Text.PlainText
                color: root.ink
                opacity: 0.7
                font.family: Style.font.menuFamily
                font.pixelSize: Style.font.caption
                horizontalAlignment: root.alignLeft ? Text.AlignLeft : Text.AlignHCenter
                elide: Text.ElideRight
            }
        }
        ToggleSwitch {
            visible: root.toggle
            checked: root.selected
            interactive: false
            rounded: Style.cornerRadius > 0
            accent: Color.accent
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: root.enabled
        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: root.clicked()
    }
    PanelToolTip {
        visible: mouse.containsMouse && root.hint !== ""
        text: root.hint
    }
}

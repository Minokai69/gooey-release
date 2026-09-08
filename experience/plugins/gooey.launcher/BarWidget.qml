// Based on Omarchy shell/plugins/menu/BarWidget.qml. See LICENSE and NOTICE.md.
import QtQuick
import Quickshell
import qs.Ui
import qs.Commons

BarWidget {
  id: root
  moduleName: "gooey.launcher"

  readonly property Item anchorItem: button
  readonly property string anchorToken: "launcher-" + Date.now() + "-" + Math.random().toString(36).slice(2)
  readonly property var anchorWindow: button.QsWindow.window
  readonly property string anchorOutput: anchorWindow && anchorWindow.screen ? anchorWindow.screen.name : ""
  readonly property var anchorService: bar && bar.shell ? bar.shell.serviceFor(root.moduleName) : null
  readonly property var launcher: anchorService ? anchorService.panel : null
  onAnchorServiceChanged: if (anchorService) anchorService.registerWidget(root)
  Component.onCompleted: if (anchorService) anchorService.registerWidget(root)
  Component.onDestruction: if (anchorService) anchorService.unregisterWidget(root)
  readonly property bool opened: !!launcher && launcher.opened && launcher.anchorToken === root.anchorToken

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function request(toggle) {
    if (!root.launcher) return
    root.launcher.open(JSON.stringify({
      trigger: "pointer", toggle: toggle,
      anchorToken: root.anchorToken, output: root.anchorOutput, menu: "root"
    }))
  }

  function open() { request(false) }
  function close() {
    if (root.opened && root.launcher) root.launcher.close()
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "Menu"
    labelVisible: false
    fixedWidth: barSize
    fixedHeight: barSize
    tooltipText: root.opened ? "Close launcher" : "Open apps and desktop menu"
    active: root.opened
    Accessible.role: Accessible.Button
    Accessible.name: "Gooey launcher"
    Accessible.description: "Open applications and desktop actions"
    onPressed: function(button) {
      if (button === Qt.LeftButton || button === Qt.RightButton) root.request(true)
    }
    BorderSurface {
      anchors.fill: parent
      anchors.margins: Style.spacing.xs
      radius: Style.cornerRadius
      color: button.tooltipHovered ? Style.hoverFillFor(button.foreground, Color.accent)
        : root.opened ? Style.selectedFillFor(button.foreground, Color.accent) : "transparent"
      borderSpec: button.tooltipHovered ? Border.controlSpec("hover-cursor", button.foreground, Color.accent)
        : root.opened ? Border.controlSpec("selected", button.foreground, Color.accent) : Border.none()
      Behavior on color { ColorAnimation { duration: 110 } }
    }
    Row {
      id: brand
      anchors.centerIn: parent
      spacing: Style.space(8)
      Text { text: "\ue900"; font.family: "omarchy"; font.pixelSize: Style.font.icon; color: root.opened ? Style.selectedStateColor(button.foreground, Color.accent) : button.foreground }
    }
  }
}

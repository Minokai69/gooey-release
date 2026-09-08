import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

ShellRoot {
  id: fixtures
  component TestWindow: FloatingWindow {
    id: win
    property string name: ""
    property string tint: "#202334"
    property int contentClicks: 0
    property int headerClicks: 0
    property int selectedFolder: 0
    readonly property bool notes: name === "Notes"
    title: "Gooey · " + name
    visible: true
    implicitWidth: 600
    implicitHeight: 540
    color: tint

    // A real client-side header target lets the integration runner prove that
    // the companion only consumes pointer input inside its centered strip. Wayland
    // clients have no authoritative global position: these diagnostics are
    // client-local and the runner adds the matching native window geometry.
    function diagnostics() {
      var w = headerProbe.width
      var h = headerProbe.height
      return {
        name: name,
        title: title,
        headerClicks: headerClicks,
        contentClicks: contentClicks,
        headerRect: { x: 0, y: 0, width: w, height: h },
        headerPoints: [
          { x: 12, y: 12 },
          { x: Math.round(w / 2), y: 12 },
          { x: Math.max(12, w - 12), y: 12 },
          { x: Math.round(w / 2), y: Math.round(h / 2) }
        ]
      }
    }

    ColumnLayout {
      anchors.fill: parent
      anchors.margins: 28
      spacing: 18
      RowLayout {
        id: headerRow
        Layout.fillWidth: true
        ColumnLayout {
          spacing: 6
          Text { text: win.name; color: "#c0caf5"; font.family: "Sans Serif"; font.pixelSize: 28; font.weight: Font.DemiBold }
          Text { text: win.notes ? "A little room to think." : "Everything in its place."; color: "#9aa5ce"; font.family: "Sans Serif"; font.pixelSize: 14 }
        }
        Item { Layout.fillWidth: true }
        Rectangle {
          width: 66; height: 26; radius: 13; color: "#30374d"
          Text { anchors.centerIn: parent; text: win.headerClicks ? win.headerClicks + " clicks" : "DEMO"; color: "#9aa5ce"; font.family: "Sans Serif"; font.pixelSize: 10; font.letterSpacing: win.headerClicks ? 0 : 1.3 }
        }
      }
      Rectangle { Layout.fillWidth: true; height: 1; color: "#353c52" }

      ColumnLayout {
        visible: win.notes
        Layout.fillWidth: true
        spacing: 12
        Text { text: "Make yourself at home"; color: "#c0caf5"; font.family: "Sans Serif"; font.pixelSize: 20; font.weight: Font.Medium }
        Text {
          Layout.fillWidth: true
          wrapMode: Text.WordWrap
          text: "Drag the window strip to move this window. Open its menu to use the Shelf or send it to another workspace."
          color: "#a9b1d6"; font.family: "Sans Serif"; font.pixelSize: 15; lineHeight: 1.4
        }
      }
      Rectangle {
        visible: win.notes
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 130
        radius: 12; color: "#252a3e"; border.color: editor.activeFocus ? "#7aa2f7" : "#353d57"
        TextEdit {
          id: editor
          anchors.fill: parent
          anchors.margins: 20
          text: "Ideas for today\n\n• Keep useful things close\n• Give each project its own workspace\n• Make the desktop feel like home\n\nYou can edit this note."
          color: "#c0caf5"; font.family: "Sans Serif"; font.pixelSize: 15
          selectionColor: "#414f78"; selectedTextColor: "#ffffff"
          wrapMode: TextEdit.Wrap; selectByMouse: true; clip: true
          Accessible.name: "Sample note"
        }
      }

      ColumnLayout {
        visible: !win.notes
        Layout.fillWidth: true
        spacing: 10
        Text { text: "Your places"; color: "#c0caf5"; font.family: "Sans Serif"; font.pixelSize: 17; font.weight: Font.Medium }
        Repeater {
          model: [ {name:"Projects", detail:"Things you are making", count:"4 folders"}, {name:"Pictures", detail:"A bit of inspiration", count:"12 items"}, {name:"Downloads", detail:"Recently collected", count:"3 items"} ]
          delegate: Rectangle {
            required property var modelData
            required property int index
            Layout.fillWidth: true
            height: 76; radius: 10
            color: win.selectedFolder === index ? "#2e4150" : folderMouse.containsMouse ? "#263940" : "#22333b"
            border.color: win.selectedFolder === index ? "#73b6bb" : "#33464e"
            RowLayout {
              anchors.fill: parent; anchors.margins: 16; spacing: 14
              Rectangle {
                width: 30; height: 23; radius: 4; color: "#73b6bb"
                Rectangle { x: 0; y: -4; width: 13; height: 9; radius: 3; color: "#73b6bb" }
              }
              ColumnLayout {
                Layout.fillWidth: true; spacing: 5
                Text { text: modelData.name; color: "#c0d9df"; font.family: "Sans Serif"; font.pixelSize: 15; font.weight: Font.Medium }
                Text { text: modelData.detail; color: "#91aeb8"; font.family: "Sans Serif"; font.pixelSize: 12 }
              }
              Text { text: modelData.count; color: "#91aeb8"; font.family: "Sans Serif"; font.pixelSize: 11 }
            }
            MouseArea { id: folderMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { win.selectedFolder = index; win.contentClicks++ } }
          }
        }
        Item { Layout.fillHeight: true }
      }
      Text {
        Layout.fillWidth: true
        text: win.notes ? "A sample note for trying the desktop · not saved" : "Sample folders · " + win.contentClicks + " selections"
        color: "#7f8caa"; font.family: "Sans Serif"; font.pixelSize: 11; wrapMode: Text.WordWrap
      }
    }
    MouseArea {
      id: headerProbe
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: parent.top
      height: Math.min(parent.height, headerRow.y + headerRow.height + 37)
      acceptedButtons: Qt.LeftButton
      cursorShape: Qt.PointingHandCursor
      onClicked: win.headerClicks++
    }
  }
  TestWindow { id: notesFixture; name: "Notes" }
  TestWindow { id: filesFixture; name: "Files"; tint: "#1c2b33" }
  IpcHandler {
    target: "fixtures"
    function ping(): string { return "ok" }
    function status(): string {
      return JSON.stringify({ windows: [notesFixture.diagnostics(), filesFixture.diagnostics()] })
    }
  }
}

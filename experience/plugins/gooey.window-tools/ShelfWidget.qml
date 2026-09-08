import QtQuick
import Quickshell
import qs.Ui
import qs.Commons
import "components"

BarWidget {
    id: root
    moduleName: "gooey.window-tools"
    onServiceChanged: if (service) service.registerShelf(root)
    Component.onCompleted: if (service) service.registerShelf(root)
    Component.onDestruction: if (service) service.unregisterShelf(root)
    readonly property var service: bar && bar.shell ? bar.shell.serviceFor("gooey.window-tools") : null
    readonly property Item anchorItem: button
    readonly property int shelfCount: service ? service.shelves.length : 0
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    WidgetButton {
        id: button
        bar: root.bar
        anchors.fill: parent
        text: "Shelf"
        labelVisible: false
        implicitWidth: Math.max(barSize, shelfContent.implicitWidth + scaledHorizontalMargin * 2)
        implicitHeight: barSize
        tooltipText: root.shelfCount ? "Shelf · " + root.shelfCount + (root.shelfCount === 1 ? " window set aside" : " windows set aside") : "Shelf · no windows set aside"
        Row {
            id: shelfContent
            anchors.centerIn: parent
            spacing: Style.space(7)
            ActionIcon {
                anchors.verticalCenter: parent.verticalCenter
                width: Style.space(16)
                height: Style.space(16)
                name: "shelf"
                stroke: button.foreground
            }
            Rectangle {
                visible: !root.vertical && root.shelfCount > 0
                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(Style.space(18), countLabel.implicitWidth + Style.space(8))
                height: Style.space(18)
                radius: Style.cornerRadius
                color: Util.alpha(button.foreground, 0.13)
                Text {
                    id: countLabel
                    anchors.centerIn: parent
                    text: root.shelfCount
                    color: button.foreground
                    font.family: button.fontFamily
                    font.pixelSize: Math.max(10, button.fontSize - 1)
                    font.weight: Font.DemiBold
                }
            }
        }
        onPressed: function (mouseButton) {
            if (!root.bar || !root.bar.shell)
                return;
            var window = button.QsWindow.window;
            root.bar.shell.toggle("gooey.window-tools", JSON.stringify({
                kind: "shelf",
                screen: window && window.screen ? window.screen.name : ""
            }));
        }
    }
}

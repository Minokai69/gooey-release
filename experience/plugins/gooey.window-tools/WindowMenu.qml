import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui
import "components"

Item {
    id: root
    property var shell: null
    property var service: null
    property var manifest: null
    property string omarchyPath: Quickshell.env("OMARCHY_PATH")
    readonly property var backend: service || (shell ? shell.serviceFor("gooey.window-tools") : null)
    readonly property var bar: shell ? shell.bar : null
    property bool opened: false
    property string kind: "actions"
    property string targetId: ""
    property string anchorAction: "menu-actions"
    property string targetInstance: ""
    property string outputName: ""
    property string capturedRestore: ""
    property string capturedTitle: ""
    property string capturedOwnerMonitor: ""
    property bool ownerFromShelf: false
    property bool followWindow: false
    property string message: ""
    property bool waitingForTarget: false
    property bool focusPrimed: false
    readonly property var owner: backend ? backend.findWindow(targetId) : null
    readonly property bool shelfView: kind === "shelf"
    readonly property var output: backend ? backend.findMonitor(outputName) : null
    readonly property var shelfItems: backend ? backend.shelves : []
    readonly property bool actionsReady: !!backend && backend.ready && !backend.busy && !!owner && targetInstance === backend.instance && (ownerFromShelf || owner.decorationVisible !== false)
    readonly property var selectedScreen: screenByName(outputName)
    readonly property Item shelfAnchor: findShelfAnchor()
    readonly property var numberedDestinations: backend ? backend.destinations.filter(function (d) {
        return /^[1-9][0-9]*$/.test(String(d.destination)) && String(d.label) === String(d.destination);
    }) : []
    readonly property var namedDestinations: backend ? backend.destinations.filter(function (d) {
        return !/^[1-9][0-9]*$/.test(String(d.destination)) || String(d.label) !== String(d.destination);
    }) : []
    readonly property string workspaceLabel: owner ? (owner.shelved ? "Shelf" : "Workspace " + String(owner.workspaceName || owner.workspaceId).replace(/^name:/, "")) : "Unavailable"
    readonly property string restoreLabel: capturedRestore ? "workspace " + capturedRestore.replace(/^name:/, "") : "a workspace you choose"
    readonly property string ownerLayout: owner ? String(owner.layout || "other") : "other"
    readonly property bool dwindleTile: !!owner && ownerLayout === "dwindle" && !owner.floating
    readonly property bool scrollingTile: !!owner && ownerLayout === "scrolling" && !owner.floating && !!owner.scrolling
    readonly property string columnDimension: scrollingTile && owner.scrolling.horizontal === false ? "height" : "width"
    readonly property real columnFraction: scrollingTile ? Number(owner.scrolling.columnWidth) : 0
    readonly property string columnLabel: scrollingTile ? "Column " + (Number(owner.scrolling.columnIndex) + 1) + " of " + Number(owner.scrolling.columnCount) : ""
    readonly property string nextColumnIcon: scrollingTile && ["left", "right", "up", "down"].indexOf(owner.scrolling.direction) !== -1 ? owner.scrolling.direction : "right"
    readonly property string previousColumnIcon: ({left: "right", right: "left", up: "down", down: "up"})[nextColumnIcon]

    component ColumnSizeControls: Column {
        width: parent.width
        spacing: Style.space(8)
        visible: root.scrollingTile
        SectionHeading {
            text: "COLUMN " + root.columnDimension.toUpperCase()
            detail: Math.round(root.columnFraction * 100) + "%"
        }
        RowLayout {
            width: parent.width
            spacing: Style.space(8)
            ActionButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                text: "25%"
                Accessible.name: "25% " + root.columnDimension
                actionKey: "column-width-quarter"
                windowId: root.targetId
                selected: Math.abs(root.columnFraction - 0.25) < 0.005
                hint: "Set this column to 25% of the available workspace " + root.columnDimension
                enabled: root.can("column-width")
                onClicked: root.act("column-width", "quarter")
            }
            ActionButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                text: "Half"
                Accessible.name: "Half " + root.columnDimension
                actionKey: "column-width-half"
                windowId: root.targetId
                selected: Math.abs(root.columnFraction - 0.5) < 0.005
                hint: "Set this column to half the available workspace " + root.columnDimension
                enabled: root.can("column-width")
                onClicked: root.act("column-width", "half")
            }
            ActionButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                text: "85%"
                Accessible.name: "85% " + root.columnDimension
                actionKey: "column-width-85"
                windowId: root.targetId
                selected: Math.abs(root.columnFraction - 0.85) < 0.005
                hint: "Set this column to 85% of the available workspace " + root.columnDimension
                enabled: root.can("column-width")
                onClicked: root.act("column-width", "85")
            }
            ActionButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                text: "Full"
                Accessible.name: "Full " + root.columnDimension
                actionKey: "column-width-full"
                windowId: root.targetId
                selected: Math.abs(root.columnFraction - 1) < 0.005
                hint: "Set this column to the full available workspace " + root.columnDimension
                enabled: root.can("column-width")
                onClicked: root.act("column-width", "full")
            }
        }
        Text {
            width: parent.width
            text: "Changes every window in this column."
            textFormat: Text.PlainText
            color: Color.popups.text
            opacity: 0.65
            font.family: Style.font.menuFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.Wrap
        }
    }

    function screenByName(name) {
        var screens = Quickshell.screens;
        for (var i = 0; i < screens.length; i++)
            if (screens[i].name === name)
                return screens[i];
        return null;
    }

    function findShelfAnchor() {
        if ((!shelfView && !ownerFromShelf) || !backend)
            return null;
        // Observe host layout changes before invoking the helper.
        var widgets = backend.shelfWidgets;
        for (var i = 0; i < widgets.length; i++) {
            var widget = widgets[i];
            var anchor = widget.anchorItem;
            var window = anchor ? anchor.QsWindow.window : null;
            if (widget.visible && widget.width > 0 && widget.height > 0 && window && window.screen && window.screen.name === outputName)
                return anchor;
        }
        return null;
    }

    function chooseOutput(preferred) {
        if (preferred && screenByName(preferred))
            return String(preferred);
        if (bar && typeof bar.focusedScreenName === "function") {
            var focused = bar.focusedScreenName();
            if (screenByName(focused))
                return focused;
        }
        return Quickshell.screens.length ? Quickshell.screens[0].name : "";
    }

    function close() {
        opened = false;
        waitingForTarget = false;
    }
    function open(payloadJson) {
        var payload = {};
        try {
            payload = JSON.parse(payloadJson || "{}");
        } catch (e) {}
        if (payload.kind === "shelf" || !payload.id)
            openShelf(payload.screen || "");
        else
            openOwner(String(payload.id), String(payload.kind || "actions"));
    }

    function openShelf(preferredOutput) {
        kind = "shelf";
        ownerFromShelf = false;
        targetId = "";
        targetInstance = backend ? backend.instance : "";
        outputName = chooseOutput(preferredOutput);
        capturedRestore = backend ? backend.restoreDestination(outputName) : "";
        message = "";
        waitingForTarget = false;
        opened = true;
        if (backend)
            backend.refresh();
    }

    function openOwner(id, requestedKind, expectedInstance, fromShelf) {
        if (!/^[0-9]+$/.test(id))
            return;
        targetId = id;
        // The Shelf can address windows with no visible native decoration. Its
        // destination picker retains that source and the visible Shelf anchor.
        // Native/tab IPC never receives this exemption.
        ownerFromShelf = fromShelf === true;
        kind = ["workspace", "layout"].indexOf(requestedKind) !== -1 ? requestedKind : "actions";
        anchorAction = kind === "workspace" ? "menu-workspace" : kind === "layout" ? "resize-grip" : "menu-actions";
        followWindow = false;
        message = "";
        targetInstance = expectedInstance ? String(expectedInstance) : (backend ? backend.instance : "");
        waitingForTarget = true;
        // Keep the panel unmapped until a fresh snapshot locates this owner.
        opened = false;
        if (backend)
            backend.refresh();
    }

    function syncTarget() {
        if (!backend)
            return;
        if (waitingForTarget) {
            waitingForTarget = false;
            if (!backend.ready || !owner || (!ownerFromShelf && owner.decorationVisible === false))
                return;
            if (targetInstance && targetInstance !== backend.instance)
                return;
            targetInstance = backend.instance;
            capturedTitle = owner.title || owner.appId || "Window";
            capturedOwnerMonitor = String(owner.monitor || "");
            outputName = chooseOutput(ownerFromShelf ? outputName : owner.monitor);
            capturedRestore = backend.restoreDestination(outputName);
            opened = true;
        } else if (opened && !shelfView && backend.ready) {
            if (!owner || targetInstance !== backend.instance || (!ownerFromShelf && owner.decorationVisible === false)
                    || String(owner.monitor || "") !== capturedOwnerMonitor)
                close();
        }
    }

    function can(action) {
        return actionsReady && backend.supports(owner, action);
    }
    function act(action, arg) {
        if (!can(action))
            return;
        message = "";
        backend.perform(action, targetId, arg, targetInstance);
    }
    function shelfAction(windowId, restore) {
        if (!backend || !backend.ready || backend.busy)
            return;
        var win = backend.findWindow(windowId);
        if (!win || !backend.supports(win, "shelf"))
            return;
        if (!restore) {
            openOwner(String(windowId), "workspace", backend.instance, true);
            return;
        }
        backend.perform("shelf", String(windowId), restore, backend.instance);
    }
    function currentDestination(option) {
        if (!owner)
            return false;
        var name = String(owner.workspaceName || "");
        if (name.indexOf("name:") !== 0)
            name = "name:" + name;
        return String(owner.workspaceId) === String(option.destination) || name === String(option.destination);
    }

    function buttonGeometry() {
        var result = [];
        if (!opened || !panel.visible)
            return result;
        var content = panel.contentItem;
        if (!content)
            return result;
        var viewport = focusRoot.mapToItem(content, 0, 0);
        function visit(item) {
            if (!item || item.visible === false)
                return;
            if (item.objectName === "gooey-window-action") {
                var p = item.mapToItem(content, 0, 0);
                var cx = p.x + item.width / 2, cy = p.y + item.height / 2;
                var clipped = false;
                for (var ancestor = item.parent; ancestor && ancestor !== focusRoot; ancestor = ancestor.parent) {
                    if (ancestor.clip) {
                        var clipOrigin = ancestor.mapToItem(content, 0, 0);
                        if (cx < clipOrigin.x || cx > clipOrigin.x + ancestor.width || cy < clipOrigin.y || cy > clipOrigin.y + ancestor.height)
                            clipped = true;
                    }
                }
                result.push({
                    text: item.text,
                    action: item.actionKey,
                    destination: item.destination,
                    windowId: item.windowId,
                    enabled: item.enabled,
                    visible: !clipped && cx >= viewport.x && cx <= viewport.x + focusRoot.width && cy >= viewport.y && cy <= viewport.y + focusRoot.height,
                    x: p.x,
                    y: p.y,
                    width: item.width,
                    height: item.height,
                    centerX: cx,
                    centerY: cy
                });
            }
            var children = item.children || [];
            for (var i = 0; i < children.length; i++)
                visit(children[i]);
        }
        visit(focusRoot);
        return result;
    }

    onKindChanged: {
        menuScroll.contentY = 0;
        if (opened)
            focusRoot.forceActiveFocus();
    }
    onOpenedChanged: {
        menuScroll.contentY = 0;
        focusPrimed = false;
        if (backend)
            backend.menuOpen = opened;
        if (opened) {
            if (bar && typeof bar.requestPopout === "function")
                bar.requestPopout(root);
            focusTimer.restart();
            Qt.callLater(function () {
                if (opened)
                    focusRoot.forceActiveFocus();
            });
        } else {
            focusTimer.stop();
            if (bar && bar.activePopout === root)
                bar.releasePopout(root);
        }
    }
    onBackendChanged: if (backend) {
        backend.menuOpen = opened;
        if (waitingForTarget)
            backend.refresh();
    }
    onSelectedScreenChanged: if (opened && !selectedScreen)
        close()
    Component.onDestruction: {
        if (backend)
            backend.menuOpen = false;
        if (bar && bar.activePopout === root)
            bar.releasePopout(root);
    }

    Connections {
        target: root.backend
        function onUpdated() {
            root.syncTarget();
        }
        function onActionFinished(action, windowId, success, errorText) {
            if (!root.opened)
                return;
            if (!success) {
                root.message = errorText;
                return;
            }
            if (["workspace", "close", "focus", "column-focus", "show-shelf"].indexOf(action) !== -1 || (action === "shelf" && !root.shelfView))
                root.close();
        }
    }
    IpcHandler {
        target: "gooey.window-tools"
        function openMenu(stableId: string, kind: string): void {
            root.openOwner(stableId, kind);
        }
        function openMenuForInstance(stableId: string, kind: string, expectedInstance: string): void {
            if (!/^[A-Za-z0-9_.-]+$/.test(expectedInstance))
                return;
            root.openOwner(stableId, kind, expectedInstance);
        }
        function shelf(): void {
            root.openShelf("");
        }
        function close(): void {
            root.close();
        }
        function status(): string {
            return JSON.stringify({
                ready: !!root.backend && root.backend.ready,
                opened: root.opened,
                tooltip: root.backend ? root.backend.tooltipStatus : null,
                kind: root.kind,
                layout: root.ownerLayout,
                source: root.shelfView || root.ownerFromShelf ? "shelf" : "window",
                targetId: root.targetId,
                instance: root.targetInstance,
                output: root.outputName,
                shelfCount: root.shelfItems.length,
                followWindow: root.followWindow,
                busy: !!root.backend && root.backend.busy,
                lastAction: root.backend ? root.backend.lastAction : "",
                lastActionId: root.backend ? root.backend.lastActionId : "",
                lastActionMessage: root.backend ? root.backend.lastActionMessage : "",
                message: root.message,
                anchor: {
                    x: panel.origin.x,
                    y: panel.origin.y
                },
                card: {
                    x: card.x,
                    y: card.y,
                    width: card.width,
                    height: card.height
                },
                buttons: root.buttonGeometry(),
                scroll: { y: menuScroll.contentY, height: menuScroll.height, contentHeight: menuScroll.contentHeight },
                theme: root.backend ? root.backend.themeStatus : null,
                error: root.backend ? root.backend.error : "Service is loading"
            });
        }
    }
    Timer {
        id: focusTimer
        interval: 75
        onTriggered: root.focusPrimed = true
    }

    PanelWindow {
        id: panel
        screen: root.selectedScreen
        visible: root.opened && !!root.selectedScreen
        color: "transparent"
        anchors {
            top: true
            bottom: true
            left: true
            right: true
        }
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "gooey-window-menu"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: root.opened ? (root.focusPrimed ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.Exclusive) : WlrKeyboardFocus.None
        readonly property real margin: Style.space(12)
        readonly property real popupWidth: Math.min(Math.max(240, Style.space(root.kind === "actions" ? 400 : 440)), Math.max(120, width - margin * 2))
        readonly property real popupHeight: Math.min(menuContent.implicitHeight + menuHeader.implicitHeight + Style.space(72) + 1, Math.max(120, height - margin * 2))
        readonly property point origin: {
            var x = margin, y = margin;
            var screenX = root.output ? Number(root.output.x || 0) : 0;
            var screenY = root.output ? Number(root.output.y || 0) : 0;
            var anchor = root.shelfAnchor;
            var aw = anchor ? anchor.QsWindow.window : null;
            var anchorContent = aw ? aw.contentItem : null;
            if ((root.shelfView || root.ownerFromShelf) && anchor && aw && anchorContent && root.bar && !root.bar.barHidden) {
                anchorWatcher.transform;
                var pos = anchor.mapToItem(anchorContent, 0, 0);
                var side = root.bar.position;
                if (side === "left" || side === "right") {
                    x = side === "left" ? aw.width + margin : width - aw.width - popupWidth - margin;
                    y = pos.y + anchor.height / 2 - popupHeight / 2;
                } else {
                    x = pos.x + anchor.width / 2 - popupWidth / 2;
                    y = side === "bottom" ? height - aw.height - popupHeight - margin : aw.height + margin;
                }
            } else if (root.owner) {
                var trigger = (root.owner.buttons || []).find(function (button) { return button.action === root.anchorAction; });
                var a = trigger || root.owner.anchor || {
                    x: root.owner.x,
                    y: root.owner.y,
                    width: root.owner.width,
                    height: 0
                };
                x = root.anchorAction === "resize-grip" ? Number(a.x || 0) - screenX : Number(a.x || 0) - screenX + Number(a.width || 0) - popupWidth;
                y = Number(a.y || 0) - screenY + Number(a.height || 0) + Style.space(8);
                if (y + popupHeight > height - margin && Number(a.y || 0) - screenY - popupHeight - Style.space(8) >= margin)
                    y = Number(a.y || 0) - screenY - popupHeight - Style.space(8);
            } else {
                x = width - popupWidth - margin;
                y = root.bar && root.bar.position === "top" ? root.bar.barSize + margin : margin;
            }
            return Qt.point(Math.round(Math.max(margin, Math.min(x, width - popupWidth - margin))), Math.round(Math.max(margin, Math.min(y, height - popupHeight - margin))));
        }
        TransformWatcher {
            id: anchorWatcher
            a: {
                var anchor = root.shelfAnchor;
                var window = anchor ? anchor.QsWindow.window : null;
                return window ? window.contentItem : null;
            }
            b: root.shelfAnchor
        }
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onClicked: root.close()
        }
        BorderSurface {
            id: card
            x: panel.origin.x
            y: panel.origin.y
            width: panel.popupWidth
            height: panel.popupHeight
            radius: Style.cornerRadius
            color: Color.popups.background
            borderSpec: Border.surfaceSpec("popups", "border", Color.accent, Style.normalBorderWidth)
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.AllButtons
            }
            Item {
                id: focusRoot
                anchors.fill: parent
                anchors.margins: Style.space(20)
                focus: true
                Keys.onEscapePressed: root.close()
                RowLayout {
                    id: menuHeader
                    width: parent.width
                    spacing: Style.space(12)
                    ActionButton {
                        visible: !root.shelfView && root.kind !== "actions"
                        text: ""
                        iconName: "back"
                        actionKey: "actions-menu"
                        hint: "Back to window controls"
                        Accessible.name: "Back to window controls"
                        quiet: true
                        Layout.preferredWidth: Style.space(44)
                        onClicked: root.kind = "actions"
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Text {
                            Layout.fillWidth: true
                            text: root.shelfView ? "Shelf" : root.kind === "workspace" ? "Send to workspace" : root.kind === "layout" ? (root.scrollingTile ? "Column controls" : "Arrange & resize") : "Window controls"
                            textFormat: Text.PlainText
                            color: Color.popups.text
                            font.family: Style.font.menuFamily
                            font.pixelSize: Style.font.heading
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }
                        Text {
                            Layout.fillWidth: true
                            text: root.shelfView ? root.shelfItems.length + (root.shelfItems.length === 1 ? " window set aside" : " windows set aside") : root.capturedTitle
                            textFormat: Text.PlainText
                            color: Color.popups.text
                            opacity: 0.78
                            font.family: Style.font.menuFamily
                            font.pixelSize: Style.font.body
                            elide: Text.ElideRight
                        }
                    }
                    ActionButton {
                        text: ""
                        iconName: "close"
                        actionKey: "close-menu"
                        hint: "Close menu"
                        Accessible.name: "Close menu"
                        quiet: true
                        Layout.preferredWidth: Style.space(44)
                        onClicked: root.close()
                    }
                }
                Rectangle {
                    id: headerRule
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: menuHeader.bottom
                    anchors.topMargin: Style.space(16)
                    height: 1
                    color: Util.alpha(Color.popups.text, 0.12)
                }
                Flickable {
                    id: menuScroll
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: headerRule.bottom
                    anchors.topMargin: Style.space(16)
                    anchors.bottom: parent.bottom
                    contentHeight: menuContent.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}
                    Column {
                        id: menuContent
                        width: parent.width
                        spacing: Style.space(16)
                        Text {
                            width: parent.width
                            visible: text !== ""
                            text: root.message || (!root.backend || !root.backend.ready ? (root.backend ? root.backend.error : "Window controls are loading…") : "")
                            textFormat: Text.PlainText
                            color: Color.urgent
                            font.family: Style.font.menuFamily
                            font.pixelSize: Style.font.body
                            wrapMode: Text.Wrap
                        }
                        Column {
                            width: parent.width
                            spacing: Style.space(12)
                            visible: root.shelfView
                            ActionButton {
                                width: parent.width
                                text: "Show / hide Shelf"
                                subtitle: "View the Shelf workspace · Super + S"
                                iconName: "shelf"
                                actionKey: "show-shelf"
                                hint: "Open the same Shelf used by Omarchy's scratchpad"
                                enabled: !!root.backend && root.backend.ready && !root.backend.busy
                                onClicked: root.backend.toggleShelf()
                            }
                            Rectangle {
                                width: parent.width
                                height: emptyContent.implicitHeight + Style.space(36)
                                visible: root.shelfItems.length === 0
                                radius: Style.cornerRadius
                                color: Util.alpha(Color.popups.text, 0.025)
                                Column {
                                    id: emptyContent
                                    anchors.centerIn: parent
                                    width: parent.width - Style.space(32)
                                    spacing: Style.space(10)
                                    ActionIcon {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        width: 30
                                        height: 30
                                        name: "shelf"
                                        stroke: Color.accent
                                    }
                                    Text {
                                        width: parent.width
                                        text: "Your Shelf is clear"
                                        textFormat: Text.PlainText
                                        color: Color.popups.text
                                        font.family: Style.font.menuFamily
                                        font.pixelSize: Style.font.body
                                        font.weight: Font.DemiBold
                                        horizontalAlignment: Text.AlignHCenter
                                    }
                                    Text {
                                        width: parent.width
                                        text: "Open a window’s strip and choose Send to shelf. It stays running until you need it again."
                                        textFormat: Text.PlainText
                                        color: Color.popups.text
                                        opacity: 0.7
                                        font.family: Style.font.menuFamily
                                        font.pixelSize: Style.font.caption
                                        wrapMode: Text.Wrap
                                        horizontalAlignment: Text.AlignHCenter
                                    }
                                }
                            }
                            Repeater {
                                model: root.shelfItems
                                delegate: Rectangle {
                                    required property var modelData
                                    width: menuContent.width
                                    height: shelfRow.implicitHeight + Style.space(24)
                                    radius: Style.cornerRadius
                                    color: Util.alpha(Color.popups.text, 0.025)
                                    border.width: 1
                                    border.color: Util.alpha(Color.popups.text, 0.1)
                                    Column {
                                        id: shelfRow
                                        anchors.fill: parent
                                        anchors.margins: Style.space(12)
                                        spacing: Style.space(10)
                                        Text {
                                            width: parent.width
                                            text: modelData.title || modelData.appId || "Window"
                                            textFormat: Text.PlainText
                                            color: Color.popups.text
                                            font.family: Style.font.menuFamily
                                            font.pixelSize: Style.font.body
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }
                                        RowLayout {
                                            width: parent.width
                                            spacing: Style.space(8)
                                            ActionButton {
                                                text: "Show window"
                                                iconName: "show"
                                                actionKey: "focus"
                                                windowId: String(modelData.id)
                                                Layout.fillWidth: true
                                                hint: "Focus this window on the Shelf"
                                                enabled: !!root.backend && !root.backend.busy && root.backend.supports(modelData, "focus")
                                                onClicked: root.backend.perform("focus", String(modelData.id), null, root.backend.instance)
                                            }
                                            ActionButton {
                                                text: "Take off shelf"
                                                iconName: "unshelf"
                                                actionKey: "take-off-shelf"
                                                windowId: String(modelData.id)
                                                Layout.fillWidth: true
                                                hint: "Return this window to " + root.restoreLabel
                                                enabled: !!root.backend && !root.backend.busy && root.backend.supports(modelData, "shelf")
                                                onClicked: root.shelfAction(String(modelData.id), root.capturedRestore)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        Column {
                            width: parent.width
                            spacing: Style.space(14)
                            visible: !root.shelfView && root.kind === "workspace"
                            SectionHeading {
                                text: "CURRENT"
                                detail: root.workspaceLabel
                            }
                            Flow {
                                width: parent.width
                                spacing: Style.space(8)
                                Repeater {
                                    model: root.numberedDestinations
                                    delegate: ActionButton {
                                        required property var modelData
                                        actionKey: "workspace"
                                        destination: modelData.destination
                                        windowId: root.targetId
                                        width: (menuContent.width - Style.space(32)) / 5
                                        text: modelData.label
                                        textSize: Style.font.display
                                        subtitle: root.currentDestination(modelData) ? "Current" : modelData.existing ? "Open" : "New"
                                        selected: root.currentDestination(modelData)
                                        hint: root.currentDestination(modelData) ? "This window is already here" : modelData.existing ? "Send this window to workspace " + modelData.label : "Create workspace " + modelData.label + " with this window"
                                        enabled: root.can("workspace") && !root.currentDestination(modelData)
                                        onClicked: root.act("workspace", {
                                            destination: modelData.destination,
                                            follow: root.followWindow
                                        })
                                    }
                                }
                            }
                            Column {
                                width: parent.width
                                spacing: Style.space(8)
                                visible: root.namedDestinations.length > 0
                                SectionHeading {
                                    text: "NAMED WORKSPACES"
                                }
                                Repeater {
                                    model: root.namedDestinations
                                    delegate: ActionButton {
                                        required property var modelData
                                        width: parent.width
                                        actionKey: "workspace"
                                        destination: modelData.destination
                                        windowId: root.targetId
                                        text: String(modelData.label).replace(/^name:/, "")
                                        iconName: root.currentDestination(modelData) ? "check" : "workspace"
                                        selected: root.currentDestination(modelData)
                                        hint: root.currentDestination(modelData) ? "This window is already here" : "Send this window to " + modelData.label
                                        enabled: root.can("workspace") && !root.currentDestination(modelData)
                                        onClicked: root.act("workspace", {
                                            destination: modelData.destination,
                                            follow: root.followWindow
                                        })
                                    }
                                }
                            }
                            ActionButton {
                                width: parent.width
                                text: "Follow window"
                                subtitle: root.followWindow ? "Switch to its destination after moving" : "Stay on your current workspace"
                                actionKey: "follow-window"
                                toggle: true
                                selected: root.followWindow
                                hint: "Also switch to the destination workspace after moving"
                                onClicked: root.followWindow = !root.followWindow
                            }
                            Text {
                                width: parent.width
                                visible: !!root.owner && root.owner.grouped
                                text: "Workspace moves are unavailable for grouped windows so other windows stay in place."
                                textFormat: Text.PlainText
                                color: Color.popups.text
                                opacity: 0.7
                                font.family: Style.font.menuFamily
                                font.pixelSize: Style.font.caption
                                wrapMode: Text.Wrap
                            }
                        }
                        Column {
                            width: parent.width
                            spacing: Style.space(14)
                            visible: !root.shelfView && root.kind === "actions"
                            GridLayout {
                                width: parent.width
                                columns: 2
                                columnSpacing: Style.space(8)
                                rowSpacing: Style.space(8)
                                ActionButton {
                                    Layout.fillWidth: true
                                    text: root.owner && root.owner.shelved ? "Take off shelf" : "Send to shelf"
                                    iconName: root.owner && root.owner.shelved ? "unshelf" : "shelf"
                                    actionKey: "shelf"
                                    windowId: root.targetId
                                    hint: root.owner && root.owner.shelved ? "Return this window to " + root.restoreLabel : "Set this window aside and keep it running"
                                    enabled: root.can("shelf")
                                    onClicked: {
                                        if (root.owner.shelved && !root.capturedRestore)
                                            root.kind = "workspace";
                                        else
                                            root.act("shelf", root.capturedRestore);
                                    }
                                }
                                ActionButton {
                                    Layout.fillWidth: true
                                    text: "Workspace…"
                                    iconName: "workspace"
                                    actionKey: "workspace-menu"
                                    hint: "Send this window to a specific workspace"
                                    enabled: root.can("workspace")
                                    onClicked: root.kind = "workspace"
                                }
                                ActionButton {
                                    Layout.fillWidth: true
                                    text: root.owner && root.owner.floating ? "Tile window" : "Float window"
                                    iconName: root.owner && root.owner.floating ? "tile" : "float"
                                    actionKey: "float"
                                    windowId: root.targetId
                                    hint: root.owner && root.owner.floating ? "Return to your tiling layout" : "Move and size this window freely"
                                    enabled: root.can("float")
                                    onClicked: root.act("float", null)
                                }
                                ActionButton {
                                    Layout.fillWidth: true
                                    text: root.owner && (root.owner.maximized || Number(root.owner.fullscreen) === 1) ? "Restore size" : "Maximize"
                                    iconName: root.owner && (root.owner.maximized || Number(root.owner.fullscreen) === 1) ? "restore" : "maximize"
                                    actionKey: "maximize"
                                    windowId: root.targetId
                                    hint: "Fill the available workspace while keeping desktop controls visible"
                                    enabled: root.can("maximize")
                                    onClicked: root.act("maximize", null)
                                }
                            }
                            ColumnSizeControls {}
                            ActionButton {
                                width: parent.width
                                text: root.scrollingTile ? "Column controls…" : "Arrange & resize…"
                                subtitle: root.scrollingTile ? "Adjust column size, navigate, or center" : root.dwindleTile ? "Change split, swap tiles, or adjust size" : "Adjust this window’s size"
                                iconName: root.scrollingTile ? "columns" : "split"
                                actionKey: "layout-menu"
                                hint: "More controls for your Hyprland layout"
                                enabled: root.can("split") || root.can("swap") || root.can("resize") || root.can("column-width") || root.can("column-center") || root.can("column-focus")
                                onClicked: root.kind = "layout"
                            }
                            Rectangle {
                                width: parent.width
                                height: 1
                                color: Util.alpha(Color.popups.text, 0.12)
                            }
                            ActionButton {
                                width: parent.width
                                text: "Close window"
                                iconName: "close"
                                actionKey: "close"
                                windowId: root.targetId
                                destructive: true
                                quiet: true
                                hint: "Close " + root.capturedTitle
                                enabled: root.can("close")
                                onClicked: root.act("close", null)
                            }
                        }
                        Column {
                            width: parent.width
                            spacing: Style.space(14)
                            visible: !root.shelfView && root.kind === "layout"
                            Text {
                                width: parent.width
                                text: "Click the diagonal resize icon for this menu, or drag it to resize." + (root.owner && root.owner.grouped ? " Grouped-window movement is unavailable." : root.dwindleTile ? " Tiled windows need a neighboring tile to share space with." : "")
                                textFormat: Text.PlainText
                                color: Color.popups.text
                                opacity: 0.65
                                font.family: Style.font.menuFamily
                                font.pixelSize: Style.font.caption
                                wrapMode: Text.Wrap
                            }
                            ColumnSizeControls {}
                            Column {
                                width: parent.width
                                spacing: Style.space(8)
                                visible: root.scrollingTile
                                SectionHeading {
                                    text: "COLUMNS"
                                    detail: root.columnLabel
                                }
                                RowLayout {
                                    width: parent.width
                                    spacing: Style.space(8)
                                    ActionButton {
                                        Layout.fillWidth: true
                                        text: "Previous"
                                        iconName: root.previousColumnIcon
                                        actionKey: "column-previous"
                                        windowId: root.targetId
                                        hint: "Focus the previous column"
                                        enabled: root.can("column-previous")
                                        onClicked: root.act("column-focus", "previous")
                                    }
                                    ActionButton {
                                        Layout.fillWidth: true
                                        text: "Center"
                                        iconName: "center"
                                        actionKey: "column-center"
                                        windowId: root.targetId
                                        hint: "Center this column in the viewport"
                                        enabled: root.can("column-center")
                                        onClicked: root.act("column-center", null)
                                    }
                                    ActionButton {
                                        Layout.fillWidth: true
                                        text: "Next"
                                        iconName: root.nextColumnIcon
                                        actionKey: "column-next"
                                        windowId: root.targetId
                                        hint: "Focus the next column"
                                        enabled: root.can("column-next")
                                        onClicked: root.act("column-focus", "next")
                                    }
                                }
                            }
                            Column {
                                width: parent.width
                                spacing: Style.space(8)
                                visible: root.dwindleTile
                                SectionHeading {
                                    text: "TILING"
                                    detail: root.owner && root.owner.floating ? "Floating window" : root.workspaceLabel
                                }
                                ActionButton {
                                    width: parent.width
                                    text: "Change split"
                                    iconName: "split"
                                    actionKey: "split"
                                    windowId: root.targetId
                                    hint: "Change the split direction in your current tiling layout"
                                    enabled: root.can("split")
                                    onClicked: root.act("split", null)
                                }
                            }
                            Column {
                                width: parent.width
                                spacing: Style.space(8)
                                visible: root.dwindleTile
                                SectionHeading {
                                    text: "SWAP WITH NEIGHBOR"
                                }
                                GridLayout {
                                    width: parent.width
                                    columns: 4
                                    columnSpacing: Style.space(8)
                                    rowSpacing: Style.space(8)
                                    Repeater {
                                        model: [
                                            {
                                                text: "Left",
                                                arg: "l",
                                                icon: "left"
                                            },
                                            {
                                                text: "Up",
                                                arg: "u",
                                                icon: "up"
                                            },
                                            {
                                                text: "Down",
                                                arg: "d",
                                                icon: "down"
                                            },
                                            {
                                                text: "Right",
                                                arg: "r",
                                                icon: "right"
                                            }
                                        ]
                                        delegate: ActionButton {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            text: modelData.text
                                            iconName: modelData.icon
                                            enabled: root.can("swap")
                                            actionKey: "swap-" + modelData.arg
                                            windowId: root.targetId
                                            hint: "Swap this window with its " + modelData.text.toLowerCase() + " neighbor"
                                            onClicked: root.act("swap", modelData.arg)
                                        }
                                    }
                                }
                            }
                            Column {
                                width: parent.width
                                spacing: Style.space(8)
                                visible: root.can("resizeHorizontal") || root.can("resizeVertical")
                                SectionHeading {
                                    text: "RESIZE"
                                }
                                GridLayout {
                                    width: parent.width
                                    columns: 2
                                    columnSpacing: Style.space(8)
                                    rowSpacing: Style.space(8)
                                    Repeater {
                                        model: [
                                            {
                                                text: "Narrower",
                                                icon: "narrower",
                                                x: -200,
                                                y: 0
                                            },
                                            {
                                                text: "Wider",
                                                icon: "wider",
                                                x: 200,
                                                y: 0
                                            },
                                            {
                                                text: "Shorter",
                                                icon: "shorter",
                                                x: 0,
                                                y: -200
                                            },
                                            {
                                                text: "Taller",
                                                icon: "taller",
                                                x: 0,
                                                y: 200
                                            }
                                        ]
                                        delegate: ActionButton {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            text: modelData.text
                                            iconName: modelData.icon
                                            visible: root.can(modelData.x !== 0 ? "resizeHorizontal" : "resizeVertical")
                                            enabled: root.can("resize")
                                            actionKey: "resize"
                                            windowId: root.targetId
                                            hint: "Resize this window by 200 pixels using your current layout"
                                            onClicked: root.act("resize", modelData)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    Variants {
        model: root.opened && root.selectedScreen ? Quickshell.screens : []
        delegate: Component {
            PanelWindow {
                required property var modelData
                screen: modelData
                visible: root.opened && !!root.selectedScreen && modelData.name !== root.selectedScreen.name
                color: "transparent"
                exclusionMode: ExclusionMode.Ignore
                anchors {
                    top: true
                    bottom: true
                    left: true
                    right: true
                }
                WlrLayershell.namespace: "gooey-window-menu-dismiss"
                WlrLayershell.layer: WlrLayer.Overlay
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.AllButtons
                    onPressed: root.close()
                }
            }
        }
    }
}

import QtQuick
QtObject {
    property var widgets: []
    property var panel: null
    function registerWidget(widget) {
        if (widgets.indexOf(widget) < 0) widgets = widgets.concat([widget])
    }
    function unregisterWidget(widget) {
        widgets = widgets.filter(function(item) { return item !== widget })
    }
}

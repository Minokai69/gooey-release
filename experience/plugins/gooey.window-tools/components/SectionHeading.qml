import QtQuick
import qs.Commons

Row {
    property string text: ""
    property string detail: ""
    spacing: Style.space(8)
    Text {
        text: parent.text
        textFormat: Text.PlainText
        color: Color.popups.text
        font.family: Style.font.menuFamily
        font.pixelSize: Style.font.caption
        font.weight: Font.DemiBold
    }
    Text {
        visible: parent.detail !== ""
        text: parent.detail
        textFormat: Text.PlainText
        color: Color.popups.text
        opacity: 0.55
        font.family: Style.font.menuFamily
        font.pixelSize: Style.font.caption
    }
}

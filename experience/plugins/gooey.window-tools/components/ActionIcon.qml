import QtQuick
import qs.Commons

// Small line icons do not depend on a particular icon font.
Canvas {
    id: root
    property string name: ""
    property color stroke: Color.foreground
    implicitWidth: 20
    implicitHeight: 20
    onNameChanged: requestPaint()
    onStrokeChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var c = getContext("2d");
        c.reset();
        c.clearRect(0, 0, width, height);
        c.scale(width / 20, height / 20);
        c.strokeStyle = stroke;
        c.lineWidth = 1.5;
        c.lineCap = "round";
        c.lineJoin = "round";
        function line(points) {
            c.beginPath();
            c.moveTo(points[0], points[1]);
            for (var i = 2; i < points.length; i += 2)
                c.lineTo(points[i], points[i + 1]);
            c.stroke();
        }
        function box(x, y, w, h) {
            c.strokeRect(x, y, w, h);
        }
        function arrow(direction) {
            if (direction === "left") {
                line([16, 10, 4, 10]);
                line([8, 6, 4, 10, 8, 14]);
            }
            if (direction === "right") {
                line([4, 10, 16, 10]);
                line([12, 6, 16, 10, 12, 14]);
            }
            if (direction === "up") {
                line([10, 16, 10, 4]);
                line([6, 8, 10, 4, 14, 8]);
            }
            if (direction === "down") {
                line([10, 4, 10, 16]);
                line([6, 12, 10, 16, 14, 12]);
            }
        }
        switch (name) {
        case "close":
            line([5, 5, 15, 15]);
            line([15, 5, 5, 15]);
            break;
        case "check":
            line([4, 10, 8, 14, 16, 6]);
            break;
        case "back":
            arrow("left");
            break;
        case "left":
        case "right":
        case "up":
        case "down":
            arrow(name);
            break;
        case "shelf":
        case "unshelf":
            line([3, 12, 3, 16, 17, 16, 17, 12]);
            if (name === "shelf") {
                line([10, 3, 10, 12]);
                line([6, 8, 10, 12, 14, 8]);
            } else {
                line([10, 12, 10, 3]);
                line([6, 7, 10, 3, 14, 7]);
            }
            break;
        case "show":
            box(3, 4, 14, 12);
            line([3, 8, 17, 8]);
            break;
        case "workspace":
            box(3, 3, 5, 5);
            box(12, 3, 5, 5);
            box(3, 12, 5, 5);
            box(12, 12, 5, 5);
            break;
        case "float":
            box(7, 7, 10, 10);
            line([3, 13, 3, 3, 13, 3]);
            break;
        case "tile":
            box(3, 4, 14, 12);
            line([10, 4, 10, 16]);
            break;
        case "columns":
            box(7, 3, 6, 14);
            line([3, 3, 3, 17]);
            line([17, 3, 17, 17]);
            break;
        case "center":
            box(7, 4, 6, 12);
            line([1, 10, 5, 10]);
            line([3, 8, 5, 10, 3, 12]);
            line([19, 10, 15, 10]);
            line([17, 8, 15, 10, 17, 12]);
            break;
        case "maximize":
            line([7, 3, 3, 3, 3, 7]);
            line([13, 3, 17, 3, 17, 7]);
            line([3, 13, 3, 17, 7, 17]);
            line([13, 17, 17, 17, 17, 13]);
            break;
        case "restore":
            line([7, 3, 7, 7, 3, 7]);
            line([13, 3, 13, 7, 17, 7]);
            line([3, 13, 7, 13, 7, 17]);
            line([13, 17, 13, 13, 17, 13]);
            break;
        case "split":
            box(3, 3, 14, 14);
            line([10, 3, 10, 17]);
            line([10, 10, 17, 10]);
            break;
        case "narrower":
            line([2, 10, 7, 10]);
            line([4, 7, 7, 10, 4, 13]);
            line([18, 10, 13, 10]);
            line([16, 7, 13, 10, 16, 13]);
            break;
        case "wider":
            line([8, 10, 2, 10]);
            line([5, 7, 2, 10, 5, 13]);
            line([12, 10, 18, 10]);
            line([15, 7, 18, 10, 15, 13]);
            break;
        case "shorter":
            line([10, 2, 10, 7]);
            line([7, 4, 10, 7, 13, 4]);
            line([10, 18, 10, 13]);
            line([7, 16, 10, 13, 13, 16]);
            break;
        case "taller":
            line([10, 8, 10, 2]);
            line([7, 5, 10, 2, 13, 5]);
            line([10, 12, 10, 18]);
            line([7, 15, 10, 18, 13, 15]);
            break;
        }
    }
}

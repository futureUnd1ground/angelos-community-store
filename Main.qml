import QtQuick

// The store is intentionally a settings plugin. Registry work starts only when
// the page is opened, so an installed store has no background network activity.
QtObject {
    property var plugin
}

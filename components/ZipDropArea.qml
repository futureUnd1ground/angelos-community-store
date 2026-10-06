import QtQuick

DropArea {
    id: root
    signal fileSelected(string url)
    signal rejected(string message)

    function accepts(urls) {
        return urls && urls.length === 1 && /^file:\/\/(?:localhost)?\/[^?#]*\.zip$/i.test(String(urls[0]))
    }
    function select(urls) {
        if (!accepts(urls)) {
            rejected("Перетащи один локальный ZIP-архив плагина.")
            return false
        }
        fileSelected(String(urls[0]))
        return true
    }
    onEntered: drag => { drag.accepted = root.accepts(drag.urls) }
    onDropped: drop => {
        if (root.select(drop.urls))
            drop.acceptProposedAction()
    }
}

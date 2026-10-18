pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root
    property var plugin: null
    readonly property bool busy: publisher.running || auth.running
    property string login: ""
    property string message: ""
    property string error: ""
    property string prUrl: ""
    property string releaseUrl: ""

    function checkAuth() {
        if (!plugin || busy)
            return
        auth.command = ["python3", plugin.dir + "/scripts/publish-plugin.py", "auth"]
        auth.running = true
    }
    function publish(source) {
        if (!plugin || busy || !String(source || "").trim())
            return false
        message = "Публикую ZIP на GitHub и отправляю на проверку…"
        error = ""
        prUrl = ""
        releaseUrl = ""
        publisher.command = ["python3", plugin.dir + "/scripts/publish-plugin.py", "publish", String(source).trim()]
        publisher.running = true
        return true
    }
    Process {
        id: auth
        stdout: StdioCollector { id: authOutput }
        stderr: StdioCollector { id: authError }
        onExited: code => {
            try {
                root.login = code === 0 ? JSON.parse(authOutput.text).login : ""
                root.error = code === 0 ? "" : authError.text.trim()
            } catch (e) {
                root.error = "Не удалось проверить вход GitHub: " + String(e)
            }
        }
    }
    Process {
        id: publisher
        stdout: StdioCollector { id: publishOutput }
        stderr: StdioCollector { id: publishError }
        onExited: code => {
            if (code !== 0) {
                root.error = publishError.text.trim() || "Публикация не выполнена."
                root.message = ""
                return
            }
            try {
                const result = JSON.parse(publishOutput.text)
                root.message = result.message
                root.prUrl = result.url || ""
                root.releaseUrl = result.release || ""
                root.error = ""
            } catch (e) {
                root.error = "Не удалось прочитать результат публикации: " + String(e)
            }
        }
    }
}

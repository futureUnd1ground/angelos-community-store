import QtQuick
import Quickshell
import Quickshell.Io
import qs.services

// Search community plugins with: plugins <name, author, description, or tag>
Item {
    id: root
    visible: false
    width: 0
    height: 0

    property var plugin
    property string pluginId
    property var entries: []
    property string status: "loading"
    property string busyId: ""
    readonly property string prefix: "plugins"
    readonly property bool global: true
    readonly property string defaultRegistry: "https://raw.githubusercontent.com/futureUnd1ground/angelos-community-registry/main/plugins.json"
    signal changed

    onPluginChanged: if (plugin && status === "loading") fetch()

    function fetch() {
        if (!plugin)
            return
        const url = plugin ? plugin.get("registryUrl", defaultRegistry) : defaultRegistry
        registry.command = ["python3", plugin.dir + "/scripts/community-store.py", "fetch", url]
        registry.running = true
    }

    function newer(installed, latest) {
        const a = String(installed || "0").split(".").map(Number)
        const b = String(latest || "0").split(".").map(Number)
        for (let i = 0; i < Math.max(a.length, b.length); i++) {
            const x = Number.isFinite(a[i]) ? a[i] : 0
            const y = Number.isFinite(b[i]) ? b[i] : 0
            if (x !== y)
                return y > x
        }
        return false
    }

    function query(text, prefixed) {
        const q = String(text || "").trim().toLowerCase()
        if (status === "loading")
            return [{"id": "loading", "title": "Loading community plugins…", "subtitle": "", "icon": "package", "score": 1}]
        if (status === "error")
            return [{"id": "refresh", "title": "Community registry unavailable", "subtitle": "Press Enter to retry", "icon": "warning", "score": 1}]
        const out = []
        for (const entry of entries) {
            const id = String(entry.id || "")
            if (id === "community-store")
                continue
            const installed = Plugins.byId(id)
            const haystack = [entry.name, id, entry.author, entry.description, ...(entry.tags || []), entry.category].join(" ").toLowerCase()
            if (q && !haystack.includes(q))
                continue
            const label = entry.name || id
            const author = entry.author || "Unknown author"
            const score = q ? (String(entry.name || "").toLowerCase().startsWith(q) ? 80 : 40) : 10
            if (!installed) {
                out.push({"id": "install:" + id, "title": "Install: " + label, "subtitle": author + " · v" + entry.version, "icon": entry.icon || "package", "score": score})
                continue
            }
            if (newer(installed.version, entry.version))
                out.push({"id": "update:" + id, "title": "Update: " + label, "subtitle": "Installed v" + installed.version + " · latest v" + entry.version, "icon": entry.icon || "package", "score": score + 5})
            if (!installed.bundled && id !== "community-store")
                out.push({"id": "remove:" + id, "title": "Remove: " + label, "subtitle": "Installed v" + (installed.version || "?"), "icon": "trash", "score": score})
        }
        return out.slice(0, 30)
    }

    function activate(id) {
        if (id === "refresh") {
            fetch()
            return true
        }
        const action = id.slice(0, id.indexOf(":"))
        const pluginId = id.slice(id.indexOf(":") + 1)
        const entry = entries.find(item => item.id === pluginId)
        if (action === "remove") {
            if (pluginId === "community-store")
                return true
            Plugins.remove(pluginId)
            changed()
            return true
        }
        if ((action === "install" || action === "update") && entry && !installer.running) {
            busyId = pluginId
            installer.command = ["python3", plugin.dir + "/scripts/community-store.py", "install", entry.source, entry.id, String(entry.version)]
            installer.running = true
        }
        return true
    }

    Process {
        id: registry
        stdout: StdioCollector { id: registryOutput }
        stderr: StdioCollector { id: registryError }
        onExited: code => {
            if (code !== 0) {
                root.status = "error"
                console.warn("Community Store launcher registry:", registryError.text)
                root.changed()
                return
            }
            try {
                const payload = JSON.parse(registryOutput.text)
                root.entries = payload.plugins.filter(item => item && item.status === "approved")
                root.status = "ready"
            } catch (e) {
                root.status = "error"
                console.warn("Community Store launcher registry:", e)
            }
            root.changed()
        }
    }

    Process {
        id: installer
        stdout: StdioCollector { id: installOutput }
        stderr: StdioCollector { id: installError }
        onExited: code => {
            root.busyId = ""
            if (code === 0) {
                Plugins.reload()
                root.status = "ready"
            } else {
                console.warn("Community Store launcher install:", installError.text || installOutput.text)
            }
            root.changed()
        }
    }
}

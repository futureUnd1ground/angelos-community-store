pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import qs.config
import qs.services

Singleton {
    id: root
    property var plugin: null
    property string defaultUrl: "https://raw.githubusercontent.com/futureUnd1ground/angelos-community-registry/main/plugins.json"
    property string url: ""
    property var entries: []
    property string error: ""
    property string status: "idle"
    property bool busy: fetcher.running || installer.running || batchActive || shellRestart.running
    property var updateQueue: []
    property bool batchActive: false
    property int batchTotal: 0
    property int batchDone: 0
    property int batchFailed: 0
    property var batchErrors: []
    property bool autoUpdateAttempted: false
    property bool autoUpdate: false
    property bool automaticRun: false
    property int revision: 0
    property string lastMessage: ""
    readonly property var storeEntry: entries.find(p => p.id === "community-store") || null
    readonly property int availablePluginUpdates: entries.filter(p => p.id !== "community-store" && installed(p.id) && newer(version(p.id), p.version)).length
    readonly property bool storeUpdateAvailable: !!storeEntry && !!installed("community-store") && newer(version("community-store"), storeEntry.version)
    signal changed
    signal operationFinished(bool ok, string message)

    Component.onCompleted: {
        if (!plugin)
            return
        url = plugin.get("registryUrl", defaultUrl)
        fetch()
    }

    function fetch() {
        if (busy || !plugin)
            return
        error = ""
        lastMessage = ""
        status = "loading"
        fetcher.command = ["python3", plugin.dir + "/scripts/community-store.py", "fetch", url || defaultUrl]
        fetcher.running = true
    }

    function install(entry) {
        if (!entry || !plugin || busy)
            return false
        return startInstall(entry)
    }

    function installLocal(source) {
        const file = String(source || "").trim()
        if (!file || !plugin || busy)
            return false
        error = ""
        lastMessage = ""
        status = "installing"
        installer.command = ["python3", plugin.dir + "/scripts/community-store.py", "install-local", file]
        installer.running = true
        return true
    }

    function startInstall(entry) {
        if (!entry || !plugin || installer.running || fetcher.running)
            return false
        error = ""
        lastMessage = ""
        status = "installing"
        installer.command = ["python3", plugin.dir + "/scripts/community-store.py", "install",
                             entry.source || "", entry.id || "", entry.version || ""]
        installer.running = true
        return true
    }

    // Reinstalling deliberately goes through the same verified installer. The
    // Python helper stages the archive and moves the old copy to plugin-trash
    // before replacing it, so a failed download leaves the working plugin intact.
    function reinstall(entry) {
        install(entry)
    }

    function setAutoUpdate(value) {
        autoUpdate = !!value
        if (autoUpdate && status === "ready")
            maybeAutoUpdate()
    }

    function maybeAutoUpdate() {
        if (!autoUpdate || busy || Plugins.scanning || automaticRun || autoUpdateAttempted)
            return
        autoUpdateAttempted = true
        updateAllPlugins(true)
    }

    function updateAllPlugins(automatic) {
        if (busy || !plugin || Plugins.scanning)
            return
        automaticRun = automatic === true
        updateQueue = entries.filter(p => p.id !== "community-store" && installed(p.id) && newer(version(p.id), p.version))
        batchTotal = updateQueue.length
        batchDone = 0
        batchFailed = 0
        batchErrors = []
        batchActive = batchTotal > 0
        if (batchActive)
            installNext()
        else
            automaticRun = false
    }

    function installNext() {
        if (updateQueue.length === 0) {
            status = batchFailed > 0 ? "error" : "ready"
            error = batchErrors.join("\n")
            lastMessage = "Обновлено: " + (batchDone - batchFailed) + "/" + batchTotal
            batchActive = false
            automaticRun = false
            if (batchDone > batchFailed)
                shellRestart.restart()
            return
        }
        const entry = updateQueue[0]
        updateQueue = updateQueue.slice(1)
        startInstall(entry)
    }

    function uninstall(id) {
        if (busy)
            return false
        // Community Store is the manager itself. Removing it would make the
        // settings page and all recovery actions disappear until a manual
        // reinstall, so it is intentionally never removable from the store.
        if (String(id || "") === "community-store") {
            lastMessage = "Community Store нельзя удалить из самого магазина."
            return false
        }
        Plugins.remove(id)
        // Plugins reloads after its asynchronous move has completed.
        touch()
        return true
    }

    function installed(id) {
        return Plugins.byId(id)
    }

    function version(id) {
        const p = installed(id)
        return p ? String(p.version || "0") : ""
    }

    function newer(installedVersion, latestVersion) {
        const a = String(installedVersion || "0").split(".").map(Number)
        const b = String(latestVersion || "0").split(".").map(Number)
        for (let i = 0; i < Math.max(a.length, b.length); i++) {
            const x = Number.isFinite(a[i]) ? a[i] : 0
            const y = Number.isFinite(b[i]) ? b[i] : 0
            if (y !== x)
                return y > x
        }
        return false
    }

    function setRegistry(value) {
        const next = String(value || "").trim()
        if (busy || !next || !next.startsWith("https://"))
            return false
        url = next
        if (plugin)
            plugin.set("registryUrl", next)
        fetch()
        return true
    }

    function touch() {
        revision++
        changed()
    }

    Connections {
        target: Plugins
        function onScanningChanged() {
            if (!Plugins.scanning && root.status === "ready")
                root.maybeAutoUpdate()
        }
    }

    Process {
        id: fetcher
        stdout: StdioCollector { id: fetchOutput }
        stderr: StdioCollector { id: fetchError }
        onExited: code => {
            if (code !== 0) {
                root.status = "error"
                root.error = fetchError.text || "Could not load the registry."
                return
            }
            try {
                const payload = JSON.parse(fetchOutput.text)
                if (!payload || payload.version !== 1 || !Array.isArray(payload.plugins))
                    throw new Error("Unsupported registry format")
                root.entries = payload.plugins.filter(p => p && p.status === "approved" && typeof p.id === "string" && typeof p.name === "string" && typeof p.source === "string")
                root.status = "ready"
                root.autoUpdateAttempted = false
                root.touch()
                root.maybeAutoUpdate()
            } catch (e) {
                root.status = "error"
                root.error = String(e)
            }
        }
    }

    Process {
        id: installer
        stdout: StdioCollector { id: installOutput }
        stderr: StdioCollector { id: installError }
        onExited: code => {
            const message = (code === 0 ? installOutput.text : installError.text).trim()
            root.status = code === 0 ? "ready" : "error"
            root.error = code === 0 ? "" : (message || "Installation failed.")
            root.lastMessage = message
            Plugins.reload()
            root.touch()
            root.operationFinished(code === 0, message)
            if (root.batchActive) {
                root.batchDone++
                if (code !== 0) {
                    root.batchFailed++
                    root.batchErrors = root.batchErrors.concat([installer.command[4] + ": " + root.error])
                }
                nextInstall.start()
            } else if (code === 0) {
                shellRestart.restart()
            }
        }
    }

    Timer {
        id: nextInstall
        interval: 350
        onTriggered: root.installNext()
    }
    Timer {
        id: shellRestart
        interval: 1000
        onTriggered: Quickshell.execDetached(["angelos", "restart"])
    }
}

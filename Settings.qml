import QtQuick
import Quickshell
import qs.config
import qs.widgets
import qs.services
import "services"
import "components" as Cards
import "Categories.js" as Categories

// PluginSettingsPage already provides the outer PxPage. Plugin settings must
// therefore be a normal item with an implicit height.
Column {
    id: page

    property var plugin
    property string search: ""
    property string category: "All"
    property string registryInput: ""
    property var selected: null
    property var selectedInstalled: null
    property bool autoUpdate: plugin ? plugin.get("autoUpdate", false) : false
    property real interfaceScale: {
        const value = Number(plugin ? plugin.get("interfaceScale", 1) : 1)
        return value > 0 ? Math.max(0.8, Math.min(1.2, value)) : 1
    }
    property string operationMessage: ""
    property bool confirmingSelectedRemove: false
    readonly property var availableEntries: Registry.entries.filter(page.matches)
    readonly property var installedEntries: Plugins.plugins.filter(entry => page.matches(Object.assign({}, entry, Registry.entries.find(r => r.id === entry.id) || {})))

    width: parent ? parent.width : Theme.u * 150
    spacing: Theme.u * 5

    // Keep the scale local to this plugin page. The outer item reports the
    // scaled height to AngelOS, so the settings scroll view remains correct.
    Item {
        id: scaledArea
        width: page.width
        height: content.implicitHeight * page.interfaceScale

        Column {
            id: content
            width: page.width / page.interfaceScale
            scale: page.interfaceScale
            transformOrigin: Item.TopLeft
            spacing: Theme.u * 5

            PxGroup {
                width: parent.width
                title: "Настройки Community Store"
                icon: "settings"

                SettingRow {
                    label: "Автоматически обновлять плагины"
                    hint: "Проверять registry при открытии и устанавливать доступные обновления."
                    PxToggle {
                        checked: page.autoUpdate
                        onToggled: checked => page.setAutoUpdate(checked)
                    }
                }

                SettingRow {
                    label: "Размер интерфейса"
                    hint: "Меняет только страницу Community Store."
                    PxSegmented {
                        model: [
                            {"label": "80%", "value": 0.8},
                            {"label": "100%", "value": 1},
                            {"label": "120%", "value": 1.2}
                        ]
                        currentValue: page.interfaceScale
                        onActivated: value => page.setInterfaceScale(value)
                    }
                }

                PxText {
                    width: parent.width
                    text: Registry.status === "loading" ? "Проверяю registry…" : Registry.error || page.operationMessage || "Готово"
                    color: Registry.error ? Theme.danger : Theme.textDim
                    wrapMode: Text.Wrap
                }

                Row {
                    spacing: Theme.u * 2
                    PxButton {
                        compact: true
                        text: "Обновить registry"
                        icon: "refresh"
                        enabled: !Registry.busy
                        onClicked: Registry.fetch()
                    }
                    PxButton {
                        compact: true
                        text: "Обновить все"
                        icon: "download"
                        enabled: !Registry.busy && Registry.availablePluginUpdates > 0
                        onClicked: Registry.updateAllPlugins(false)
                    }
                }
            }

            PxField {
                width: parent.width
                icon: "search"
                placeholder: "Поиск плагинов по названию, автору, описанию или тегу"
                text: page.search
                onEdited: page.search = text
            }

            Flow {
                width: parent.width
                spacing: Theme.u * 2
                PxButton {
                    compact: true
                    text: I18n.t("Все", "All")
                    checked: page.category === "All"
                    onClicked: page.category = "All"
                }
                Repeater {
                    model: Categories.groups(Registry.entries)
                    PxCombo {
                        required property var modelData
                        width: Math.min(Theme.u * 100, parent.width)
                        model: modelData.items.map(c => ({label: I18n.t(c.ru, c.en), value: c.id}))
                        placeholder: I18n.t(modelData.ru, modelData.en)
                        currentValue: page.category
                        onActivated: v => page.category = v
                    }
                }
            }

            PxGroup {
                width: parent.width
                title: "Установленные плагины (" + page.installedEntries.length + " / " + Plugins.plugins.length + ")"
                icon: "plug"

                Repeater {
                    model: page.installedEntries
                    Cards.InstalledPluginCard {
                        required property int index
                        property int rowIndex: index
                        entry: page.installedEntries[rowIndex]
                        onShowDetails: entry => page.selectedInstalled = entry
                    }
                }
                PxText {
                    visible: Plugins.scanning
                    text: "Читаю установленные плагины…"
                    dim: true
                }
                PxText {
                    visible: !Plugins.scanning && page.installedEntries.length === 0
                    text: Plugins.plugins.length === 0 ? "Установленных плагинов нет." : "Установленных плагинов в этой категории или поиске нет."
                    dim: true
                }
            }

            PxGroup {
                width: parent.width
                title: "Доступные плагины (" + page.availableEntries.length + ")"
                icon: "package"

                Repeater {
                    model: page.availableEntries
                    Cards.PluginCard {
                        required property int index
                        property int rowIndex: index
                        entry: page.availableEntries[rowIndex]
                        onOpenDetails: entry => page.selected = entry
                    }
                }
                PxText {
                    visible: !Registry.busy && page.availableEntries.length === 0
                    text: Registry.error ? "Не удалось загрузить registry." : "Плагины не найдены."
                    dim: true
                }
            }

            PxGroup {
                width: parent.width
                title: "Registry"
                icon: "cloud"

                PxText {
                    width: parent.width
                    text: Registry.status === "loading" ? "Загружаю registry…" : Registry.error || (Registry.entries.length + " одобренных плагинов загружено")
                    dim: true
                    wrapMode: Text.Wrap
                }
                PxField {
                    width: parent.width
                    text: page.registryInput
                    placeholder: "HTTPS-адрес plugins.json"
                    onEdited: page.registryInput = text
                }
                Row {
                    spacing: Theme.u * 2
                    PxButton {
                        compact: true
                        text: "Сохранить адрес"
                        icon: "save"
                        enabled: !Registry.busy
                        onClicked: Registry.setRegistry(page.registryInput)
                    }
                    PxButton {
                        compact: true
                        text: "Открыть registry"
                        icon: "external"
                        onClicked: Quickshell.execDetached(["xdg-open", "https://github.com/futureUnd1ground/angelos-community-registry"])
                    }
                }
            }

            PxGroup {
                visible: !!page.selectedInstalled
                width: parent.width
                title: page.selectedInstalled ? I18n.label(page.selectedInstalled.name) : "Данные плагина"

                PxText {
                    width: parent.width
                    text: page.selectedInstalled ? I18n.label(page.selectedInstalled.description || "") +
                        "\n\nID: " + page.selectedInstalled.id +
                        "\nVersion: " + (page.selectedInstalled.version || "0") +
                        "\nAuthor: " + (page.selectedInstalled.author || "Unknown") +
                        "\nLocation: " + page.selectedInstalled.dir : ""
                    wrapMode: Text.Wrap
                }
                Row {
                    spacing: Theme.u * 2
                    PxButton {
                        compact: true
                        text: "Открыть папку"
                        icon: "folder"
                        onClicked: Shell.openPath(page.selectedInstalled.dir)
                    }
                    PxButton {
                        compact: true
                        text: "Закрыть"
                        icon: "close"
                        onClicked: page.selectedInstalled = null
                    }
                }
            }

            PxGroup {
                visible: !!page.selected
                width: parent.width
                title: page.selected ? page.selected.name : "Данные плагина"

                PxText {
                    width: parent.width
                    text: page.selected ? ((page.selected.description || "") +
                        "\n\nby " + (page.selected.author || "Unknown") +
                        "\nLatest version: " + (page.selected.version || "0") +
                        (Registry.installed(page.selected.id) ? "\nInstalled version: " + Registry.version(page.selected.id) : "\nNot installed") +
                        "\nMinimum AngelOS: " + (page.selected.minAngelOSVersion || "Not specified") +
                        "\nTags: " + (page.selected.tags || []).join(", ") +
                        "\nDependencies: " + (page.selected.dependencies || []).join(", ") +
                        "\nPermissions: " + (page.selected.permissions || []).join(", ") +
                        "\nLicense: " + (page.selected.license || "Not specified") +
                        (page.selected.homepage ? "\nHomepage: " + page.selected.homepage : "") +
                        (page.selected.changelog ? "\nChangelog: " + page.selected.changelog : "")) : ""
                    wrapMode: Text.Wrap
                }
                Row {
                    spacing: Theme.u * 2
                    PxButton {
                        compact: true
                        visible: !!page.selected
                        text: page.selected && !Registry.installed(page.selected.id) ? "Скачать" : page.selected && Registry.newer(Registry.version(page.selected.id), page.selected.version) ? "Обновить" : "Переустановить"
                        icon: "download"
                        enabled: !!page.selected && !Registry.busy
                        onClicked: {
                            if (!page.selected)
                                return
                            if (Registry.installed(page.selected.id) && !Registry.newer(Registry.version(page.selected.id), page.selected.version))
                                Registry.reinstall(page.selected)
                            else
                                Registry.install(page.selected)
                        }
                    }
                    PxButton {
                        compact: true
                        visible: !!page.selected && !!Registry.installed(page.selected.id) && page.selected.id !== "community-store"
                        danger: true
                        text: page.confirmingSelectedRemove ? "Подтвердить удаление" : "Удалить"
                        icon: "trash"
                        enabled: !Registry.busy
                        onClicked: {
                            if (!page.confirmingSelectedRemove) {
                                page.confirmingSelectedRemove = true
                                removeConfirmReset.restart()
                                return
                            }
                            page.confirmingSelectedRemove = false
                            Registry.uninstall(page.selected.id)
                        }
                    }
                    PxButton {
                        compact: true
                        text: "Закрыть"
                        icon: "close"
                        onClicked: page.selected = null
                    }
                }
            }

            PxText {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: "made by future, MixaDods dotfiles"
                color: Theme.textDim
                kind: "tiny"
            }
        }
    }

    Timer {
        id: removeConfirmReset
        interval: 4000
        onTriggered: page.confirmingSelectedRemove = false
    }

    Connections {
        target: Registry
        function onOperationFinished(ok, message) {
            page.operationMessage = message || (ok ? "Operation completed." : "Operation failed.")
        }
    }

    Component.onCompleted: {
        page.registryInput = plugin ? plugin.get("registryUrl", Registry.defaultUrl) : Registry.defaultUrl
        Registry.plugin = plugin
        Registry.url = page.registryInput
        Registry.fetch()
        Registry.setAutoUpdate(page.autoUpdate)
    }

    function matches(entry) {
        const q = page.search.trim().toLowerCase()
        const hay = Categories.searchText(entry).toLowerCase()
        return (!q || hay.includes(q)) && Categories.matches(entry, page.category)
    }

    function setAutoUpdate(value) {
        page.autoUpdate = !!value
        if (page.plugin)
            page.plugin.set("autoUpdate", page.autoUpdate)
        Registry.setAutoUpdate(page.autoUpdate)
    }

    function setInterfaceScale(value) {
        page.interfaceScale = Math.max(0.8, Math.min(1.2, Number(value) || 1))
        if (page.plugin)
            page.plugin.set("interfaceScale", page.interfaceScale)
    }
}

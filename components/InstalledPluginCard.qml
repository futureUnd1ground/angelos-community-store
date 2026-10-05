import QtQuick
import Quickshell
import qs.config
import qs.widgets
import qs.services
import "../services"

PxBox {
    id: card

    required property var entry
    readonly property int registryRevision: Registry.revision
    readonly property var catalogEntry: {
        const revision = registryRevision
        return entry ? Registry.entries.find(item => item.id === entry.id) || null : null
    }
    readonly property bool updateAvailable: !!catalogEntry && Registry.newer(String(entry.version || "0"), String(catalogEntry.version || "0"))
    readonly property bool isStore: !!entry && entry.id === "community-store"
    property bool confirmingRemove: false
    property bool confirmingReinstall: false
    signal showDetails(var entry)

    width: parent ? parent.width : 500
    height: content.implicitHeight + Theme.u * 8
    color: Theme.face

    Timer {
        id: confirmationReset
        interval: 4000
        onTriggered: {
            card.confirmingRemove = false
            card.confirmingReinstall = false
        }
    }

    Column {
        id: content
        x: Theme.u * 4
        y: Theme.u * 4
        width: parent.width - Theme.u * 8
        spacing: Theme.u * 2

        Row {
            width: parent.width
            spacing: Theme.u * 4
            PxIcon {
                name: card.entry && card.entry.icon || "plug"
                pixel: Theme.u * 3
            }
            Column {
                width: parent.width - parent.spacing - Theme.u * 3
                spacing: Theme.u
                PxText {
                    width: parent.width
                    text: card.entry ? I18n.label(card.entry.name) + "  v" + (card.entry.version || "0") : ""
                    font.bold: true
                    elide: Text.ElideRight
                }
                PxText {
                    width: parent.width
                    text: card.entry ? I18n.label(card.entry.description || "") : ""
                    wrapMode: Text.Wrap
                    dim: true
                }
                PxText {
                    width: parent.width
                    text: card.entry ? (card.isStore ? "Системный менеджер · удаление отключено" : (card.entry.bundled ? "Встроенный" : "Пользовательский плагин") + (card.entry.author ? " · " + card.entry.author : "")) : ""
                    kind: "tiny"
                    dim: true
                    elide: Text.ElideRight
                }
                PxText {
                    visible: card.updateAvailable
                    text: card.catalogEntry ? "Доступно обновление: v" + card.catalogEntry.version : ""
                    kind: "tiny"
                    color: Theme.accent
                }
            }
        }
        Flow {
            width: parent.width
            spacing: Theme.u * 2
            PxToggle {
                checked: card.entry ? Plugins.isEnabled(card.entry) : false
                text: checked ? "Включён" : "Выключен"
                onToggled: checked => { if (card.entry) Plugins.setEnabled(card.entry.id, checked) }
            }
            PxButton {
                compact: true
                text: "Подробнее"
                icon: "info"
                enabled: !!card.entry
                onClicked: card.showDetails(card.entry)
            }
            PxButton {
                compact: true
                text: "Папка"
                icon: "folder"
                enabled: !!card.entry
                onClicked: Shell.openPath(card.entry.dir)
            }
            PxButton {
                visible: !!card.catalogEntry && !card.entry.bundled && card.updateAvailable
                compact: true
                text: "Обновить"
                icon: "download"
                enabled: !Registry.busy
                onClicked: Registry.install(card.catalogEntry)
            }
            PxButton {
                visible: !!card.catalogEntry && !card.entry.bundled
                compact: true
                text: card.confirmingReinstall ? "Подтвердить" : "Переустановить"
                icon: "refresh"
                enabled: !Registry.busy
                onClicked: {
                    if (!card.confirmingReinstall) {
                        card.confirmingReinstall = true
                        card.confirmingRemove = false
                        confirmationReset.restart()
                        return
                    }
                    card.confirmingReinstall = false
                    Registry.reinstall(card.catalogEntry)
                }
            }
            PxButton {
                compact: true
                danger: true
                visible: !card.isStore
                text: card.confirmingRemove ? "Подтвердить" : (card.entry && card.entry.bundled ? "Скрыть" : "Удалить")
                icon: "trash"
                enabled: !!card.entry
                onClicked: {
                    if (!card.confirmingRemove) {
                        card.confirmingRemove = true
                        card.confirmingReinstall = false
                        confirmationReset.restart()
                        return
                    }
                    card.confirmingRemove = false
                    Registry.uninstall(card.entry.id)
                }
            }
        }
    }
}

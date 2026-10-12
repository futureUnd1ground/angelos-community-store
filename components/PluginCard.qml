import QtQuick
import Quickshell
import qs.config
import qs.widgets
import "../services"

PxBox {
    id: card

    required property var entry
    readonly property int registryRevision: Registry.revision
    readonly property var local: {
        const revision = registryRevision
        return entry ? Registry.installed(entry.id) : null
    }
    readonly property bool isStore: !!entry && entry.id === "community-store"
    readonly property string repositoryUrl: entry ? String(entry.repository || entry.homepage || (entry.id === "community-store" ? "https://github.com/futureUnd1ground/angelos-community-store" : "")) : ""
    property bool confirmingRemove: false
    property bool confirmingReinstall: false
    signal openDetails(var entry)

    width: parent ? parent.width : 500
    height: cardColumn.implicitHeight + Theme.u * 8
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
        id: cardColumn
        x: Theme.u * 4
        y: Theme.u * 4
        width: parent.width - Theme.u * 8
        spacing: Theme.u * 2

        Row {
            width: parent.width
            spacing: Theme.u * 4
            PxIcon {
                name: card.entry && card.entry.icon || "package"
                pixel: Theme.u * 3
                anchors.top: parent.top
            }
            Column {
                width: parent.width - parent.spacing - Theme.u * 3
                spacing: Theme.u
                PxText {
                    width: parent.width
                    text: card.entry ? card.entry.name : ""
                    font.bold: true
                    elide: Text.ElideRight
                }
                PxText {
                    width: parent.width
                    text: card.entry ? "by " + (card.entry.author || "Unknown") + "  ·  v" + (card.entry.version || "0") : ""
                    kind: "tiny"
                    dim: true
                    elide: Text.ElideRight
                }
                PxText {
                    width: parent.width
                    text: card.entry ? card.entry.description || "" : ""
                    wrapMode: Text.Wrap
                    dim: true
                }
                PxText {
                    width: parent.width
                    text: card.entry ? (card.entry.tags || []).join("  ·  ") : ""
                    kind: "tiny"
                    dim: true
                    visible: !!card.entry && (card.entry.tags || []).length > 0
                    elide: Text.ElideRight
                }
                PxText {
                    text: !card.local ? "Не установлен" : Registry.newer(Registry.version(card.entry.id), card.entry.version) ? "Доступно обновление" : "Установлен"
                    kind: "tiny"
                    color: Registry.newer(Registry.version(card.entry.id), card.entry.version) ? Theme.accent : Theme.textDim
                }
            }
        }

        Flow {
            width: parent.width
            spacing: Theme.u * 2
            PxButton {
                compact: true
                text: !card.local ? "Скачать" : Registry.newer(Registry.version(card.entry.id), card.entry.version) ? "Обновить" : "Установлен"
                icon: !card.local ? "download" : Registry.newer(Registry.version(card.entry.id), card.entry.version) ? "refresh" : "check"
                enabled: !!card.entry && !Registry.busy && (!card.local || Registry.newer(Registry.version(card.entry.id), card.entry.version))
                onClicked: Registry.install(card.entry)
            }
            PxButton {
                visible: !!card.local
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
                    Registry.reinstall(card.entry)
                }
            }
            PxButton {
                compact: true
                danger: true
                visible: !!card.local && !card.isStore
                text: card.confirmingRemove ? "Подтвердить" : "Удалить"
                icon: "trash"
                enabled: !Registry.busy
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
            PxButton {
                compact: true
                text: "Подробнее"
                icon: "info"
                enabled: card.repositoryUrl !== ""
                onClicked: Quickshell.execDetached(["xdg-open", card.repositoryUrl])
            }
        }
    }
}

.pragma library

// Stable registry IDs; labels are translated only for display.
var definitions = [
    {id: "All", ru: "Все", en: "All", aliases: []},
    {id: "Story", ru: "Сюжет", en: "Story", aliases: ["stories", "narrative", "lore", "chapter", "chapters", "story packs", "сюжет", "истории", "главы"]},
    {id: "Novels", ru: "Визуальные новеллы", en: "Visual novels", aliases: ["novel", "visual novel", "visual novels", "новелла", "новеллы"]},
    {id: "Quests", ru: "Квесты", en: "Quests", aliases: ["quest", "missions", "квест", "квесты", "задания"]},
    {id: "Characters", ru: "Персонажи", en: "Characters", aliases: ["character", "npc", "персонаж", "персонажи"]},
    {id: "Realms", ru: "Миры и измерения", en: "Worlds & realms", aliases: ["world", "worlds", "realm", "dimensions", "heaven", "hell", "circle", "circles", "миры", "измерения", "рай", "ад", "круги"]},
    {id: "Dialogue", ru: "Диалоги и сцены", en: "Dialogue & scenes", aliases: ["dialogues", "dialog", "scene", "scenes", "диалоги", "сцены"]},
    {id: "Minigames", ru: "Мини-игры", en: "Minigames", aliases: ["minigame", "games", "game", "mini games", "мини игры", "игры"]},
    {id: "Voices", ru: "Голоса и озвучка", en: "Voices", aliases: ["voice", "voice packs", "озвучка", "голоса"]},
    {id: "Pets", ru: "Питомцы", en: "Pets", aliases: ["pet", "catwalk", "питомцы"]},
    {id: "Widgets", ru: "Виджеты", en: "Widgets", aliases: ["widget", "виджеты"]},
    {id: "Desktop", ru: "Рабочий стол", en: "Desktop", aliases: ["рабочий стол"]},
    {id: "Bar", ru: "Панель", en: "Bar", aliases: ["panel", "панель"]},
    {id: "Themes", ru: "Оформление", en: "Themes", aliases: ["theme", "palette", "palettes", "тема", "темы", "оформление"]},
    {id: "Skins", ru: "Скины интерфейса", en: "Interface skins", aliases: ["skin", "settings skin", "golden gate", "скины"]},
    {id: "Wallpapers", ru: "Обои", en: "Wallpapers", aliases: ["wallpaper", "обои"]},
    {id: "Cursors", ru: "Курсоры", en: "Cursors", aliases: ["cursor", "курсор", "курсоры"]},
    {id: "Fonts", ru: "Шрифты", en: "Fonts", aliases: ["font", "typography", "шрифты"]},
    {id: "Icons", ru: "Значки", en: "Icons", aliases: ["icon", "icon packs", "значки", "иконки"]},
    {id: "Effects", ru: "Эффекты и анимации", en: "Effects & animations", aliases: ["effect", "animation", "animations", "эффекты", "анимации"]},
    {id: "AI", ru: "AI-помощники", en: "AI assistants", aliases: ["claude", "codex", "ai assistant", "ai assistants", "ии"]},
    {id: "DeveloperTools", ru: "Разработка", en: "Developer tools", aliases: ["developer", "development", "dev", "coding", "разработка"]},
    {id: "Launcher", ru: "Лаунчер и поиск", en: "Launcher & search", aliases: ["launchers", "search", "лаунчер", "поиск"]},
    {id: "Network", ru: "Сеть", en: "Network", aliases: ["networking", "сеть"]},
    {id: "Audio", ru: "Музыка и звук", en: "Music & audio", aliases: ["music", "sound", "музыка", "звук"]},
    {id: "Productivity", ru: "Продуктивность", en: "Productivity", aliases: ["workflow", "продуктивность"]},
    {id: "Integrations", ru: "Интеграции", en: "Integrations", aliases: ["integration", "интеграции"]},
    {id: "Accessibility", ru: "Доступность", en: "Accessibility", aliases: ["a11y", "доступность"]},
    {id: "System", ru: "Система", en: "System", aliases: ["system tools", "system-monitor", "система"]},
    {id: "Utilities", ru: "Утилиты", en: "Utilities", aliases: ["utility", "tools", "утилиты"]}
];
var narrativeIds = ["Story", "Novels", "Quests", "Characters", "Realms", "Dialogue", "Voices"];
var appearanceIds = ["Themes", "Skins", "Wallpapers", "Cursors", "Fonts", "Icons", "Effects"];
var narrativeTags = ["story", "stories", "narrative", "lore", "chapter", "chapters", "quest", "quests", "npc", "dialogue", "dialogues", "scene", "scenes", "novel", "novels", "visual novel", "visual novels", "сюжет", "истории", "квест", "квесты", "диалоги", "сцены"];

function normalize(value) {
    return String(value || "").trim().toLowerCase().replace(/[ _-]+/g, " ");
}
function canonical(value) {
    var key = normalize(value);
    for (var i = 0; i < definitions.length; ++i) {
        var d = definitions[i];
        if (normalize(d.id) === key || d.aliases.some(function(a) { return normalize(a) === key; })) return d.id;
    }
    return "";
}
function choices(entries) {
    var result = definitions.slice();
    var seen = Object.create(null);
    for (var i = 0; i < (entries || []).length; ++i) {
        var raw = String(entries[i].category || "").trim();
        var key = normalize(raw);
        if (!raw || canonical(raw) || seen[key]) continue;
        seen[key] = true;
        result.push({id: raw, ru: raw, en: raw, aliases: []});
    }
    return result;
}
function matches(entry, selected) {
    if (selected === "All") return true;
    var id = canonical(selected) || String(selected);
    var category = canonical(entry.category);
    var tags = (entry.tags || []).map(normalize);
    if (id === "Story") {
        return narrativeIds.indexOf(category) !== -1 || tags.some(function(t) { return narrativeTags.indexOf(t) !== -1 || canonical(t) === "Story"; });
    }
    if (id === "Themes" && (appearanceIds.indexOf(category) !== -1 || tags.some(function(t) { return appearanceIds.indexOf(canonical(t)) !== -1; }))) return true;
    if (id === "Audio" && category === "Voices") return true;
    if (category === id || normalize(entry.category) === normalize(id)) return true;
    return tags.some(function(t) { return canonical(t) === id || t === normalize(id); });
}
function searchTerms(entry) {
    return definitions.filter(function(d) { return d.id !== "All" && matches(entry, d.id); }).map(function(d) { return d.ru + " " + d.en; }).join(" ");
}

function groups(entries) {
    var result = [
        {ru: "Сюжет и игра", en: "Story & games", items: []},
        {ru: "Оформление", en: "Appearance", items: []},
        {ru: "Плагины и инструменты", en: "Plugins & tools", items: []}
    ];
    choices(entries).forEach(function(c) {
        if (c.id === "All") return;
        var index = narrativeIds.indexOf(c.id) !== -1 || c.id === "Minigames" ? 0 : appearanceIds.indexOf(c.id) !== -1 ? 1 : 2;
        result[index].items.push(c);
    });
    return result;
}

function searchText(entry) {
    var values = [entry.name, entry.author, entry.description, entry.category, searchTerms(entry)].concat(entry.tags || []);
    return values.map(function(v) {
        if (v && typeof v === "object") return Object.keys(v).map(function(k) { return v[k]; }).join(" ");
        return String(v || "");
    }).join(" ");
}

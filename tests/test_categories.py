"""Run real category rules in Qt's JavaScript engine."""
import os, shutil, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNNER=shutil.which('qmltestrunner6') or '/usr/lib/qt6/bin/qmltestrunner'

class CategoryTests(unittest.TestCase):
    def test_category_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);shutil.copyfile(ROOT/'Categories.js',root/'Categories.js')
            (root/'tst_categories.qml').write_text('''import QtQuick
import QtTest
import "Categories.js" as Categories
TestCase {
 name: "MarketCategories"
 function test_story_contains_native_story_types() {
   for (const id of ["Story","Novels","Quests","Characters","Realms","Dialogue","Voices"])
     verify(Categories.matches({category:id,tags:[]},"Story"),id);
   verify(Categories.matches({category:"Utilities",tags:["lore"]},"Story"));
   verify(!Categories.matches({category:"Widgets",tags:["pet"]},"Story"));
   verify(!Categories.matches({category:"Utilities",tags:["game"]},"Story"));
 }
 function test_appearance_contains_native_asset_types() {
   for (const id of ["Skins","Wallpapers","Cursors","Fonts","Icons","Effects"])
     verify(Categories.matches({category:id},"Themes"),id);
   verify(Categories.matches({category:"Desktop",tags:["cursor"]},"Themes"));
   verify(!Categories.matches({category:"Utilities",tags:["network"]},"Themes"));
 }
 function test_installed_plugin_tags() {
   verify(Categories.matches({category:"Utilities",tags:["claude","developer"]},"AI"));
   verify(Categories.matches({category:"Utilities",tags:["codex","developer"]},"DeveloperTools"));
   verify(Categories.matches({category:"Desktop",tags:["catwalk"]},"Pets"));
   verify(Categories.matches({category:"Utilities",tags:["osu","game"]},"Minigames"));
   verify(Categories.matches({category:"Utilities",tags:["realm","heaven","hell"]},"Realms"));
   verify(Categories.matches({category:"Launcher",tags:["search"]},"Launcher"));
 }
 function test_legacy_and_localized_names() {
   compare(Categories.canonical(" Worlds "),"Realms");
   compare(Categories.canonical("СЮЖЕТ"),"Story");
   compare(Categories.canonical("story-packs"),"Story");
   verify(Categories.matches({category:"Narrative"},"Story"));
   verify(Categories.matches({category:"Utilities",tags:["widgets"]},"Widgets"));
 }
 function test_custom_categories_not_lost() {
   const choices=Categories.choices([{category:"Photography"},{category:"photography"},{category:"Narrative"}]);
   compare(choices.filter(c=>c.id.toLowerCase()==="photography").length,1);
   compare(choices.filter(c=>c.id==="Narrative").length,0);
   verify(Categories.matches({category:"Photography"},"Photography"));
 }
 function test_groups_and_search() {
   const groups=Categories.groups([{category:"Photography"}]);compare(groups.length,3);
   verify(groups[0].items.some(c=>c.id==="Dialogue"));
   verify(groups[1].items.some(c=>c.id==="Cursors"));
   verify(groups[2].items.some(c=>c.id==="Photography"));
   const terms=Categories.searchTerms({category:"Quests"}).toLowerCase();
   verify(terms.includes("сюжет"));verify(terms.includes("квесты"));
 }
}''')
            r=subprocess.run([RUNNER,'-input',str(root)],env={**os.environ,'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software'},capture_output=True,text=True,timeout=30)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)

if __name__=='__main__':unittest.main()

import importlib.util, io, json, tempfile, unittest, zipfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('localized_store',Path(__file__).resolve().parents[1]/'scripts/community-store.py');store=importlib.util.module_from_spec(spec);spec.loader.exec_module(store)
class LocalizedManifestTests(unittest.TestCase):
 def test_localized_labels_and_invalid_labels(self):
  for label,valid in [({'ru':'VPN','en':'VPN'},True),('VPN',True),({},False),({'ru':''},False),({'ru':None},False)]:
   archive=io.BytesIO()
   with zipfile.ZipFile(archive,'w') as z:z.writestr('manifest.json',json.dumps({'id':'vpn','version':'1.1.2','name':label}))
   with tempfile.TemporaryDirectory() as tmp:
    if valid:self.assertEqual(store.unpack_plugin(archive.getvalue(),Path(tmp)/'extract')[1]['name'],label)
    else:
     with self.assertRaises(ValueError):store.unpack_plugin(archive.getvalue(),Path(tmp)/'extract')

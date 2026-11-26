import csv, json, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "w02_b3" / "build_labeled_sample.py"
FIX = ROOT / "tests" / "w02_b3" / "fixtures" / "raw"
class SampleTests(unittest.TestCase):
 def build(self, seed=42):
  out=Path(tempfile.mkdtemp()); subprocess.run([sys.executable,str(SCRIPT),'--data-dir',str(FIX),'--output-dir',str(out),'--seed',str(seed),'--per-stratum','1'],check=True); return out
 def test_deterministic_seed(self):
  a,b=self.build(),self.build(); self.assertEqual((a/'labeled_sample.csv').read_bytes(),(b/'labeled_sample.csv').read_bytes()); shutil.rmtree(a); shutil.rmtree(b)
 def test_contract_and_hex_and_mapping(self):
  out=self.build()
  with (out/'labeled_sample.csv').open(newline='') as f: rows=list(csv.DictReader(f))
  self.assertEqual(len(rows[0]),18); self.assertIn('00',[r['data_0'] for r in rows]); self.assertEqual({r['attack_type'] for r in rows if r['label']=='1'},{'dos','fuzzy','gear','rpm'}); shutil.rmtree(out)
 def test_provenance_shared_tail_and_manifest(self):
  out=self.build()
  with (out/'labeled_sample.csv').open(newline='') as f: rows=list(csv.DictReader(f))
  self.assertTrue(any(r['label_provenance']=='inferred_from_source' and not r['flag_raw'] for r in rows)); self.assertFalse(any(r['timestamp']=='1478200727.419470' for r in rows)); m=json.loads((out/'manifest.json').read_text()); self.assertEqual(m['seed'],42); self.assertEqual(m['rows'],6); shutil.rmtree(out)
if __name__=='__main__': unittest.main()

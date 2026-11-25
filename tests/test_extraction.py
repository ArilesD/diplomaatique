import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ExtractionTest(unittest.TestCase):
    def test_deux_arretes_gardent_leurs_articles_respectifs(self):
        with TemporaryDirectory(dir=ROOT) as directory:
            subprocess.run(
                [
                    sys.executable, 'diplomaatique.py', 'exemple/recueil-original.txt',
                    'exemple/recueil-original.json', '--output', directory,
                ],
                cwd=ROOT,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            results = sorted(Path(directory).rglob('*.json'))
            docs = [json.loads(path.read_text(encoding='utf-8')) for path in results]

        self.assertEqual([doc['numero_arrete'] for doc in docs], [
            '78-2026-02-17-00001', '78-2026-02-17-00002',
        ])
        self.assertEqual([len(doc['articles']) for doc in docs], [5, 4])
        self.assertNotEqual(docs[0]['articles'][0]['contenu'], docs[1]['articles'][0]['contenu'])
        original = (ROOT / 'exemple/recueil-original.txt').read_text(encoding='utf-8')
        for doc in docs:
            self.assertIn(doc['numero_arrete'], original)


if __name__ == '__main__':
    unittest.main()

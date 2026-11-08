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
                    sys.executable, 'diplomaatique.py', 'exemple/raa-fictif.txt',
                    'exemple/raa-fictif.json', '--output', directory,
                ],
                cwd=ROOT,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            results = sorted(Path(directory).rglob('*.json'))
            docs = [json.loads(path.read_text(encoding='utf-8')) for path in results]

        self.assertEqual([doc['numero_arrete'] for doc in docs], [
            '93-2026-01-15-90001', '93-2026-01-15-90002',
        ])
        self.assertEqual([len(doc['articles']) for doc in docs], [2, 1])
        self.assertIn('jardin des Érables', docs[0]['articles'][0]['contenu'])
        self.assertIn('bibliothèque des Tilleuls', docs[1]['articles'][0]['contenu'])


if __name__ == '__main__':
    unittest.main()

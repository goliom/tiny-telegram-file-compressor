"""Check that every supported language can format every application message."""
import sys
import unittest
from pathlib import Path
from string import Formatter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compression_i18n import LANGUAGES, MESSAGES, text


class TranslationTest(unittest.TestCase):
    def test_all_languages_preserve_message_fields(self):
        self.assertEqual(set(LANGUAGES), {'fr', 'en', 'es', 'it', 'de', 'nl', 'ru', 'hi', 'zh'})
        formatter = Formatter()
        for key, translations in MESSAGES.items():
            self.assertEqual(len(translations), len(LANGUAGES), key)
            fields = {name for _, name, _, _ in formatter.parse(translations[0]) if name is not None}
            values = {name: f'[{name}]' for name in fields}
            for language, translation in zip(LANGUAGES, translations):
                with self.subTest(key=key, language=language):
                    self.assertTrue(translation.strip())
                    self.assertEqual({name for _, name, _, _ in formatter.parse(translation) if name is not None}, fields)
                    rendered = text(key, language, **values)
                    for value in values.values():
                        self.assertIn(value, rendered)


if __name__ == '__main__':
    unittest.main()

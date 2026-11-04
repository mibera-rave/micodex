"""Regression vectors from maintainer comment 6622775368; no public calls."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mibera as m
from wallet_bridge import Guard

class CleanerContractTests(unittest.TestCase):
    def test_preserve_internal_unicode_spaces(self):
        for raw, expected in [('a\u00a0b','a\u00a0b'),('a\u00a0\u2003b','a\u00a0\u2003b'),
                              ('\u3000a\u00a0b\u3000','a\u00a0b'),(' hello\n camp ','hello camp')]:
            with self.subTest(raw=repr(raw)):
                self.assertEqual(m.chat_text(raw),expected)

    def test_server_changed_content_rejected_before_say(self):
        # Conservative option explicitly accepted by the maintainer. The raw
        # approved text is never rewritten to bypass these input rejections.
        for raw in ['\ufeffa\u2028b\u3000','a\u200bb','hi \u200d there',
                    'a\vb','a\fb','cafe\u0301','e\u0301\u0302\u0303\u0304',
                    '\u200b','x\u0302\u0303\u0304','\x0304red','\x04ABCDEFred']:
            with self.subTest(raw=repr(raw)):
                self.assertRaises(Guard,m.chat_text,raw)

    def test_all_maintainer_removal_ranges_and_format_controls(self):
        ranges=[(0,31),(127,159),(173,173),(847,847),(1564,1564),
                (4447,4448),(6068,6069),(6155,6159),(8203,8207),(8232,8238),
                (8288,8303),(12644,12644),(65024,65038),(65279,65279),
                (65440,65440),(65520,65531)]
        for lo,hi in ranges:
            for cp in range(lo,hi+1):
                if cp in (9,10,13):continue
                with self.subTest(codepoint=hex(cp)):
                    self.assertRaises(Guard,m.chat_text,'a'+chr(cp)+'b')

    def test_visible_content_and_two_marks_preserved(self):
        for text in ['caf\u00e9','x\u0302\u0303','\u2764\ufe0f','a\u202fb','a\u3000b']:
            with self.subTest(text=repr(text)):self.assertEqual(m.chat_text(text),text)

if __name__=='__main__':unittest.main()

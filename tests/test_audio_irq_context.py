import unittest
from tools.audit_audio_irq_context import analyze,PRESERVED,FIELDS
from tools.build_audio_irq_context_core import transform


def rows():
    return [['I','10','80','100','1000','c7f2c9','43981','120','188','511','305','4660','135','9','1','0'],
            ['R','10','100','100','28000','c7f2c9','43981','120','188','511','305','4660','135','9','0','0']]


class IrqContextTests(unittest.TestCase):
    def test_intact(self):self.assertTrue(analyze(rows())['passed'])

    def test_all_actual_cpu_fields(self):
        for field in PRESERVED:
            r=rows();at=FIELDS.index(field)+1
            value=int(r[1][at],16 if field=='pc' else 10)^1
            r[1][at]=f'{value:06x}' if field=='pc' else str(value)
            self.assertIn(field,analyze(r)['pairs'][0]['failures'])

    def test_boundaries_and_duplicate_events(self):
        for r in ([],rows()[:1],rows()[1:],[rows()[0],*rows()],rows()[::-1]):
            with self.assertRaises(ValueError):analyze(r)

    def test_transform_fails_closed(self):
        with self.assertRaises(ValueError):transform('unknown core')

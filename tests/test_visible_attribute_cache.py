import inspect
from pathlib import Path
import unittest
from tools.build_native import build
from tools.check_visible_attribute_cache import expected


class VisibleAttributeCacheTests(unittest.TestCase):
    def test_default_and_prerequisite(self):
        self.assertFalse(inspect.signature(build).parameters['experimental_visible_attribute_cache'].default)
        with self.assertRaisesRegex(ValueError,'Visible attribute cache'):
            build(Path('unused'),[],Path('unused'),experimental_visible_attribute_cache=True)

    def test_queued_alias_is_immutable(self):
        flags=bytearray(128);flags[0]=1;flags[64]=3
        staged,result,cursor,left,_,rows=expected(bytes(4096),flags,0,0,0,1)
        self.assertEqual(staged[64*64:65*64],bytes((i^(i>>8))&255 for i in range(64*64,65*64)))
        self.assertEqual(result[0],2);self.assertEqual(result[64],3)
        self.assertEqual((cursor,left,rows),(1,0,[0]))

    def test_nonvisible_rows_do_not_spend_budget(self):
        flags=bytearray(128)
        for i in (30,31,32):flags[i]=1
        _,result,cursor,left,_,rows=expected(bytes(4096),flags,30,0,0,1)
        self.assertEqual((cursor,left,rows),(33,0,[32]))
        self.assertEqual(result[30:33],bytes((0,0,2)))

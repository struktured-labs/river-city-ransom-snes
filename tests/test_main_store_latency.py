import unittest
from tools.audit_main_store_latency import parse


class MainStoreTests(unittest.TestCase):
    points={0:0x3000,1:0xf282,2:0x3102,3:0xf2da}

    def fixture(self):
        image=bytearray(0x20000);rows=[]
        for event,pc in self.points.items():
            opcode=(0xa9,0x20,0x85,0xee)[event];image[0x10000+pc]=opcode
            image[0x13103]=0xf6
            rows.append(list(map(str,[event,1+event//2,128,100,event+1]))+
                [f'{0xc10000+pc:06x}',f'{opcode:02x}']+
                list(map(str,[44,0,0,0x1fc if event!=2 else 0x1fa,42,1,2,192,3,0,0])))
        return rows,bytes(image)

    def test_actual_accumulator_and_high_bit_form_committed_camera(self):
        rows,image=self.fixture();loops,edges=parse(rows,self.points,2,image)
        self.assertEqual(loops[0]['commit']['camera'],300)
        self.assertEqual(loops[0]['commit']['old_camera_low'],42)
        self.assertFalse(edges)

    def test_missing_input_duplicate_store_or_start_fail(self):
        rows,image=self.fixture()
        for bad in (rows[:1]+rows[2:],rows[:3]+rows[2:],rows[:1]+rows):
            with self.assertRaises(ValueError):parse(bad,self.points,2,image)

    def test_wrong_stack_pc_clock_frame_and_opcode_fail(self):
        for index,column,value in ((2,10,'508'),(2,5,'c03102'),(2,4,'1'),
                (2,1,'3'),(2,6,'ea'),(2,12,'256')):
            rows,image=self.fixture();rows[index][column]=value
            with self.assertRaises(ValueError):parse(rows,self.points,2,image)

    def test_different_store_operand_rejected(self):
        rows,image=self.fixture();bad=bytearray(image);bad[0x13103]=0xf5
        with self.assertRaises(ValueError):parse(rows,self.points,2,bytes(bad))

    def test_camera_free_main_is_retained_not_fabricated(self):
        rows,image=self.fixture();loops,_=parse(rows[:2]+rows[3:],self.points,2,image)
        self.assertIsNone(loops[0]['commit'])

    def test_extra_transition_store_is_retained_separately(self):
        rows,image=self.fixture();nested=rows[2].copy()
        nested[4]='4';nested[10]='504';nested[16]='1';rows[3][4]='5'
        loops,edges=parse(rows[:3]+[nested]+rows[3:],self.points,2,image)
        self.assertEqual(len(loops),1)
        self.assertEqual(edges[0]['kind'],'nested transition camera')
        self.assertEqual(edges[0]['event']['s'],504)

    def test_outside_camera_and_censored_tail_retained(self):
        rows,image=self.fixture();leading=rows[2].copy();leading[4]='0';leading[1]='1'
        trailing=rows[0].copy();trailing[4]='5';trailing[1]='2'
        loops,edges=parse([leading]+rows+[trailing],self.points,2,image)
        self.assertEqual(len(loops),1)
        self.assertEqual([e['kind'] for e in edges],['camera outside main','trailing main'])

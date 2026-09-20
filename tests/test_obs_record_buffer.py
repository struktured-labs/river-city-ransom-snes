import unittest
from tools.audit_obs_record_buffer import analyze


TRACE = '''B,1
I,2,7,10,800,1000
P,3,7,10,4096,1000,800
p,4,7,10,7296,1000
D,5,8,10,7296,1000,1000,21334333
d,6,8,10,3200,21334333
Z,7
'''


class BufferTraceTests(unittest.TestCase):
    def test_conservation(self):
        r = analyze(TRACE)
        self.assertEqual(r['producer_frame_delta_histogram'], {800: 1})
        self.assertEqual(r['consumer_frame_delta_histogram'], {-1024: 1})
        self.assertFalse(r['between_transaction_changes'])

    def test_32_extra_frames_detected(self):
        r = analyze(TRACE.replace('7296', '7424'))
        self.assertEqual(r['non_append_producers'][0]['delta_frames'], 832)
        self.assertEqual(r['non_1024_consumers'][0]['delta_frames'], -1056)

    def test_unobserved_buffer_change_retained(self):
        r = analyze(TRACE.replace('D,5,8,10,7296', 'D,5,8,10,7168'))
        self.assertEqual(r['between_transaction_changes'][0]['byte_change'], -128)

    def test_lost_end_rejected(self):
        with self.assertRaises(ValueError):
            analyze(TRACE.replace('p,4,7,10,7296,1000\n', ''))

    def test_final_censor_retained(self):
        r = analyze(TRACE.replace('d,6,8,10,3200,21334333\n', ''))
        self.assertEqual(len(r['final_censored']), 1)

    def test_cross_cpu_delivery_sorted(self):
        lines = TRACE.splitlines()
        lines[3], lines[4] = lines[4], lines[3]
        self.assertEqual(analyze('\n'.join(lines))['consumer_count'], 1)

    def test_unaligned_size_rejected(self):
        with self.assertRaises(ValueError):
            analyze(TRACE.replace('7296', '7297'))

    def test_missing_boundary_rejected(self):
        with self.assertRaises(ValueError):
            analyze(TRACE.replace('Z,7\n', ''))


if __name__ == '__main__':
    unittest.main()

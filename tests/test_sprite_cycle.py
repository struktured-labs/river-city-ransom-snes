import copy
import unittest
from tools.run_sprite_cycle import gates


class SpriteCycleTests(unittest.TestCase):
    def sample(self):
        data = dict(structural_passed=True, generations=[dict(source_frame=3, source_sha256='abc',
            left_censored=False, source_to_first_render_frames=1)])
        rows = [dict(probe_052b=1, native=dict(logical_camera_x=15),
            input_requested=[1], input_delivered=[1], fault=None)]
        return data, rows

    def test_next_frame_requires_same_source_and_no_omissions(self):
        data, rows = self.sample()
        self.assertTrue(all(gates(data, data, rows, rows).values()))
        for delay in (None, 3):
            other = copy.deepcopy(data); other['generations'][0]['source_to_first_render_frames'] = delay
            self.assertFalse(gates(data, other, rows, rows)['every_known_generation_displayed_next_frame'])
        other = copy.deepcopy(data); other['generations'][0]['source_sha256'] = 'different'
        self.assertFalse(gates(data, other, rows, rows)['same_source_generations'])

    def test_cannot_improve_sprites_by_slowing_game_or_changing_inputs(self):
        data, rows = self.sample()
        for field, value, gate in (
            ('probe_052b', 0, 'original_game_counter_unchanged'),
            ('native', dict(logical_camera_x=14), 'logical_camera_unchanged'),
            ('input_delivered', [], 'input_delivery_unchanged'),
            ('fault', 'overrun', 'no_adapter_faults')):
            changed = copy.deepcopy(rows); changed[0][field] = value
            self.assertFalse(gates(data, data, rows, changed)[gate])

    def test_empty_known_population_does_not_pass(self):
        data, rows = self.sample(); data['generations'][0]['left_censored'] = True
        self.assertFalse(gates(data, data, rows, rows)['every_known_generation_displayed_next_frame'])

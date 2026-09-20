import unittest
from tools.benchmark_capture import validate_render_options


class RenderOptionsTests(unittest.TestCase):
    def test_known_bounds_and_unrelated_options(self):
        validate_render_options({'RCR_RENDER_SCROLL_TRACE':'trace.csv','RCR_RENDER_FIRST':'1',
                                 'RCR_RENDER_LAST':'15000','RCR_PROFILE_FIRST':'1'})
        validate_render_options({})

    def test_wrong_prefix_fails_before_capture(self):
        for key in ('RCR_RENDER_SCROLL_FIRST','RCR_RENDER_SCROLL_LAST'):
            with self.assertRaisesRegex(ValueError,'Unknown renderer'):
                validate_render_options({'RCR_RENDER_SCROLL_TRACE':'trace.csv',key:'1'})

    def test_inverted_and_zero_bounds(self):
        for first,last in ((0,100),(100,1)):
            with self.assertRaisesRegex(ValueError,'bounds'):
                validate_render_options({'RCR_RENDER_SCROLL_TRACE':'trace.csv',
                                         'RCR_RENDER_FIRST':str(first),'RCR_RENDER_LAST':str(last)})

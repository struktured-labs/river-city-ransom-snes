import contextlib
import io
import json
import unittest
from unittest.mock import Mock, patch
from tools.sync_reported_issues import sync


class ReportedIssueTests(unittest.TestCase):
    def spec(self):
        return Mock(read_text=Mock(return_value=json.dumps([dict(key='x', title='A regression', body='User evidence')])) )

    def test_default_dry_run_never_creates(self):
        with patch('tools.sync_reported_issues.gh', return_value='[]') as gh, contextlib.redirect_stdout(io.StringIO()):
            result = sync(self.spec())
        self.assertEqual(result[0]['action'], 'would_create')
        self.assertEqual(gh.call_count, 1)

    def test_existing_closed_issue_is_not_duplicated(self):
        record = dict(number=7, title='A regression', state='CLOSED', url='https://example.invalid/issues/7')
        with patch('tools.sync_reported_issues.gh', return_value=json.dumps([record])) as gh, contextlib.redirect_stdout(io.StringIO()):
            result = sync(self.spec(), apply=True)
        self.assertEqual(result[0]['number'], 7)
        self.assertEqual(result[0]['action'], 'existing')
        self.assertEqual(gh.call_count, 1)

    def test_create_is_followed_by_identity_verification(self):
        record = dict(number=8, title='A regression', state='OPEN', url='https://example.invalid/issues/8')
        with patch('tools.sync_reported_issues.gh', side_effect=['[]', record['url'], json.dumps(record)]) as gh, contextlib.redirect_stdout(io.StringIO()):
            result = sync(self.spec(), apply=True)
        self.assertEqual(result[0]['action'], 'created')
        self.assertEqual(gh.call_args_list[1].args[:2], ('issue', 'create'))
        self.assertEqual(gh.call_args_list[2].args[:2], ('issue', 'view'))

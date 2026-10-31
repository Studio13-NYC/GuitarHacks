import json
import unittest
from unittest.mock import patch
from test_flashcards import QApplication
from painter_coach import PracticeCoach,request_body,parse_response


class CoachTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_request_contains_only_supplied_practice_data_and_no_tools(self):
        value={'mode':'guess','rows':[{'id':'major','failed':2}],'notes':'Less major today'}
        body=request_body(json.dumps(value),'gpt-6.1-terra')
        self.assertEqual(json.loads(body['input']),value)
        self.assertFalse(body['store']);self.assertNotIn('tools',body)
        self.assertTrue(body['text']['format']['strict'])

    def test_invalid_unknown_duplicate_or_unbounded_model_advice_is_rejected(self):
        def response(advice):
            return json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(advice)}]}]})
        valid={'summary':'Major needs more practice.','priorities':[{'id':'major','priority':1,'reason':'Two failures.'}]}
        self.assertEqual(parse_response(response(valid),{'major'}),valid)
        for priorities in [[{'id':'minor','priority':1,'reason':'unknown'}],[{'id':'major','priority':99,'reason':'bad'}],valid['priorities']*2]:
            with self.assertRaises(ValueError):parse_response(response({'summary':'test','priorities':priorities}),{'major'})
        with self.assertRaises(ValueError):parse_response('{"status":"incomplete"}',{'major'})

    def test_missing_credentials_reports_problem_without_network_request(self):
        coach=PracticeCoach();received=[];coach.ready.connect(lambda *args:received.append(args))
        with patch('painter_coach.credentials',return_value=('','gpt-6.1-terra')),patch.object(coach.network,'post') as post:
            coach.review('request-1','{}');post.assert_not_called()
        self.assertEqual(received[0][0],'request-1')
        self.assertIn('not connected',json.loads(received[0][1])['error'])

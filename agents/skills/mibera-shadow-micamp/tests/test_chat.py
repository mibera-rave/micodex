"""Chat regressions using scripted frames; no public connection or wallet."""
import json, sys, unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mibera as m
from wallet_bridge import Guard

class ChatTests(unittest.TestCase):
    def test_normalization(self):
        for raw, expected in [(' hello','hello'),('hello ','hello'),
                ('hello\nworld','hello world'),('a   b','a b'),
                ('\r\n a\t b \n','a b'),('a\u00a0\u2003b','a\u00a0\u2003b')]:
            with self.subTest(raw=repr(raw)):self.assertEqual(m.chat_text(raw),expected)
    def test_boundary(self):
        self.assertEqual(m.chat_text('x'*280),'x'*280)
        self.assertEqual(m.chat_text('😀'*140),'😀'*140)
        for text in ['x'*281,'😀'*141,' '*281,'', ' \n\t',None,3,
                     'a\x00b','a\x1cb','a\x85b','a\x7fb','a\ud800b']:
            with self.subTest(text=repr(text)):self.assertRaises(Guard,m.chat_text,text)
    def run_chat(self, frames, text='  hello\n  camp  '):
        vault=Mock();vault.get.return_value={}
        http=Mock();http.call.return_value={'fire':'camp'}
        journal=Mock();sock=Mock();sock.recv.side_effect=[json.dumps(f) for f in [
            {'t':'welcome','you':'own','people':[{'id':'own','me':7}]},*frames]]
        with patch.object(m,'runtime_check'),patch.object(m,'session_validate',return_value={'ticket':'local','expires':10**20}):
            result=m.participate(vault,journal,'local',7,'Fixture','chat-local-001',
                                 {'kind':'chat','text':text,'approved':True},http,lambda *a,**k:sock)
        return result,journal,sock
    def test_exact_normalized_ack(self):
        result,journal,sock=self.run_chat([
            {'t':'said','id':'other','text':'hello camp'},
            {'t':'said','id':'own','text':'different'},
            {'t':'pong','now':0},
            {'t':'said','id':'own','text':'hello camp'}])
        self.assertTrue(result['action']['acknowledged'])
        self.assertEqual(json.loads(sock.send.call_args_list[1].args[0])['text'],'  hello\n  camp  ')
        self.assertEqual(journal.update.call_args.args[1],'VERIFIED')
    def test_wrong_speaker_text_and_raw_echo_do_not_verify(self):
        for frame in [{'t':'said','id':'other','text':'hello camp'},
                      {'t':'said','id':'own','text':'different'},
                      {'t':'said','id':'own','text':'  hello\n  camp  '}]:
            with self.subTest(frame=frame):
                with self.assertRaises(StopIteration):self.run_chat([frame])
    def test_boundary_is_sent_and_acknowledged(self):
        self.assertTrue(self.run_chat([{'t':'said','id':'own','text':'x'*280}],text='x'*280)[0]['action']['acknowledged'])
    def test_unicode_space_exact_echo_and_raw_payload(self):
        raw=' \u3000a\u00a0\u2003b \n'
        result,journal,sock=self.run_chat([{'t':'said','id':'own','text':'a\u00a0\u2003b'}],raw)
        self.assertTrue(result['action']['acknowledged'])
        self.assertEqual(json.loads(sock.send.call_args_list[1].args[0])['text'],raw)
    def test_rejected_content_never_reserved_or_sent(self):
        vault=Mock();vault.get.return_value={};journal=Mock();http=Mock()
        http.call.return_value={'fire':'camp'};sock=Mock()
        sock.recv.return_value=json.dumps({'t':'welcome','you':'own','people':[{'id':'own','me':7}]})
        with patch.object(m,'runtime_check'),patch.object(m,'session_validate',return_value={'ticket':'local','expires':10**20}):
            with self.assertRaises(Guard):
                m.participate(vault,journal,'local',7,'Fixture','reject-local-001',
                    {'kind':'chat','text':'a\u200bb','approved':True},http,lambda *a,**k:sock)
        journal.reserve.assert_not_called()
        self.assertEqual([json.loads(c.args[0])['t'] for c in sock.send.call_args_list],['join','part'])
if __name__=='__main__':unittest.main()

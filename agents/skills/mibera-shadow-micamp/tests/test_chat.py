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
                ('\r\n a\t b \n','a b'),('a\u00a0\u2003b','a b'),
                ('\ufeffa\u2028b\u3000','a b'),('a\u200bb','a\u200bb')]:
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
if __name__=='__main__':unittest.main()

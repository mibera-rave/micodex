"""Real loopback wire tests for Micamp's documented same-origin gate."""
import json, sys, threading, unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mibera as m
from unittest.mock import Mock

class Origin(unittest.TestCase):
    def test_micamp_get_and_post_send_exact_origin(self):
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def handle_request(self):
                self.rfile.read(int(self.headers.get('Content-Length','0')))
                seen.append((self.command,self.path,self.headers.get('Origin')))
                ok=self.headers.get('Origin')==origin
                body=json.dumps({'ok':True} if ok else {'error':'origin'}).encode()
                self.send_response(200 if ok else 403)
                self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            do_GET=handle_request
            do_POST=handle_request
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        origin='http://127.0.0.1:'+str(server.server_port)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        client=m.HTTP()
        try:
            with patch.object(m,'M',origin):
                for route,data in [('/door/nonce',None),('/door/sign',{'fixture':'no signature'}),('/fires',None)]:
                    with self.subTest(route=route):
                        self.assertEqual(client.call(origin,route,data),{'ok':True})
            self.assertEqual(seen,[('GET','/door/nonce',origin),('POST','/door/sign',origin),('GET','/fires',origin)])
        finally:
            client.s.close();server.shutdown();server.server_close();thread.join()

    def test_vending_does_not_receive_micamp_origin(self):
        client=m.HTTP()
        try:
            response=Mock(status_code=200,content=b'{}');response.json.return_value={}
            with patch.object(client.s,'request',return_value=response) as request:
                client.call(m.V,'/api/registry')
            self.assertNotIn('Origin',request.call_args.kwargs['headers'])
            self.assertFalse(request.call_args.kwargs['allow_redirects'])
        finally:client.s.close()

    def test_unknown_origin_stops_before_request(self):
        client=m.HTTP()
        try:
            with patch.object(client.s,'request') as request:
                with self.assertRaises(m.Guard):client.call('https://example.invalid','/fires')
            request.assert_not_called()
        finally:client.s.close()

    def test_login_capture_and_no_redirect_are_preserved(self):
        client=m.HTTP();captured=[]
        try:
            response=Mock(status_code=200)
            response.iter_content.return_value=[b'{"ok":true}']
            response.raw.headers={}
            with patch.object(client.s,'request',return_value=response) as request:
                self.assertEqual(client.call(m.M,'/door/sign',{'fixture':'local'},capture=captured.append),{'ok':True})
            self.assertEqual(request.call_args.kwargs['headers']['Origin'],m.M)
            self.assertFalse(request.call_args.kwargs['allow_redirects'])
            self.assertTrue(request.call_args.kwargs['stream'])
            self.assertEqual(len(captured),1)
            self.assertEqual(captured[0]['status'],200)
            response.close.assert_called_once()
        finally:client.s.close()

if __name__=='__main__':unittest.main()

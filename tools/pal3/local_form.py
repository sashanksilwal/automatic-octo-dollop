"""One-use local PAL3.0 credential entry; no request/credential logging."""
import hmac
import json
import secrets
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

ROOT=Path(__file__).resolve().parents[2]
ADB=ROOT/'.tools/android-sdk/platform-tools/adb'
PORT=8765
ORIGIN=f'http://127.0.0.1:{PORT}'
NONCE=secrets.token_urlsafe(32)
USED=False
PAGE='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connect glasses to PAL3.0</title><style>body{font:16px system-ui;max-width:500px;margin:60px auto;padding:24px}label{display:block;margin:20px 0}input,button{box-sizing:border-box;font:inherit;width:100%;padding:12px;margin-top:8px}small{line-height:1.6}#status{line-height:1.6;white-space:pre-wrap}</style>
<h1>Connect glasses to PAL3.0</h1><p>Enter your Purdue career-account credentials directly here.</p>
<form id="form" autocomplete="off"><input type="hidden" name="nonce" value="NONCE">
<label>Purdue username<input name="username" required autocomplete="off" autocapitalize="none" spellcheck="false"></label>
<label>Purdue password<input name="password" type="password" required autocomplete="off"></label>
<button id="submit">Connect glasses</button></form><p id="status" role="status"></p>
<small>This form runs only on this laptop. The helper passes your credentials to the connected glasses and does not save or log them. The glasses save the Wi-Fi profile to reconnect. Certificate verification stays enabled.</small>
<script>document.getElementById('form').onsubmit=async e=>{e.preventDefault();const f=e.target,b=document.getElementById('submit'),s=document.getElementById('status');b.disabled=true;s.textContent='Connecting… this may take up to 30 seconds.';const body=new URLSearchParams(new FormData(f));f.elements.password.value='';try{const r=await fetch('/connect',{method:'POST',body});const a=await r.json();s.textContent=a.status;if(!r.ok)throw Error(a.status);f.remove();}catch(e){s.textContent=e.message+' If needed, ask to reopen the local form.'}finally{body.delete('password');body.delete('username');b.disabled=false}};</script></html>'''.replace('NONCE',NONCE)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def reply(self,code,body,kind='application/json'):
        if not isinstance(body,bytes): body=json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'")
        self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.headers.get('Host')!=f'127.0.0.1:{PORT}': self.reply(403,{'status':'Invalid host'}); return
        if self.path!='/': self.reply(404,{'status':'Not found'}); return
        self.reply(200,PAGE.encode(),'text/html; charset=utf-8')
    def do_POST(self):
        global USED
        data={}
        try:
            if (USED or self.path!='/connect' or self.headers.get('Host')!=f'127.0.0.1:{PORT}' or self.headers.get('Origin')!=ORIGIN):
                self.reply(403,{'status':'This form is unavailable. Ask to reopen it.'}); return
            n=int(self.headers.get('Content-Length','0'))
            if not 1<=n<=8192: self.reply(400,{'status':'Invalid request'}); return
            data=parse_qs(self.rfile.read(n).decode(),strict_parsing=True)
            if not hmac.compare_digest(data.get('nonce',[''])[0],NONCE):
                self.reply(403,{'status':'Invalid form token'}); return
            username=data.get('username',[''])[0].strip()
            password=data.get('password',[''])[0]
            if not username or not password or any(c in username+password for c in '\r\n\x00'):
                self.reply(400,{'status':'Enter a username and password without line breaks.'}); return
            USED=True
            result=subprocess.run([str(ADB),'-s','YM00DEC8P06371','shell','CLASSPATH=/data/local/tmp/cs536-pal-setup.dex app_process / PalConnect'],
                                  input=(username+'\n'+password+'\n').encode(),capture_output=True,timeout=40)
            username=password=None
            output=result.stdout.decode(errors='replace')
            # Only known, credential-free helper status lines may reach the page.
            lines=[s for s in output.splitlines() if s.startswith(('CONNECTED:','NOT_CONNECTED:','SETUP_REJECTED:','CONNECT_REJECTED:','SETUP_ERROR:'))]
            status=lines[-1] if lines else 'Setup could not complete. Ask to check the USB connection.'
            print(status,flush=True)
            self.reply(200,{'status':status})
        except Exception:
            self.reply(500,{'status':'Setup could not complete. Ask to check the USB connection.'})
        finally:
            data.clear()
            if USED:
                subprocess.run([str(ADB),'-s','YM00DEC8P06371','shell','rm','-f','/data/local/tmp/cs536-pal-setup.dex'],capture_output=True,timeout=5)
                threading.Thread(target=self.server.shutdown,daemon=True).start()

server=HTTPServer(('127.0.0.1',PORT),Handler)
expiry=threading.Timer(900,server.shutdown)
expiry.daemon=True
expiry.start()
print(f'Open {ORIGIN}/ and enter Purdue credentials there. They are not logged.',flush=True)
try: server.serve_forever(poll_interval=.2)
finally:
    expiry.cancel()
    server.server_close()
    subprocess.run([str(ADB),'-s','YM00DEC8P06371','shell','rm','-f','/data/local/tmp/cs536-pal-setup.dex'],capture_output=True,timeout=5)

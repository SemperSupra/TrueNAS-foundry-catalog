"""Public product TLS/browser smoke tests with a deliberately stubbed Foundry core.

These tests DO NOT replace the actual-core integration test and OCI runtime gates.
"""
from __future__ import annotations
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from http.server import BaseHTTPRequestHandler

ROOT = Path(__file__).resolve().parents[1]
class FakeIdentityError(ValueError): pass
fake_fed = types.ModuleType("foundry_catalog_federation")
fake_fed.CatalogIdentityError = FakeIdentityError
fake_fed.load_catalogs = lambda paths: [
    dict(package_id="github.com/foundry/community/probe", provider_id="github.com/foundry",
         source_revision="a"*40, version="1.0", source_tree_sha256="sha256:"+"b"*64,
         admission="DISCOVERED_ONLY")
]
class FakeReadHandler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def respond(self,status,obj):
        data=json.dumps(obj).encode()
        self.send_response(status);self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if self.headers.get("Authorization") != "Bearer "+self.server.bearer:
            return self.respond(401,{"error":"unauthorized"})
        if self.path == "/v0/catalog/apps":
            return self.respond(200,{"operation":"list","count":len(self.server.rows),"apps":list(self.server.rows)})
        return self.respond(404,{"error":"not found"})
    def reject(self): self.respond(405,{"error":"read-only endpoint"})
    do_POST=reject;do_PUT=reject;do_PATCH=reject;do_DELETE=reject;do_OPTIONS=reject
    def do_HEAD(self):
        self.send_response(405);self.send_header("Content-Length","0");self.end_headers()
fake_http = types.ModuleType("foundry_catalog_read_http")
fake_http.ReadHandler=FakeReadHandler
fake_http.load_bearer=lambda p: p.read_text().strip()
sys.modules["foundry_catalog_federation"]=fake_fed
sys.modules["foundry_catalog_read_http"]=fake_http
spec=importlib.util.spec_from_file_location("foundry_product",ROOT/"src/server.py")
product=importlib.util.module_from_spec(spec)
spec.loader.exec_module(product)

class ProductSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(); cls.folder=Path(cls.tmp.name)
        cls.token="test_token_"+"x"*48
        cls.key=cls.folder/"tls.key";cls.cert=cls.folder/"tls.crt"
        subprocess.run(["openssl","req","-x509","-nodes","-newkey","rsa:2048","-days","1",
                        "-keyout",str(cls.key),"-out",str(cls.cert),"-subj","/CN=localhost"],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        cls.key.chmod(0o600)
        cls.tls=product.configure_tls(cls.cert,cls.key)
        cls.srv=product.ProductServer("127.0.0.1",0,fake_fed.load_catalogs([]),cls.token,cls.tls)
        cls.worker=threading.Thread(target=cls.srv.serve_forever,daemon=True);cls.worker.start()
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown();cls.worker.join(timeout=5);cls.srv.server_close();cls.tmp.cleanup()
    def request(self,path,token=False,method="GET"):
        conn=http.client.HTTPSConnection("127.0.0.1",self.srv.server_port,
                                         context=ssl._create_unverified_context(),timeout=4)
        conn.request(method,path,headers={"Authorization":"Bearer "+self.token} if token else {})
        reply=conn.getresponse();result=(reply.status,dict(reply.getheaders()),reply.read())
        conn.close();return result

    def test_real_tls_handshake_readiness(self):
        code,_,data=self.request("/healthz")
        self.assertEqual(code,200);self.assertEqual(json.loads(data)["mode"],"READ_ONLY")
    def test_browser_assets_and_security_headers(self):
        for url in ("/","/app.js","/app.css"):
            with self.subTest(path=url):
                code,headers,data=self.request(url)
                self.assertEqual(code,200)
                self.assertIn("default-src 'none'",headers["Content-Security-Policy"])
                self.assertEqual(headers["X-Frame-Options"],"DENY")
                self.assertNotIn(self.token.encode(),data)
    def test_bearer_required_for_listing(self):
        self.assertEqual(self.request("/v0/catalog/apps")[0],401)
        status,_,body=self.request("/v0/catalog/apps",token=True)
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)["apps"][0]["admission"],"DISCOVERED_ONLY")
    def test_write_verbs_absent(self):
        for method in ("POST","PUT","PATCH","DELETE","OPTIONS"):
            with self.subTest(method=method):
                self.assertEqual(self.request("/v0/catalog/apps",token=True,method=method)[0],405)
    def test_head_cannot_read(self):
        self.assertEqual(self.request("/v0/catalog/apps",token=True,method="HEAD")[0],405)
    def test_no_plaintext_api(self):
        with socket.create_connection(("127.0.0.1",self.srv.server_port),timeout=4) as sock:
            sock.settimeout(3);sock.sendall(b"GET /v0/catalog/apps HTTP/1.0\r\n\r\n")
            try: data=sock.recv(256)
            except (OSError,ConnectionResetError): data=b""
            self.assertNotIn(b"DISCOVERED_ONLY",data)
    def test_key_permissions_fail_closed(self):
        self.key.chmod(0o640)
        try:
            with self.assertRaises(product.ProductConfigurationError):
                product.configure_tls(self.cert,self.key)
        finally:self.key.chmod(0o600)
    def test_private_key_symlink_rejected(self):
        link=self.folder/"link.key";link.symlink_to(self.key)
        with self.assertRaises(product.ProductConfigurationError):
            product.configure_tls(self.cert,link)
    def test_explicit_ipv4_bind_and_strong_token(self):
        for host in ("::","localhost","192.0.2.1"):
            with self.assertRaises(product.ProductConfigurationError):
                product.ProductServer(host,0,[],self.token,self.tls)
        with self.assertRaises(product.ProductConfigurationError):
            product.ProductServer("127.0.0.1",0,[],"weak",self.tls)
    def test_browser_avoids_persistent_secret_and_html_injection(self):
        js=(ROOT/"assets/app.js").read_text()
        self.assertNotIn("localStorage",js);self.assertNotIn("innerHTML",js)
        self.assertIn("credentials:'omit'",js);self.assertIn("textContent",js)
    def test_image_requires_explicit_base(self):
        docker=(ROOT/"Dockerfile").read_text()
        self.assertIn("ARG PYTHON_IMAGE\nFROM ${PYTHON_IMAGE}",docker)
        self.assertIn("USER 65532:65532",docker)
        self.assertNotIn("docker.sock",docker)

if __name__=="__main__":unittest.main()

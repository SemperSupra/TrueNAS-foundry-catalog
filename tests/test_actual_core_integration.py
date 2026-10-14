"""Live TLS integration with exact Git-SHA-pinned generic Foundry modules.

The workflow first downloads both reviewed modules from the pinned commit.
Never substitute stubbed modules for these assertions.
"""
from __future__ import annotations
import http.client
import importlib.util
import json
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
FED=ROOT/"vendor/foundry_catalog_federation.py"
HTTP=ROOT/"vendor/foundry_catalog_read_http.py"

@unittest.skipUnless(FED.is_file() and HTTP.is_file(),"pinned upstream not available locally")
class ActualSourceCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location("catalog_product",ROOT/"src/server.py")
        cls.product=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.product)
        cls.temp=tempfile.TemporaryDirectory()
        root=Path(cls.temp.name)
        source={
            "schema":cls.product.federation.SCHEMA,
            "publisher":"test.example","source":"offline",
            "uri":"https://example.org/catalog.git",
            "revision":"a"*40,
            "apps":[{"train":"community","name":"jellyfin","version":"1.0.0",
                     "path":"ix-dev/community/jellyfin",
                     "source_tree_sha256":"sha256:"+"b"*64}],
        }
        idx=root/"source.json";idx.write_text(json.dumps(source))
        cls.rows=cls.product.federation.load_catalogs([idx])
        cls.bearer="integration_token_"+"x"*45
        cert=root/"tls.crt";key=root/"tls.key"
        subprocess.run(["openssl","req","-new","-x509","-nodes","-newkey","rsa:2048",
                        "-days","1","-subj","/CN=localhost",
                        "-keyout",str(key),"-out",str(cert)],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        key.chmod(0o600)
        tls=cls.product.configure_tls(cert,key)
        cls.http=cls.product.ProductServer("127.0.0.1",0,cls.rows,cls.bearer,tls)
        cls.worker=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.worker.start()
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.worker.join(timeout=5);cls.http.server_close();cls.temp.cleanup()
    def request(self,path,authorized=True,method="GET"):
        conn=http.client.HTTPSConnection("127.0.0.1",self.http.server_port,
                                         context=ssl._create_unverified_context(),timeout=5)
        headers={"Authorization":"Bearer "+self.bearer} if authorized else {}
        conn.request(method,path,headers=headers)
        response=conn.getresponse();result=response.status,response.read()
        conn.close();return result
    def test_real_core_listing_and_bearer(self):
        status,raw=self.request("/v0/catalog/apps")
        self.assertEqual(status,200)
        result=json.loads(raw)
        self.assertEqual(result,self.product.federation.query(self.rows,"list"))
        self.assertEqual(result["apps"][0]["admission"],"DISCOVERED_ONLY")
        self.assertEqual(self.request("/v0/catalog/apps",authorized=False)[0],401)
    def test_real_core_resolve_has_no_mutation(self):
        from urllib.parse import urlencode
        row=self.rows[0]
        query=urlencode({"package_id":row["package_id"],"version":row["version"],
                         "revision":row["source_revision"],"digest":row["source_tree_sha256"]})
        code,payload=self.request("/v0/catalog/resolve?"+query)
        self.assertEqual(code,200)
        self.assertEqual(json.loads(payload)["mutation_eligible"],False)
        self.assertEqual(self.request("/v0/catalog/apps",method="POST")[0],405)

if __name__=="__main__":unittest.main()

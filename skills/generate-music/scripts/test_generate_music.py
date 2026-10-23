#!/usr/bin/env python3
"""Offline tests: run generate-music.py against fake ACE-Step and gateway servers.

  python3 scripts/test_generate_music.py
"""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("generate_music", HERE / "generate-music.py")
gm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gm)

FAKE_MP3 = b"ID3fake-mp3-bytes"


class FakeServer(BaseHTTPRequestHandler):
    requests: ClassVar[list] = []
    polls_before_done = 1
    file_url = "/v1/audio?path=%2Ftmp%2Fx.mp3"
    redirect_to = ""
    poll_failures = 0

    def log_message(self, *args):
        pass

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        FakeServer.requests.append({"path": self.path, "method": "GET", "auth": self.headers.get("Authorization", "")})
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", FakeServer.redirect_to)
            self.end_headers()
            return
        if self.path == "/health":
            return self._send({"data": {"status": "ok", "service": "ACE-Step API"}, "code": 200})
        if self.path.startswith("/v1/audio"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(FAKE_MP3)
            return
        self._send({"error": "nope"}, 404)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        ctype = self.headers.get("Content-Type", "")
        rec = {"path": self.path, "ctype": ctype, "auth": self.headers.get("Authorization", "")}
        rec["body"] = json.loads(raw) if ctype.startswith("application/json") else raw
        FakeServer.requests.append(rec)
        if self.path == "/release_task":
            return self._send({"data": {"task_id": "t1", "status": "queued"}, "code": 200})
        if self.path == "/query_result":
            done = sum(r["path"] == "/query_result" for r in FakeServer.requests) > FakeServer.polls_before_done
            if not done:
                return self._send({"data": [{"task_id": "t1", "status": 0}]})
            result = json.dumps([{"file": FakeServer.file_url, "status": 1, "metas": {"bpm": 90}}])
            return self._send({"data": [{"task_id": "t1", "status": 1, "result": result}]})
        if self.path == "/submit_song":
            return self._send({"call_id": "fc-1"})
        if self.path == "/poll_song":
            if FakeServer.poll_failures > 0:
                FakeServer.poll_failures -= 1
                return self._send({"error": "upstream hiccup"}, 503)
            return self._send({"status": "done", "mp3_b64": base64.b64encode(FAKE_MP3).decode()})
        self._send({"error": "nope"}, 404)


class GenerateMusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeServer)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeServer.requests = []
        FakeServer.file_url = "/v1/audio?path=%2Ftmp%2Fx.mp3"
        FakeServer.redirect_to = ""
        FakeServer.poll_failures = 0
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        clean = {k: v for k, v in os.environ.items() if not k.startswith(("MUSICGEN_", "ACESTEP_"))}
        self.env = mock.patch.dict(os.environ, clean, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def run_cli(self, *args):
        return gm.main([*args, "--poll-interval", "0.01", "--timeout", "10"])

    def test_normalize_lyrics_splits_same_line_tags(self):
        self.assertEqual(gm.normalize_lyrics("[Verse] hello\nworld"), "[Verse]\nhello\nworld")

    def test_acestep_api_text2music(self):
        os.environ.update(ACESTEP_API_URL=self.url, ACESTEP_API_KEY="k")
        out = self.dir / "a.mp3"
        rc = self.run_cli("--model", "acestep", "--prompt", "lo-fi, dusty Rhodes", "--instrumental",
                          "--seconds", "30", "--seed", "7", "--bpm", "85", "--out", str(out))
        self.assertEqual(rc, 0)
        self.assertEqual(out.read_bytes(), FAKE_MP3)
        release = FakeServer.requests[0]
        self.assertEqual(release["auth"], "Bearer k")
        body = release["body"]
        self.assertEqual(body["lyrics"], "[Instrumental]")
        self.assertEqual(body["audio_duration"], 30.0)
        self.assertEqual(body["seed"], 7)
        self.assertFalse(body["use_random_seed"])
        self.assertEqual(body["bpm"], 85)
        self.assertFalse(body["thinking"])
        download = [r for r in FakeServer.requests if r["path"].startswith("/v1/audio")][0]
        self.assertEqual(download["auth"], "Bearer k")  # same host as ACESTEP_API_URL

    def gets(self, prefix):
        return [r for r in FakeServer.requests if r.get("method") == "GET" and r["path"].startswith(prefix)]

    def test_acestep_download_skips_auth_on_other_host(self):
        os.environ.update(ACESTEP_API_URL=self.url, ACESTEP_API_KEY="k")
        FakeServer.file_url = self.url.replace("127.0.0.1", "localhost") + "/v1/audio?path=x.mp3"
        out = self.dir / "o.mp3"
        self.assertEqual(self.run_cli("--model", "acestep", "--prompt", "x", "--out", str(out)), 0)
        self.assertEqual(self.gets("/v1/audio")[0]["auth"], "")

    def test_acestep_download_strips_auth_on_cross_host_redirect(self):
        os.environ.update(ACESTEP_API_URL=self.url, ACESTEP_API_KEY="k")
        FakeServer.file_url = "/redirect"
        FakeServer.redirect_to = self.url.replace("127.0.0.1", "localhost") + "/v1/audio?path=x.mp3"
        out = self.dir / "r.mp3"
        self.assertEqual(self.run_cli("--model", "acestep", "--prompt", "x", "--out", str(out)), 0)
        self.assertEqual(out.read_bytes(), FAKE_MP3)
        self.assertEqual(self.gets("/redirect")[0]["auth"], "Bearer k")
        self.assertEqual(self.gets("/v1/audio")[0]["auth"], "")

    def test_acestep_download_failure_exits_1(self):
        os.environ["ACESTEP_API_URL"] = self.url
        FakeServer.file_url = "/missing.mp3"
        self.assertEqual(self.run_cli("--model", "acestep", "--prompt", "x", "--out", str(self.dir / "f.mp3")), 1)

    def test_gateway_acestep_carries_language_steps_thinking(self):
        os.environ["MUSICGEN_GATEWAY_URL"] = self.url
        rc = self.run_cli("--model", "acestep", "--backend", "gateway", "--prompt", "city pop",
                          "--lyrics", "[Verse]\nhello", "--language", "ja", "--steps", "12", "--thinking",
                          "--seed", "3", "--out", str(self.dir / "g.mp3"))
        self.assertEqual(rc, 0)
        submit = FakeServer.requests[0]["body"]
        self.assertEqual(submit["vocal_language"], "ja")
        self.assertEqual(submit["inference_steps"], 12)
        self.assertIs(submit["thinking"], True)
        self.assertEqual(submit["seed"], 3)

    def test_gateway_acestep_thinking_defaults_off_and_instrumental_drops_lyrics(self):
        os.environ["MUSICGEN_GATEWAY_URL"] = self.url
        rc = self.run_cli("--model", "acestep", "--backend", "gateway", "--prompt", "ambient",
                          "--lyrics", "[Verse]\nhello", "--instrumental", "--out", str(self.dir / "g.mp3"))
        self.assertEqual(rc, 0)
        submit = FakeServer.requests[0]["body"]
        self.assertIs(submit["thinking"], False)
        self.assertEqual(submit["lyrics"], "")

    def test_gateway_poll_retries_transient_errors(self):
        os.environ["MUSICGEN_GATEWAY_URL"] = self.url
        FakeServer.poll_failures = 2
        rc = self.run_cli("--model", "acestep", "--backend", "gateway", "--prompt", "x", "--out", str(self.dir / "p.mp3"))
        self.assertEqual(rc, 0)
        self.assertEqual(sum(r["path"] == "/poll_song" for r in FakeServer.requests), 3)

    def test_gateway_music3_instrumental_keeps_tag_sheet(self):
        os.environ["MUSICGEN_GATEWAY_URL"] = self.url
        sheet = "[Intro]\n(instrumental)\n[Verse]\n(instrumental)\n[Outro]\n(instrumental)"
        rc = self.run_cli("--model", "music3", "--prompt", "post-rock, swelling guitars", "--instrumental",
                          "--lyrics", sheet, "--out", str(self.dir / "i.mp3"))
        self.assertEqual(rc, 0)
        submit = FakeServer.requests[0]["body"]
        self.assertEqual(submit["lyrics"], sheet)
        self.assertTrue(submit["instrumental"])

    def test_dit_model_rejected_off_api_backend(self):
        os.environ["MUSICGEN_GATEWAY_URL"] = self.url
        rc = self.run_cli("--model", "acestep", "--backend", "gateway", "--prompt", "x",
                          "--dit-model", "acestep-v15-xl-turbo", "--dry-run")
        self.assertEqual(rc, 1)

    def test_acestep_api_cover_uploads_multipart(self):
        os.environ["ACESTEP_API_URL"] = self.url
        src = self.dir / "src.mp3"
        src.write_bytes(b"source-audio")
        out = self.dir / "c.mp3"
        rc = self.run_cli("--model", "acestep", "--prompt", "jazz trio", "--task", "cover",
                          "--src-audio", str(src), "--strength", "0.3", "--out", str(out))
        self.assertEqual(rc, 0)
        release = FakeServer.requests[0]
        self.assertTrue(release["ctype"].startswith("multipart/form-data"))
        self.assertIn(b'name="src_audio"; filename="src.mp3"', release["body"])
        self.assertIn(b"source-audio", release["body"])
        self.assertIn(b'name="audio_cover_strength"\r\n\r\n0.3', release["body"])

    def test_auto_backend_ignores_non_acestep_health(self):
        with mock.patch.object(gm, "acestep_healthy", return_value=False), \
             mock.patch.object(gm, "modal_available", return_value=False):
            with self.assertRaises(gm.GenError):
                gm.resolve_backend("acestep", "auto")

    def test_gateway_music3(self):
        os.environ.update(MUSICGEN_GATEWAY_URL=self.url, MUSICGEN_GATEWAY_TOKEN="tok")
        out = self.dir / "m.mp3"
        rc = self.run_cli("--model", "music3", "--prompt", "warm acoustic pop, soft female vocal",
                          "--lyrics", "[Verse] morning light", "--seconds", "500", "--out", str(out))
        self.assertEqual(rc, 0)
        self.assertEqual(out.read_bytes(), FAKE_MP3)
        submit = FakeServer.requests[0]["body"]
        self.assertEqual(submit["token"], "tok")
        self.assertEqual(submit["model"], "music3")
        self.assertEqual(submit["lyrics"], "[Verse]\nmorning light")
        self.assertEqual(submit["max_audio_length_ms"], 300_000)  # clamped to Music 3's cap

    def test_suno_handoff_writes_files(self):
        out = self.dir / "song.mp3"
        rc = self.run_cli("--model", "suno", "--prompt", "x" * 1200, "--lyrics", "[Chorus]\nla", "--out", str(out))
        self.assertEqual(rc, 0)
        self.assertEqual(len((self.dir / "song-style-prompt.txt").read_text().strip()), 1200)
        self.assertIn("[Chorus]", (self.dir / "song-lyrics.txt").read_text())

    def test_validation_errors(self):
        self.assertEqual(self.run_cli("--model", "music3", "--prompt", "pop", "--backend", "gateway"), 1)
        self.assertEqual(self.run_cli("--model", "heartmula", "--prompt", "pop", "--instrumental"), 1)
        self.assertEqual(self.run_cli("--model", "acestep", "--prompt", "x", "--task", "cover"), 1)
        self.assertEqual(self.run_cli("--model", "lyria", "--prompt", "x", "--backend", "modal"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Hermes 関連テストの共有フィクスチャ

使い方: from tests.hermes_fakes import fake_open, planting_id, crop_id, variety_id
"""
import io
import json
import urllib.error

import pytest

from app.models.crop import Crop
from app.models.location import Location
from app.models.planting import Planting
from app.models.variety import Variety
from app.utils import hermes_client


class _FakeResponse:
    def __init__(self, status, body=b'', lines=None):
        self.status = status
        self._body = body
        self._lines = lines

    def read(self):
        return self._body

    def __iter__(self):
        return iter(self._lines if self._lines is not None else self._body.splitlines(True))

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpen:
    """hermes_client._open の差し替え。呼び出しを calls に記録し、積んだ応答を順に返す"""

    def __init__(self):
        self.calls = []
        self.timeouts = []
        self._queue = []

    def reply(self, status, data):
        self._queue.append(('reply', status, data))

    def raise_(self, exc):
        self._queue.append(('raise', exc, None))

    def stream(self, lines):
        self._queue.append(('stream', 200, lines))

    def __call__(self, req, timeout):
        self.calls.append(req)
        self.timeouts.append(timeout)
        if not self._queue:
            raise AssertionError('FakeOpen: 応答が積まれていない')
        kind, a, b = self._queue.pop(0)
        if kind == 'raise':
            raise a
        if kind == 'stream':
            return _FakeResponse(200, lines=b)
        body = json.dumps(b, ensure_ascii=False).encode('utf-8')
        if a >= 400:
            raise urllib.error.HTTPError(req.full_url, a, 'error', {}, io.BytesIO(body))
        return _FakeResponse(a, body)


@pytest.fixture
def fake_open(app, monkeypatch):
    app.config['HERMES_API_KEY'] = 'test-hermes-key'
    fake = FakeOpen()
    monkeypatch.setattr(hermes_client, '_open', fake)
    return fake


@pytest.fixture
def crop_id(app):
    with app.app_context():
        return Crop.create({'name': '玉ねぎ', 'crop_type': '根菜類'})


@pytest.fixture
def variety_id(app, crop_id):
    with app.app_context():
        return Variety.create({'crop_id': crop_id, 'name': 'ネオアース'})


@pytest.fixture
def planting_id(app, variety_id):
    with app.app_context():
        loc_id = Location.create({'name': '東の畑', 'location_type': '畑'})
        return Planting.plant({'location_id': loc_id, 'variety_id': variety_id,
                               'planted_date': '2026-10-01'})

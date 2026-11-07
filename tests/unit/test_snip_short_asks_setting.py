"""snip_short_asks setting: global default, per-feed column, resolver, API, config transfer."""
import json

import pytest

from tests.app_bootstrap import bootstrap

bootstrap('snip_short_asks_setting_test_', passphrase='snip-short-asks-test-passphrase')

import database
from main_app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def db():
    return database.Database()


@pytest.fixture
def feed_slug(db, preserve_setting):
    preserve_setting('snip_short_asks')
    slug = 'snip-short-asks-feed'
    db.create_podcast(slug, 'https://example.com/feed.xml', title='Snip Short Asks')
    yield slug
    db.delete_podcast(slug)


class TestResolver:
    def test_default_is_off(self, db, feed_slug):
        assert db.resolve_snip_short_asks(feed_slug) is False

    def test_per_feed_null_inherits_global(self, db, feed_slug):
        db.set_setting('snip_short_asks', 'true', is_default=False)
        assert db.resolve_snip_short_asks(feed_slug) is True

    def test_per_feed_off_beats_global_on(self, db, feed_slug):
        db.set_setting('snip_short_asks', 'true', is_default=False)
        db.update_podcast(feed_slug, snip_short_asks=0)
        assert db.resolve_snip_short_asks(feed_slug) is False

    def test_per_feed_on_beats_global_off(self, db, feed_slug):
        db.set_setting('snip_short_asks', 'false', is_default=False)
        db.update_podcast(feed_slug, snip_short_asks=1)
        assert db.resolve_snip_short_asks(feed_slug) is True

    def test_podcast_dict_avoids_lookup(self, db, feed_slug):
        db.update_podcast(feed_slug, snip_short_asks=1)
        podcast = db.get_podcast_by_slug(feed_slug)
        assert db.resolve_snip_short_asks(feed_slug, podcast=podcast) is True


class TestApi:
    def test_global_put_get_round_trip(self, client, feed_slug):
        assert client.get('/api/v1/settings').get_json()['snipShortAsks']['value'] is False
        resp = client.put('/api/v1/settings/ad-detection', json={'snipShortAsks': True})
        assert resp.status_code == 200, resp.data
        assert client.get('/api/v1/settings').get_json()['snipShortAsks']['value'] is True
        client.put('/api/v1/settings/ad-detection', json={'snipShortAsks': False})
        assert client.get('/api/v1/settings').get_json()['snipShortAsks']['value'] is False

    def test_per_feed_patch_true_false_null(self, client, db, feed_slug):
        for sent, stored in ((True, 1), (False, 0), (None, None)):
            resp = client.patch(f'/api/v1/feeds/{feed_slug}', json={'snipShortAsks': sent})
            assert resp.status_code == 200, resp.data
            assert resp.get_json()['snipShortAsks'] is sent
            assert db.get_podcast_by_slug(feed_slug)['snip_short_asks'] == stored

    def test_feed_get_reports_field(self, client, feed_slug):
        resp = client.get(f'/api/v1/feeds/{feed_slug}')
        assert 'snipShortAsks' in resp.get_json()


class TestConfigTransfer:
    def test_feed_column_is_exported_as_a_bool(self):
        import config_transfer
        assert 'snip_short_asks' in config_transfer.FEED_COLUMNS
        assert 'snip_short_asks' in config_transfer.FEED_BOOL_COLUMNS

    def test_feed_value_survives_export_import(self, db, feed_slug):
        import config_transfer
        db.update_podcast(feed_slug, snip_short_asks=1)
        row = db.get_podcast_by_slug(feed_slug)
        exported = {c: row.get(c) for c in config_transfer.FEED_COLUMNS if c in row}
        assert exported['snip_short_asks'] == 1

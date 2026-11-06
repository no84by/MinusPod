"""snip_short_asks off: prompts and schemas are pinned to the 2.101.25 output by sha256."""
import hashlib
import json
from unittest.mock import MagicMock

import pytest

from tests.app_bootstrap import bootstrap

bootstrap('snip_short_asks_golden_test_')

from ad_detector import AdDetector
from ad_detector.prompts import ad_detection_json_schema
from ad_reviewer import AdReviewer

GOLDEN = {
    'detect show=False timestamps': 'ac44ea49c4d45e3fe4bb43b8013dc4a7711b878e5972aafe235caa5147bfd7d9',
    'detect show=False segment_ids': 'abf30034b5d4f9513f35d5a3aed63bae8748ab6ee07c885575aaf2df1c9a1abd',
    'detect show=True timestamps': '5a883057be26f4452470fb5651c894b05c863a83b9c183eb5796c442b26e8174',
    'detect show=True segment_ids': '8d390525c29a1a408b520b7513c1bb509a05879d973e0297f1b383aaa8532922',
    'schema timestamps': '7215ffeef461bab609f97f6c4262b5b25ad255aae52f16c4cfc8a616d0d1a51f',
    'schema segment_ids': '8a67eb04c9121ca41bd7b857d53c9df6feb54d8fa6868b954f59e704fd5b965f',
    'review': '11dc93e127d1e0fd9707b8e228e2d2220ed0a123947c12098caaba30fbb6fbe3',
    'resurrect': 'df2a2018b97963e5d1bf7873ce209c942e6618689942217419394a14a73b968f',
}


class _Db:
    def __init__(self, show):
        self.show = show

    def get_setting(self, key):
        return None

    def resolve_detect_show_segments(self, slug, podcast=None):
        return self.show

    def resolve_snip_short_asks(self, slug, podcast=None):
        return False


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _rendered():
    out = {}
    for show in (False, True):
        det = AdDetector()
        det.db = _Db(show)
        det.sponsor_service = None
        for mode in ('timestamps', 'segment_ids'):
            out[f'detect show={show} {mode}'] = det._build_detection_system_prompt('feed', mode)
    for mode in ('timestamps', 'segment_ids'):
        out[f'schema {mode}'] = json.dumps(ad_detection_json_schema(mode), sort_keys=True, indent=1)
    db = MagicMock()
    db.get_setting.return_value = None
    reviewer = AdReviewer(db=db, llm_client=MagicMock())
    out['review'] = reviewer._render_review_prompt(60, 'SPONSORS')
    out['resurrect'] = reviewer._render_resurrect_prompt('SPONSORS')
    return out


@pytest.mark.parametrize('name', sorted(GOLDEN))
def test_off_output_equals_upstream(name):
    assert _sha(_rendered()[name]) == GOLDEN[name]

"""Evidence-bound exploration learning through the public project API."""
import pytest
from scripts.ui_test_core.strategy_learning import applicable_experiences, learn, choose_strategy


def test_no_evidence_cannot_enable_or_create_experience(tmp_path):
    with pytest.raises((ValueError, FileNotFoundError)):
        learn(tmp_path, tmp_path / 'missing-run', 'COMPLETE')
    assert applicable_experiences(tmp_path, {}, {}, 'build') == []


def test_failure_excludes_only_its_strategy_and_stops_when_all_are_excluded():
    negative = dict(experience_id='experience-a', strategy='broad', pattern='failure', mode='trial')
    approved = dict(experience_id='experience-b', strategy='targeted', pattern='success', mode='enabled')
    selected, feedback = choose_strategy(['broad', 'targeted'], [negative, approved])
    assert selected == 'targeted'
    assert [(e['experience_id'], e['disposition']) for e in feedback] == [
        ('experience-a', 'exclude'), ('experience-b', 'adopt')]
    selected, feedback = choose_strategy(['broad'], [negative])
    assert selected is None and feedback == [dict(negative, disposition='exclude')]

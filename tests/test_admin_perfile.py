"""The repair must preserve values and identify, never guess, sampling."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_admin_perfile import assign_settings
from audit_admin_sampling import compare


def row(month, matches):
    return {'environment': 'production', 'country': 'capeverde', 'year': 2026,
            'month': month, 'file': f'{month}.json', 'matches': matches}


def test_indeterminate_uses_nearest_determinate_neighbour_with_earlier_tie():
    rows = [row(4, [False]), row(5, [False, True]), row(6, [True]), row(7, [False, True])]
    assign_settings(rows)
    assert [r['selected_all_touched'] for r in rows] == [False, False, True, True]
    assert rows[1]['determination'] == 'indeterminate_both_match'
    assert rows[1]['neighbour_file'] == '4.json'
    assert rows[3]['neighbour_file'] == '6.json'


def test_no_match_cannot_select_neighbour():
    with pytest.raises(ValueError, match='Unmatched'):
        assign_settings([row(4, [False]), row(5, [])])


def test_all_indeterminate_cannot_invent_setting():
    with pytest.raises(ValueError, match='No determinate'):
        assign_settings([row(4, [False, True])])


def test_environments_are_independent():
    rows = [row(4, [False]), {**row(4, [True]), 'environment': 'local'}]
    assign_settings(rows)
    assert rows[0]['selected_all_touched'] is False
    assert rows[1]['selected_all_touched'] is True


def test_exact_comparison_does_not_fill_null_or_accept_close_value():
    old = {'islands': {'|Town': {'mean': None, 'max': 1.2, 'min': 1.1}}}
    new = {'islands': {'Town': {'mean': None, 'max': 1.2, 'min': 1.1}}}
    assert compare(old, new, 'capeverde') == []
    new['islands']['Town']['mean'] = 0
    assert len(compare(old, new, 'capeverde')) == 1
    new['islands']['Town']['mean'] = None
    new['islands']['Town']['max'] = 1.20000001
    assert len(compare(old, new, 'capeverde')) == 1


def test_only_ivorycoast_second_level_exempt():
    old = {'districts': {'|Parent': {'mean': 1}}, 'regions': {'Parent': {'mean': 2}}}
    new = {'districts': {'Parent': {'mean': 1}}, 'regions': {'Child|Parent': {'mean': 3}}}
    assert compare(old, new, 'ivorycoast') == []
    new['districts']['Parent']['mean'] = 2
    assert len(compare(old, new, 'ivorycoast')) == 1

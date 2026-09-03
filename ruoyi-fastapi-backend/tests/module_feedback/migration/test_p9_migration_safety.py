from copy import deepcopy

from scripts.feedback_p9_migration import canonical_default, canonical_expression, compare_schema


def test_pg_restore_array_cast_normalization_preserves_operators_and_values() -> None:
    original = (
        "CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'COMPLETED'::character varying])::text[])))"
    )
    restored = "CHECK (((status)::text = ANY (ARRAY[('ACTIVE'::character varying)::text, ('COMPLETED'::character varying)::text])))"
    assert canonical_expression(original) == canonical_expression(restored)
    assert canonical_expression(original) != canonical_expression(restored.replace('ACTIVE', 'PREPARING'))
    assert canonical_expression(original) != canonical_expression(restored.replace('= ANY', '<> ALL'))
    assert canonical_default('now()') == canonical_default('CURRENT_TIMESTAMP')
    assert canonical_default("'0'::numeric") == canonical_default('0')
    assert canonical_default("'1'::numeric") != canonical_default('0')


def test_adoption_rejects_changed_constraints_missing_indexes_and_unknown_columns() -> None:
    source = {
        'tables': {'fb_project': '评价项目'},
        'columns': {'fb_project.status': ['character varying', 'NO', "'PREPARING'::character varying", None, None, 16]},
        'constraints': {'fb_project.status_check': ['c', 'CHECK (true)', True]},
        'indexes': {},
        'comments': {},
    }
    reference = deepcopy(source)
    reference['constraints']['fb_project.status_check'][1] = "CHECK (status IN ('PREPARING','ACTIVE','COMPLETED'))"
    reference['indexes']['fb_project.required_index'] = ['CREATE INDEX required_index', True, True]
    source['columns']['fb_project.unknown'] = ['text', 'YES', None, None, None, None]
    accepted, rejected = compare_schema(source, reference)
    assert not accepted
    assert {item['category'] for item in rejected} == {'columns', 'constraints', 'indexes'}


def test_adoption_rejects_partial_designer_columns() -> None:
    source = {'tables': {}, 'columns': {}, 'constraints': {}, 'indexes': {}, 'comments': {}}
    reference = deepcopy(source)
    source['columns']['fb_questionnaire_page.page_code'] = ['character varying', 'NO', None, None, None, 64]
    reference['columns'] = {
        **source['columns'],
        'fb_questionnaire_version.description_doc': ['jsonb', 'YES', None, None, None, None],
    }
    _, rejected = compare_schema(source, reference)
    assert any(item['object'] == 'P4_PARTIAL_COLUMNS' for item in rejected)

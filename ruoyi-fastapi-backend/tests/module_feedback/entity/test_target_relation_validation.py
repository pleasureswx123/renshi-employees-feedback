from decimal import Decimal
from types import SimpleNamespace as Obj

from module_feedback.validators import publication_validator as validator


def test_each_target_requires_each_enabled_relation(monkeypatch):
    monkeypatch.setattr(validator, 'get_publish_validation_issues', lambda _: [])
    targets = [Obj(target_id=i, target_user_id=i, target_user_name=f'员工{i}') for i in (1, 2)]
    relations = [
        Obj(
            relation_id=1,
            relation_code='REL_SELF',
            relation_name='自己',
            is_enabled=True,
            participates_in_score=False,
            weight=Decimal('0'),
        ),
        Obj(
            relation_id=2,
            relation_code='REL_UPPER',
            relation_name='上级',
            is_enabled=True,
            participates_in_score=True,
            weight=Decimal('50'),
        ),
        Obj(
            relation_id=3,
            relation_code='REL_PEER',
            relation_name='同级',
            is_enabled=True,
            participates_in_score=True,
            weight=Decimal('50'),
        ),
    ]
    selections = [Obj(target_id=t, relation_id=r, evaluator_user_id=10) for t, r in [(1, 2), (1, 3), (2, 3)]]
    issues = validator.get_publication_validation_issues(None, targets, relations, selections)
    assert issues == [
        {
            'code': 'TARGET_RELATION_ASSIGNMENT_REQUIRED',
            'path': 'targets.1.relations.REL_UPPER',
            'message': '被评价人“员工2”尚未配置“上级”评价人',
        }
    ]
    selections.append(Obj(target_id=2, relation_id=2, evaluator_user_id=11))
    assert validator.get_publication_validation_issues(None, targets, relations, selections) == []
    # 非计分关系也属于启用关系，必须逐人配置。
    relations[1].participates_in_score = False
    relations[1].weight = Decimal('0')
    relations[2].weight = Decimal('100')
    assert any(
        issue['code'] == 'TARGET_RELATION_ASSIGNMENT_REQUIRED'
        for issue in validator.get_publication_validation_issues(None, targets, relations, selections[:-1])
    )
    # 没有启用他评关系的仅自评配置不要求他评人员。
    relations[1].is_enabled = False
    relations[2].is_enabled = False
    assert validator.get_publication_validation_issues(None, targets, relations, []) == []


def test_supervisor_peer_conflict_is_scoped_to_target(monkeypatch):
    monkeypatch.setattr(validator, 'get_publish_validation_issues', lambda _: [])
    targets = [Obj(target_id=i, target_user_id=i, target_user_name=f'员工{i}') for i in (1, 2)]
    relations = [Obj(relation_id=i, relation_code=code, relation_name=name, relation_type=kind, is_enabled=True, participates_in_score=i != 1, weight=Decimal('0' if i == 1 else '50')) for i, code, name, kind in [(1, 'REL_SELF', '自己', 'SELF'), (2, 'REL_SUPERVISOR', '上级', 'SUPERVISOR'), (3, 'REL_PEER', '同级', 'PEER')]]
    selections = [Obj(target_id=t, relation_id=r, evaluator_user_id=u) for t, r, u in [(1, 2, 10), (1, 3, 11), (2, 2, 11), (2, 3, 10)]]
    assert validator.get_publication_validation_issues(None, targets, relations, selections) == []
    selections.append(Obj(target_id=1, relation_id=3, evaluator_user_id=10))
    issues = validator.get_publication_validation_issues(None, targets, relations, selections)
    assert len(issues) == 1
    assert issues[0]['code'] == 'EVALUATOR_RELATION_CONFLICT'
    assert issues[0]['path'] == 'targets.0.relations.REL_PEER'

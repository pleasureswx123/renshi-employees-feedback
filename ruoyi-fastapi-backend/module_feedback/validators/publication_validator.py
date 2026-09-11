from decimal import Decimal
from typing import Any

from module_feedback.constants import SELF_RELATION_CODE
from module_feedback.validators.questionnaire_validator import get_publish_validation_issues


def get_publication_validation_issues(
    questionnaire: Any,
    targets: list[Any],
    relations: list[Any],
    selections: list[Any],
    unavailable_target_ids: set[int] | None = None,
    unavailable_evaluator_ids: set[int] | None = None,
) -> list[dict[str, str]]:
    """组合P4问卷问题与P5人员、关系和任务问题。"""
    issues = list(get_publish_validation_issues(questionnaire))
    if not targets:
        issues.append({'code': 'TARGET_REQUIRED', 'path': 'targets', 'message': '至少选择一名被评价人'})
    unavailable_target_ids = unavailable_target_ids or set()
    unavailable_evaluator_ids = unavailable_evaluator_ids or set()
    for target_index, target in enumerate(targets):
        if int(target.target_user_id) in unavailable_target_ids:
            issues.append(
                {
                    'code': 'TARGET_USER_UNAVAILABLE',
                    'path': f'targets.{target_index}',
                    'message': f'被评价人“{target.target_user_name}”当前不可用或不在人员数据范围内',
                }
            )

    self_relations = [
        relation
        for relation in relations
        if relation.relation_code == SELF_RELATION_CODE
        and relation.is_enabled
        and not relation.participates_in_score
        and relation.weight == Decimal('0')
    ]
    if len(self_relations) != 1:
        issues.append(
            {
                'code': 'SELF_RELATION_REQUIRED',
                'path': 'relations',
                'message': '必须保留唯一、启用、不参与计分且权重为0.0000的自己关系',
            }
        )

    relation_by_id = {relation.relation_id: relation for relation in relations}
    non_self_selections = [
        item
        for item in selections
        if relation_by_id.get(item.relation_id) is not None
        and relation_by_id[item.relation_id].relation_code != SELF_RELATION_CODE
    ]
    scored_relations = [
        item
        for item in relations
        if item.relation_code != SELF_RELATION_CODE and item.is_enabled and item.participates_in_score
    ]
    if non_self_selections:
        total_weight = sum((item.weight for item in scored_relations), Decimal('0'))
        if total_weight != Decimal('100.0000'):
            issues.append(
                {
                    'code': 'RELATION_WEIGHT_TOTAL_INVALID',
                    'path': 'relations',
                    'message': f'存在他评任务时，计分关系权重合计必须为100.0000，当前为{total_weight:.4f}',
                }
            )

    selected_relation_ids = {item.relation_id for item in non_self_selections}
    for relation_index, relation in enumerate(relations):
        if relation in scored_relations and relation.relation_id not in selected_relation_ids:
            issues.append(
                {
                    'code': 'RELATION_POSITIVE_ASSIGNMENT_REQUIRED',
                    'path': f'relations.{relation_index}',
                    'message': f'计分关系“{relation.relation_name}”至少需要配置一名评价人',
                }
            )

    # 启用关系是每位被评价人的必配项，不能用其他人的分配抵消缺口。
    enabled_relations = [item for item in relations if item.is_enabled and item.relation_code != SELF_RELATION_CODE]
    selected_pairs = {(item.target_id, item.relation_id) for item in non_self_selections}
    for target_index, target in enumerate(targets):
        for relation in enabled_relations:
            if (target.target_id, relation.relation_id) not in selected_pairs:
                issues.append(
                    {
                        'code': 'TARGET_RELATION_ASSIGNMENT_REQUIRED',
                        'path': f'targets.{target_index}.relations.{relation.relation_code}',
                        'message': f'被评价人“{target.target_user_name}”尚未配置“{relation.relation_name}”评价人',
                    }
                )

    # 对同一被评价人，上级与同级互斥；不同被评价人之间不受此限制。
    superior_ids = {item.relation_id for item in enabled_relations if getattr(item, 'relation_type', None) == 'SUPERVISOR'}
    peer_relations = [item for item in enabled_relations if getattr(item, 'relation_type', None) == 'PEER']
    for target_index, target in enumerate(targets):
        superior_people = {item.evaluator_user_id for item in non_self_selections if item.target_id == target.target_id and item.relation_id in superior_ids}
        for peer in peer_relations:
            duplicate_people = {item.evaluator_user_id for item in non_self_selections if item.target_id == target.target_id and item.relation_id == peer.relation_id} & superior_people
            if duplicate_people:
                issues.append({'code': 'EVALUATOR_RELATION_CONFLICT', 'path': f'targets.{target_index}.relations.{peer.relation_code}', 'message': f'被评价人“{target.target_user_name}”有{len(duplicate_people)}名评价人同时被设为上级与同级，请保留一种关系'})

    scored_relation_ids = {item.relation_id for item in scored_relations}
    for target_index, target in enumerate(targets):
        target_non_self = [item for item in non_self_selections if item.target_id == target.target_id]
        if target_non_self and not any(item.relation_id in scored_relation_ids for item in target_non_self):
            issues.append(
                {
                    'code': 'TARGET_SCORING_ASSIGNMENT_REQUIRED',
                    'path': f'targets.{target_index}',
                    'message': f'被评价人“{target.target_user_name}”存在他评时至少需要一项计分关系评价',
                }
            )
    for selection_index, selection in enumerate(selections):
        if int(selection.evaluator_user_id) in unavailable_evaluator_ids:
            issues.append(
                {
                    'code': 'EVALUATOR_USER_UNAVAILABLE',
                    'path': f'evaluatorSelections.{selection_index}',
                    'message': f'评价人ID {selection.evaluator_user_id} 当前不可用或不在人员数据范围内',
                }
            )
    return issues

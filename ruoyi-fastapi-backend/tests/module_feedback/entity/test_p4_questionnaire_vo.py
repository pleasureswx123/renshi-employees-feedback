from collections.abc import Callable
from copy import deepcopy
from decimal import Decimal

import pytest
from pydantic import ValidationError

from module_feedback.entity.do import FbQuestionnairePage, FbQuestionnaireVersion
from module_feedback.entity.vo import QuestionnaireDraftSaveModel
from module_feedback.entity.vo.employee_vo import EmployeeQuestionnaireModel
from module_feedback.service.publication_service import FeedbackPublicationService
from module_feedback.service.questionnaire_service import FeedbackQuestionnaireService
from module_feedback.validators import calculate_question_max_score, get_publish_validation_issues

EXPECTED_SCORED_QUESTION_COUNT = 4


def build_full_draft_payload() -> dict:
    return {
        'versionId': 20,
        'lockVersion': 3,
        'title': 'P4完整问卷',
        'description': '该摘要必须由后端重建',
        'descriptionDoc': {
            'type': 'doc',
            'content': [
                {
                    'type': 'heading',
                    'attrs': {'level': 2},
                    'content': [{'type': 'text', 'text': '评价说明'}],
                },
                {
                    'type': 'paragraph',
                    'content': [
                        {'type': 'text', 'text': '请根据实际表现', 'marks': [{'type': 'bold'}]},
                        {'type': 'text', 'text': '完成评价。'},
                    ],
                },
            ],
        },
        'settings': {'showProgress': True},
        'pages': [
            {
                'pageCode': 'P_CORE',
                'pageTitle': '核心能力',
                'sortOrder': 1,
                'questions': [
                    {
                        'questionCode': 'Q_SINGLE',
                        'questionType': 'SINGLE_CHOICE',
                        'title': '目标是否清晰',
                        'isRequired': True,
                        'isScored': True,
                        'minScore': None,
                        'maxScore': None,
                        'decimalPlaces': 0,
                        'config': {},
                        'sortOrder': 1,
                        'options': [
                            {
                                'optionCode': 'O_YES',
                                'optionLabel': '是',
                                'score': '5.0000',
                                'sortOrder': 1,
                            },
                            {
                                'optionCode': 'O_NO',
                                'optionLabel': '否',
                                'score': '1.0000',
                                'sortOrder': 2,
                            },
                        ],
                    },
                    {
                        'questionCode': 'Q_STAR',
                        'questionType': 'STAR_RATING',
                        'title': '协作表现',
                        'isRequired': True,
                        'isScored': True,
                        'minScore': '0',
                        'maxScore': '4',
                        'decimalPlaces': 0,
                        'config': {},
                        'sortOrder': 2,
                        'options': [],
                    },
                    {
                        'questionCode': 'Q_NUMBER',
                        'questionType': 'NUMERIC_INPUT',
                        'title': '目标完成率',
                        'isScored': True,
                        'minScore': '0.0000',
                        'maxScore': '100.0000',
                        'decimalPlaces': 2,
                        'config': {'defaultValue': '80.00'},
                        'sortOrder': 3,
                        'options': [],
                    },
                ],
            },
            {
                'pageCode': 'P_MORE',
                'pageTitle': '补充评价',
                'sortOrder': 2,
                'questions': [
                    {
                        'questionCode': 'Q_SLIDER',
                        'questionType': 'SLIDER',
                        'title': '综合评分',
                        'isScored': True,
                        'minScore': '0.0',
                        'maxScore': '10.0',
                        'decimalPlaces': 1,
                        'config': {'step': '0.5', 'defaultValue': '5.0'},
                        'sortOrder': 1,
                        'options': [],
                    },
                    {
                        'questionCode': 'Q_TEXT',
                        'questionType': 'TEXT',
                        'title': '改进建议',
                        'isRequired': False,
                        'isScored': False,
                        'minScore': None,
                        'maxScore': None,
                        'decimalPlaces': 0,
                        'config': {'maxLength': 1200},
                        'sortOrder': 2,
                        'options': [],
                    },
                ],
            },
        ],
        'indicators': [
            {
                'indicatorCode': 'I_PERFORMANCE',
                'indicatorName': '绩效表现',
                'weight': '100.0000',
                'sortOrder': 1,
                'questionCodes': ['Q_SINGLE', 'Q_NUMBER', 'Q_SLIDER'],
            },
            {
                'indicatorCode': 'I_COMMENT',
                'indicatorName': '定性建议',
                'weight': '0.0000',
                'sortOrder': 2,
                'questionCodes': ['Q_STAR', 'Q_TEXT'],
            },
        ],
    }


@pytest.mark.parametrize('field_name', ['pageDescription', 'page_description'])
def test_page_contract_rejects_retired_page_description(field_name: str) -> None:
    payload = build_full_draft_payload()
    payload['pages'][0][field_name] = '不再支持的页面说明'

    with pytest.raises(ValidationError) as exc_info:
        QuestionnaireDraftSaveModel.model_validate(payload)

    assert any(
        error['loc'] == ('pages', 0, field_name) and error['type'] == 'extra_forbidden'
        for error in exc_info.value.errors()
    )


def test_legacy_frozen_page_description_is_not_exposed_or_modified() -> None:
    page = FbQuestionnairePage(
        page_id=21,
        version_id=20,
        page_code='P_LEGACY',
        page_title='历史分页',
        page_description='保留的历史页面说明',
        sort_order=1,
        questions=[],
    )
    version = FbQuestionnaireVersion(
        version_id=20,
        lock_version=1,
        status='FROZEN',
        title='历史问卷',
        description='全卷统一说明',
        pages=[page],
        indicators=[],
    )

    payload = FeedbackQuestionnaireService._document_payload(version)
    employee = EmployeeQuestionnaireModel(
        **{key: payload[key] for key in ('versionId', 'title', 'description', 'descriptionDoc', 'pages')}
    )

    assert payload['description'] == '全卷统一说明'
    assert 'pageDescription' not in payload['pages'][0]
    assert 'pageDescription' not in employee.model_dump(by_alias=True)['pages'][0]
    assert page.page_description == '保留的历史页面说明'
    assert version.status == 'FROZEN'


@pytest.mark.parametrize(
    ('score', 'issue_code'), [('0.0000', 'OPTION_SCORE_POSITIVE_REQUIRED'), ('4.5000', 'OPTION_SCORE_INTEGER_REQUIRED')]
)
def test_invalid_option_score_remains_readable_but_cannot_be_published(
    monkeypatch: pytest.MonkeyPatch, score: str, issue_code: str
) -> None:
    payload = build_full_draft_payload()
    payload['pages'][0]['questions'][0]['options'][0]['score'] = score
    monkeypatch.setattr(FeedbackQuestionnaireService, '_document_payload', lambda _: payload)
    frozen = FbQuestionnaireVersion(version_id=20, status='FROZEN')
    document = FeedbackPublicationService._questionnaire_model(frozen)
    assert document.pages[0].questions[0].options[0].score == Decimal(score)
    issues = get_publish_validation_issues(document)
    assert issues == [
        {
            'code': issue_code,
            'path': 'pages.0.questions.0.options.0.score',
            'message': '单选题“目标是否清晰”的选项“是”分值必须是大于等于1的整数',
        }
    ]
    assert frozen.status == 'FROZEN'


def test_option_score_defaults_to_one_when_omitted() -> None:
    payload = build_full_draft_payload()
    del payload['pages'][0]['questions'][0]['options'][0]['score']
    document = QuestionnaireDraftSaveModel.model_validate(payload)
    assert document.pages[0].questions[0].options[0].score == Decimal('1')
    assert get_publish_validation_issues(document) == []


def test_full_questionnaire_contract_supports_five_types_and_publish_readiness() -> None:
    draft = QuestionnaireDraftSaveModel.model_validate(build_full_draft_payload())

    questions = [question for page in draft.pages for question in page.questions]
    assert [question.question_type for question in questions] == [
        'SINGLE_CHOICE',
        'STAR_RATING',
        'NUMERIC_INPUT',
        'SLIDER',
        'TEXT',
    ]
    assert draft.description == '评价说明\n请根据实际表现完成评价。'
    assert questions[2].config.default_value == Decimal('80.00')
    assert questions[3].config.step == Decimal('0.5')
    assert calculate_question_max_score(questions[0]) == Decimal('5.0000')
    assert calculate_question_max_score(questions[4]) == Decimal('0')
    assert get_publish_validation_issues(draft) == []


def test_incomplete_draft_can_be_parsed_but_returns_stable_publish_issues() -> None:
    payload = build_full_draft_payload()
    payload['indicators'] = []

    draft = QuestionnaireDraftSaveModel.model_validate(payload)
    issues = get_publish_validation_issues(draft)

    assert {item['code'] for item in issues} == {
        'INDICATOR_WEIGHT_TOTAL_INVALID',
        'SCORED_QUESTION_INDICATOR_REQUIRED',
    }
    assert (
        sum(item['code'] == 'SCORED_QUESTION_INDICATOR_REQUIRED' for item in issues) == EXPECTED_SCORED_QUESTION_COUNT
    )


@pytest.mark.parametrize(
    ('mutator', 'message'),
    [
        (
            lambda payload: payload['pages'][0]['questions'][1].update(maxScore='10'),
            '星级评分可选星数必须在2至10之间',
        ),
        (
            lambda payload: payload['pages'][0]['questions'][2]['config'].update(defaultValue='80.123'),
            '默认值精度不能超过允许小数位数',
        ),
        (
            lambda payload: payload['pages'][1]['questions'][0]['config'].update(defaultValue='5.1'),
            '默认值必须落在合法步长上',
        ),
        (
            lambda payload: payload['pages'][1]['questions'][1].update(isScored=True),
            'Input should be False',
        ),
        (
            lambda payload: payload['pages'][0]['questions'][1].update(
                options=[
                    {
                        'optionCode': 'O_BAD',
                        'optionLabel': '非法伪选项',
                        'score': '1.0000',
                        'sortOrder': 1,
                    }
                ]
            ),
            'at most 0 items',
        ),
        (
            lambda payload: payload['indicators'][1]['questionCodes'].append('Q_SINGLE'),
            '一道题最多绑定一个指标',
        ),
        (
            lambda payload: payload['indicators'][0]['questionCodes'].append('Q_UNKNOWN'),
            '绑定了不存在的题目',
        ),
        (
            lambda payload: payload['pages'][1].update(sortOrder=3),
            '页面顺序必须从1开始连续排列',
        ),
    ],
)
def test_full_questionnaire_contract_rejects_invalid_structure(
    mutator: Callable[[dict], object],
    message: str,
) -> None:
    payload = deepcopy(build_full_draft_payload())
    mutator(payload)

    with pytest.raises(ValidationError) as exc_info:
        QuestionnaireDraftSaveModel.model_validate(payload)

    assert message in str(exc_info.value)


def test_rich_text_rejects_link_mark_and_unknown_node() -> None:
    link_payload = build_full_draft_payload()
    link_payload['descriptionDoc']['content'][1]['content'][0]['marks'] = [{'type': 'link'}]
    with pytest.raises(ValidationError, match='未允许mark'):
        QuestionnaireDraftSaveModel.model_validate(link_payload)

    node_payload = build_full_draft_payload()
    node_payload['descriptionDoc']['content'].append({'type': 'image', 'attrs': {'src': 'x'}})
    with pytest.raises(ValidationError, match='未允许节点'):
        QuestionnaireDraftSaveModel.model_validate(node_payload)


def test_question_type_config_rejects_unknown_fields() -> None:
    payload = build_full_draft_payload()
    payload['pages'][0]['questions'][2]['config']['formula'] = 'unsafe'

    with pytest.raises(ValidationError, match='Extra inputs are not permitted'):
        QuestionnaireDraftSaveModel.model_validate(payload)


def test_zero_weight_indicator_requires_scored_question() -> None:
    payload = build_full_draft_payload()
    payload['indicators'].append({
        'indicatorCode': 'I_EMPTY', 'indicatorName': '待绑定指标',
        'weight': '0.0000', 'sortOrder': len(payload['indicators']) + 1, 'questionCodes': [],
    })
    draft = QuestionnaireDraftSaveModel.model_validate(payload)
    issues = get_publish_validation_issues(draft)
    assert any(issue['code'] == 'INDICATOR_SCORED_QUESTION_REQUIRED' and '待绑定指标' in issue['message'] for issue in issues)

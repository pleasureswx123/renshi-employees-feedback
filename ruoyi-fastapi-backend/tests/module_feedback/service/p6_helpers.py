import uuid
from typing import Any

from sqlalchemy import delete, select, true

from module_feedback.entity.do import FbAnswer, FbAnswerSheet, FbProjectCompletionAudit
from module_feedback.entity.vo import PublicationConfigSaveModel, PublishRequestModel, QuestionnaireDraftSaveModel
from module_feedback.entity.vo.employee_vo import AnswerDraftSaveModel, AnswerSubmitModel
from module_feedback.service import FeedbackPublicationService, FeedbackQuestionnaireService
from module_feedback.service.employee_service import FeedbackEmployeeService
from tests.module_feedback.service.test_p5_publication_flow_postgresql import cleanup_project, create_ready_project


def questionnaire(version_id: int, lock_version: int) -> QuestionnaireDraftSaveModel:
    common = {'isRequired': True, 'isScored': True, 'options': []}
    questions = [
        {
            **common,
            'questionCode': 'Q_OPTION',
            'questionType': 'SINGLE_CHOICE',
            'title': '协作评价',
            'sortOrder': 1,
            'config': {},
            'options': [
                {'optionCode': 'O_GOOD', 'optionLabel': '很好', 'score': '3', 'requiresReason': True, 'sortOrder': 1},
                {'optionCode': 'O_OTHER', 'optionLabel': '一般', 'score': '0', 'requiresReason': False, 'sortOrder': 2},
            ],
        },
        {
            **common,
            'questionCode': 'Q_STAR',
            'questionType': 'STAR_RATING',
            'title': '主动性',
            'sortOrder': 2,
            'minScore': '0',
            'maxScore': '5',
            'decimalPlaces': 0,
            'config': {},
        },
        {
            **common,
            'questionCode': 'Q_NUMBER',
            'questionType': 'NUMERIC_INPUT',
            'title': '质量评分',
            'sortOrder': 1,
            'minScore': '0',
            'maxScore': '100',
            'decimalPlaces': 2,
            'config': {'defaultValue': '20'},
        },
        {
            **common,
            'questionCode': 'Q_SLIDER',
            'questionType': 'SLIDER',
            'title': '沟通评分',
            'sortOrder': 2,
            'minScore': '0',
            'maxScore': '10',
            'decimalPlaces': 1,
            'config': {'step': '0.5', 'defaultValue': '5'},
        },
        {
            **common,
            'questionCode': 'Q_TEXT',
            'questionType': 'TEXT',
            'title': '建议',
            'sortOrder': 3,
            'isScored': False,
            'config': {'maxLength': 100},
        },
    ]
    return QuestionnaireDraftSaveModel(
        versionId=version_id,
        lockVersion=lock_version,
        title='P6五题型问卷',
        pages=[
            {'pageCode': 'P_ONE', 'pageTitle': '协作表现', 'sortOrder': 1, 'questions': questions[:2]},
            {'pageCode': 'P_TWO', 'pageTitle': '质量与建议', 'sortOrder': 2, 'questions': questions[2:]},
        ],
        indicators=[
            {
                'indicatorCode': 'I_ALL',
                'indicatorName': '综合表现',
                'weight': '100',
                'sortOrder': 1,
                'questionCodes': [question['questionCode'] for question in questions],
            }
        ],
    )


async def create_p6_project(
    factory: Any, *, extra_relation: bool = False, publish: bool = True, long_text: bool = False
) -> dict:
    state = await create_ready_project(factory, uuid.uuid4().hex[:12])
    try:
        async with factory() as db:
            project_id = state['project_id']
            draft = await FeedbackQuestionnaireService.get_draft(db, project_id, true())
            document = questionnaire(draft.version_id, draft.lock_version)
            if long_text:
                document.pages[1].questions[0].title = '质量评分：' + '跨部门复杂任务的质量与交付稳定性，' * 12
                document.pages[0].questions[0].options[
                    0
                ].option_label = '很好：在跨部门协作与复杂交付中持续主动提供帮助'
            await FeedbackQuestionnaireService.save_draft(db, project_id, document, 'p6-test', true())
            config = await FeedbackPublicationService.get_config(db, project_id, true())
            targets = [state['user_ids'][0], state['user_ids'][2]]
            evaluator = state['user_ids'][1]
            relations = []
            for relation in config.relations:
                item = relation.model_dump(by_alias=True, mode='json')
                item = {
                    key: item[key]
                    for key in (
                        'relationCode',
                        'relationType',
                        'relationName',
                        'isEnabled',
                        'participatesInScore',
                        'weight',
                        'sortOrder',
                    )
                }
                if item['relationCode'] == 'REL_PEER':
                    item.update(isEnabled=True, participatesInScore=True, weight='50' if extra_relation else '100')
                if item['relationCode'] == 'REL_SUPERVISOR' and extra_relation:
                    item.update(isEnabled=True, participatesInScore=True, weight='50')
                relations.append(item)
            selections = [
                {'targetUserId': target, 'relationCode': 'REL_PEER', 'evaluatorUserIds': [evaluator]}
                for target in targets
            ]
            if extra_relation:
                selections.append(
                    {'targetUserId': targets[0], 'relationCode': 'REL_SUPERVISOR', 'evaluatorUserIds': [evaluator]}
                )
            config = await FeedbackPublicationService.save_config(
                db,
                project_id,
                PublicationConfigSaveModel(
                    projectLockVersion=config.project_lock_version,
                    versionId=config.version_id,
                    versionLockVersion=config.version_lock_version,
                    targets=[{'targetUserId': target} for target in targets],
                    relations=relations,
                    evaluatorSelections=selections,
                ),
                'p6-test',
                true(),
                true(),
            )
            state['evaluator_id'] = evaluator
            if not publish:
                return state
            await FeedbackPublicationService.publish(
                db,
                project_id,
                PublishRequestModel(
                    projectLockVersion=config.project_lock_version,
                    versionId=config.version_id,
                    versionLockVersion=config.version_lock_version,
                ),
                state['user_ids'][0],
                'p6-test',
                true(),
                true(),
            )
            project = await FeedbackEmployeeService.get_project(db, project_id, evaluator)
            state.update(evaluator_id=evaluator, task_ids=[task.assignment_id for task in project.tasks])
        return state
    except Exception:
        await cleanup_p6_project(factory, state)
        raise


async def cleanup_p6_project(factory: Any, state: dict) -> None:
    async with factory() as db:
        await db.execute(
            delete(FbProjectCompletionAudit).where(FbProjectCompletionAudit.project_id == state['project_id'])
        )
        sheets = select(FbAnswerSheet.sheet_id).where(FbAnswerSheet.project_id == state['project_id'])
        await db.execute(delete(FbAnswer).where(FbAnswer.sheet_id.in_(sheets)))
        await db.execute(delete(FbAnswerSheet).where(FbAnswerSheet.project_id == state['project_id']))
        await db.commit()
    await cleanup_project(factory, state)


def answer_request(detail: Any, *, submit: bool = False, complete: bool = True, **overrides) -> Any:
    questions = [question for page in detail.questionnaire.pages for question in page.questions]
    values = [
        {'questionId': questions[0].question_id, 'optionId': questions[0].options[0].option_id, 'reason': '配合主动'},
        {'questionId': questions[1].question_id, 'numericValue': '4'},
        {'questionId': questions[2].question_id, 'numericValue': '42.25'},
        {'questionId': questions[3].question_id, 'numericValue': '4.5'},
        {'questionId': questions[4].question_id, 'textValue': '继续保持'},
    ]
    payload = {
        'versionId': detail.task.version_id,
        'lockVersion': detail.lock_version,
        'lastPageId': detail.questionnaire.pages[-1].page_id,
        'answers': values if complete else values[:1],
        **overrides,
    }
    if submit:
        payload.setdefault('submissionId', str(uuid.uuid4()))
        return AnswerSubmitModel.model_validate(payload)
    return AnswerDraftSaveModel.model_validate(payload)

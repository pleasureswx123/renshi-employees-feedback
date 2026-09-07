"""随系统发布的版本化问卷模板；创建时复制，后续修改不影响模板或其他项目。"""

from uuid import uuid4

from exceptions.exception import ServiceException
from module_feedback.entity.vo.questionnaire_vo import QuestionnaireDraftSaveModel

TEMPLATES = [
    {
        'templateKey': 'employee-360-v1',
        'name': '员工综合评价',
        'description': '适用于员工日常工作表现评价。五个指标等权重，10道行为评价题及1道可选建议题。',
        'dimensions': [
            ('团队合作', ['能够及时共享工作信息，配合团队完成任务。', '能够尊重不同意见，并主动协助同事解决问题。']),
            ('沟通协调', ['能够清晰表达工作进展、问题与需求。', '遇到跨部门事项时能够主动协调并及时反馈。']),
            ('工作效率', ['能够合理安排优先级，按约定时间交付任务。', '能够主动优化工作方法，减少重复和无效工作。']),
            ('专业能力', ['具备岗位所需的知识和技能，交付符合质量要求。', '能够分析工作问题并提出可执行的解决方案。']),
            ('积极性', ['能够主动承担职责并持续跟进工作结果。', '愿意接受反馈并持续学习、改进。']),
        ],
    },
    {
        'templateKey': 'manager-360-v1',
        'name': '管理者评价',
        'description': '适用于管理岗位反馈。四个指标等权重，8道行为评价题及1道可选建议题。',
        'dimensions': [
            ('目标管理', ['能够将团队目标分解为清晰、可执行的任务。', '能够跟踪目标进展，及时识别风险并调整行动。']),
            ('团队领导', ['能够明确职责分工，为团队提供必要支持。', '能够通过辅导和反馈帮助成员成长。']),
            ('协同决策', ['能够听取不同意见，并依据事实做出决策。', '能够协调资源，推动跨团队问题解决。']),
            ('责任担当', ['面对困难能够承担责任并推动落实。', '能够以身作则，公平一致地执行团队规则。']),
        ],
    },
]
SCALE = ['很少体现', '偶尔体现', '基本体现', '经常体现', '持续体现']


def list_system_templates() -> list[dict]:
    return [
        {
            'templateKey': item['templateKey'],
            'name': item['name'],
            'description': item['description'],
            'scale': SCALE.copy(),
            'indicators': [
                {'name': name, 'weight': 100 // len(item['dimensions']), 'questions': list(questions)}
                for name, questions in item['dimensions']
            ],
        }
        for item in TEMPLATES
    ]


def build_template(key: str, version_id: int, title: str) -> QuestionnaireDraftSaveModel:
    template = next((item for item in TEMPLATES if item['templateKey'] == key), None)
    if template is None:
        raise ServiceException(message='系统模板不存在，请刷新后重新选择')
    pages, indicators = [], []
    for index, (name, titles) in enumerate(template['dimensions'], 1):
        questions = []
        for order, question_title in enumerate(titles, 1):
            questions.append(
                {
                    'questionCode': f'Q_{uuid4().hex}',
                    'questionType': 'SINGLE_CHOICE',
                    'title': question_title,
                    'isRequired': True,
                    'isScored': True,
                    'sortOrder': order,
                    'options': [
                        {'optionCode': f'O_{uuid4().hex}', 'optionLabel': label, 'score': score, 'sortOrder': score}
                        for score, label in enumerate(SCALE, 1)
                    ],
                }
            )
        pages.append({'pageCode': f'P_{uuid4().hex}', 'pageTitle': name, 'sortOrder': index, 'questions': questions})
        indicators.append(
            {
                'indicatorCode': f'I_{uuid4().hex}',
                'indicatorName': name,
                'weight': 100 // len(template['dimensions']),
                'sortOrder': index,
                'questionCodes': [q['questionCode'] for q in questions],
            }
        )
    pages.append(
        {
            'pageCode': f'P_{uuid4().hex}',
            'pageTitle': '补充建议',
            'sortOrder': len(pages) + 1,
            'questions': [
                {
                    'questionCode': f'Q_{uuid4().hex}',
                    'questionType': 'TEXT',
                    'title': '请描述值得肯定的表现，以及建议改进的具体事项。',
                    'isRequired': False,
                    'isScored': False,
                    'sortOrder': 1,
                    'config': {'maxLength': 1000},
                }
            ],
        }
    )
    return QuestionnaireDraftSaveModel(
        versionId=version_id,
        lockVersion=0,
        title=title,
        description='请基于实际观察作答：1分很少体现，2分偶尔体现，3分基本体现，4分经常体现，5分持续体现。',
        pages=pages,
        indicators=indicators,
    )

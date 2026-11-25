"""OpenAPI descriptions only; runtime input handling stays in api.py."""
from copy import deepcopy
from fastapi.openapi.utils import get_openapi


def obj(properties, required=()):
    schema = dict(type='object', properties=properties, additionalProperties=True)
    if required:
        schema['required'] = list(required)
    return schema


FILE = dict(type='string', description='先调用 /api/bootstrap 查看 samples / imported 中的 id。', examples=['sample-0'])
CONDITION = dict(type='integer', minimum=0, default=0, description='工况索引，从 0 开始；通过 /api/open 查询。')
CHANNEL = dict(type='integer', minimum=0, default=0, description='通道索引，从 0 开始；通过 /api/open 查询。')
FILTER = obj({
    'type': dict(type='string', enum=['lowpass', 'highpass', 'bandpass', 'bandstop']),
    'order': dict(type='integer', minimum=1, maximum=100, default=5),
    'low': dict(type='number', exclusiveMinimum=0, description='低通截止频率或带通/带阻下限，Hz。'),
    'high': dict(type='number', exclusiveMinimum=0, description='高通截止频率或带通/带阻上限，Hz。'),
}, ['type', 'order'])
COMMON = {
    'file_id': FILE, 'condition': CONDITION, 'channel': CHANNEL,
    'start': dict(type='number', minimum=0, default=0, description='请求开始时刻，秒。'),
    'end': dict(type=['number', 'null'], description='请求结束时刻，秒；null 表示全部。'),
    'window': dict(type='string', enum=['rectangular', 'hann'], default='rectangular'),
    'confidence': dict(type='integer', enum=[95, 97, 100], default=97),
    'full_period': dict(type='boolean', description='有有效键相时默认取整周期；无有效键相时请省略或传 false。'),
    'remove_mean': dict(type='boolean', default=False, description='FFT 前是否去均值。'),
    'filters': dict(type='array', items=FILTER, default=[]),
    'include_original': dict(type='boolean', default=False),
    'title': dict(type='string', minLength=1, maxLength=200),
    'main_color': dict(type='string', examples=['#0000ff']),
}
BASE_EXAMPLE = dict(file_id='sample-0', condition=0, channel=0, start=0,
                    end=None, window='rectangular', confidence=97, remove_mean=False, filters=[])
TREND = obj({
    'id': dict(type='string', pattern='^[A-Za-z0-9_-]{1,64}$'),
    'metric': dict(type='string', enum=['mean', 'median', 'effective', 'peak_to_peak']),
    'width': dict(type='integer', minimum=1, description='窗口宽度，采样点。'),
    'step': dict(type='integer', minimum=1, description='窗口步长，采样点。'),
    'tail': dict(type='string', enum=['desktop_strict', 'complete'], default='desktop_strict'),
    'effective_mode': dict(type='string', enum=['desktop', 'window_ac'], default='desktop'),
    'color': dict(type='string', default='#ff00ff'), 'visible': dict(type='boolean', default=True),
}, ['id'])


def document_schema(app):
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
    schema.setdefault('components', {}).setdefault('securitySchemes', {})['HSJSession'] = {
        'type': 'apiKey', 'in': 'header', 'name': 'X-HSJ-Token',
        'description': '文档页面自动读取当前本机会话。服务重启后点击“刷新本机会话”；也可手动填写 /api/bootstrap 返回的 token。',
    }
    details = {
        '/api/export-file-list':('导出','列出批量结果文件','type=wave或special，id为已完成任务ID。'),
        '/api/export-file':('导出','读取批量结果中的单个文件','按任务和index读取结果，不在服务器解包外部路径。'),
        '/api/shutdown':('服务','退出本机分析服务','取消后台任务并停止本机服务。执行后需用启动脚本重新启动。'),
        '/api/special-legacy': ('专项分析','保存原版OCA/OAG结果','使用专项结果中的legacy_text和legacy_extension输出GB18030格式文件。'),
        '/api/special-batch': ('专项分析','创建专项后台批量任务','选择通道项目、报表或五种格式图像，支持CON和整周期参数。'),
        '/api/special-batch-status': ('专项分析','查询专项批量进度','读取任务ID对应的进度、当前项目及错误。'),
        '/api/special-batch-cancel': ('专项分析','取消专项批量任务','取消后不提供部分结果下载。'),
        '/api/special-batch-download': ('专项分析','下载专项批量ZIP','已完成任务提供图像、报表、清单及错误记录。'),
        '/api/special': ('专项分析', '轴心 / 相关 / 趋势 / 动平衡 / 盘车 / 效率 / 协联 / 圆度', 'module 指定专项模块；参数与页面所选模块对应。'),
        '/api/special-report': ('专项分析', '导出专项 Word / Excel', '通过 source_request 在服务端读取原数据生成报表，或传入结果；format 支持 docx、xlsx，以及需本机Office的doc、xls。'),
        '/api/waterfall-data': ('三维瀑布图', '读取三维波形或频谱瀑布数据', '按同一试验类型的全部工况，使用参考通道均值作 X 坐标，沿用原三维模块 FFT 规则。'),
        '/api/health': ('服务', '查看服务状态', '返回当前后端版本和框架。'),
        '/api/bootstrap': ('文件', '读取会话和文件列表', '返回 token，以及 samples / imported 文件 ID。仅读取列表，不执行分析。'),
        '/api/coverage': ('服务', '查看功能迁移清单', '读取原版功能迁移台账，不修改验收状态。'),
        '/api/open': ('文件', '读取文件与工况通道信息', '返回文件元数据、工况和通道列表。'),
        '/api/upload': ('文件', '导入 SEL 文件', '选择原始 SEL 文件，以二进制上传，最大 256 MB。'),
        '/api/chd-upload': ('文件', '导入 CHD 文件', '二进制上传 CHD；需要在请求头填写采样率、标题和单位。'),
        '/api/analyze': ('分析', '计算波形、频谱和统计', '默认 97% 峰峰值、矩形窗、不在 FFT 前去均值。有键相时默认整周期。返回捡取所需的 analysis_id。'),
        '/api/chart': ('分析', '读取图表采样点或细节', 'analysis_id 来自分析或长图结果，服务重启后需重新分析。'),
        '/api/overlays': ('分析', '读取叠加通道', 'actual_start / actual_end 使用主通道分析结果中的实际时段。'),
        '/api/trends': ('分析', '计算移动趋势', '窗口宽度和步长单位为采样点。'),
        '/api/trend-export': ('导出', '导出一条移动趋势 CSV', 'trends 必须只包含一条趋势配置。'),
        '/api/throwload': ('分析', '计算甩负荷趋势与标注', 'base / final 为秒，须满足窗口及通道时长约束。'),
        '/api/strip-data': ('长图', '读取长图原始通道', '读取原始数据，不附加波形页面的滤波。'),
        '/api/export': ('导出', '导出分析 JSON 或 CSV', '返回可下载文件，kind 指定 json / waveform / spectrum。'),
        '/api/report': ('导出', '生成 Word 或 Excel 报表', 'format 为 docx 或 xlsx。'),
        '/api/image': ('导出', '生成分析图像', '返回图像文件。'),
        '/api/image-convert': ('导出', '转换已有图像', 'image 是 PNG 的 data URL，参照波形页图像转换流程。'),
        '/api/legacy-data': ('导出', '导出原版数据格式', '支持当前时段、完整通道及谱峰 CHD 数据。'),
        '/api/batch': ('批量任务', '创建批量导出任务', '执行后会生成后台任务和输出文件；通过任务 ID 查询或取消。'),
        '/api/batch-status': ('批量任务', '查询批量任务进度', 'id 来自 /api/batch 返回值。'),
        '/api/batch-cancel': ('批量任务', '取消批量导出任务', '请求取消尚未完成的任务。'),
        '/api/batch-download': ('批量任务', '下载批量结果 ZIP', '任务完成后可下载；服务重启后内存中的任务记录失效。'),
    }
    for path, operations in schema['paths'].items():
        for method, operation in operations.items():
            if method not in ('get', 'post'):
                continue
            tag, summary, description = details[path]
            operation.update(tags=[tag], summary=summary, description=description)
            if method != 'post':
                continue
            operation['security'] = [{'HSJSession': []}]
            download_types = {
                '/api/export-file':['application/octet-stream'],
                '/api/special-legacy':['application/octet-stream'],
                '/api/special-batch-download':['application/zip'],
                '/api/special-report':['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','application/vnd.openxmlformats-officedocument.wordprocessingml.document','application/vnd.ms-excel','application/msword'],
                '/api/export': ['application/json', 'text/csv'],
                '/api/trend-export': ['text/csv'],
                '/api/legacy-data': ['application/octet-stream'],
                '/api/batch-download': ['application/zip'],
                '/api/report': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
                '/api/image': ['image/png', 'image/jpeg', 'image/bmp', 'image/gif', 'image/tiff'],
                '/api/image-convert': ['image/png', 'image/jpeg', 'image/bmp', 'image/gif', 'image/tiff'],
            }
            if path in download_types:
                operation['responses']['200'] = {'description': '下载结果文件', 'content': {
                    mime: {'schema': {'type': 'string', 'format': 'binary'}} for mime in download_types[path]}}
            for code, text in [('400', '参数或文件格式无效'), ('403', '会话、访问地址或来源无效'),
                               ('409', '已有分析任务执行中'), ('413', '请求为空或超过大小限制')]:
                operation.setdefault('responses', {})[code] = {'description': text, 'content': {
                    'application/json': {'schema': obj({'error': {'type': 'string'}}, ['error'])}}}
            if path in ('/api/upload', '/api/chd-upload'):
                params = [dict(name='X-Filename', location='header', description='原始文件名；中文会由文档页面自动进行 URL 编码。', default='data.chd' if 'chd' in path else 'data.sel')]
                if path == '/api/chd-upload':
                    params += [dict(name='X-Sample-Rate', location='header', description='采样率，Hz。', default='1024'),
                               dict(name='X-Title', location='header', description='通道标题。', default='CHD'),
                               dict(name='X-Unit', location='header', description='通道单位。', default='um'),
                               dict(name='X-Color', location='header', description='通道颜色。', default='#0000ff')]
                operation['parameters'] = [dict(name=p['name'], **{'in': p['location']}, required=p['name']=='X-Sample-Rate', description=p['description'], schema={'type': 'string', 'default': p['default']}) for p in params]
                continue
            properties, required, example = deepcopy(COMMON), ['file_id'], deepcopy(BASE_EXAMPLE)
            if path in ('/api/export-file-list','/api/export-file'):
                properties={'type':{'type':'string','enum':['wave','special']},'id':{'type':'string'},'index':{'type':'integer','minimum':0}};required=['type','id']+(['index'] if path=='/api/export-file' else []);example={'type':'wave','id':'替换为已完成任务ID','index':0}
            elif path=='/api/shutdown':
                properties={};required=[];example={}
            elif path=='/api/special-legacy':
                properties={'legacy_extension':{'type':'string','enum':['oca','oag']},'legacy_text':{'type':'string'}};required=['legacy_extension','legacy_text'];example={'legacy_extension':'oca','legacy_text':'1.000000\t0.900000\r\n'}
            elif path.startswith('/api/special-batch-'):
                properties={'id':{'type':'string'}};required=['id'];example={'id':'替换为专项批量任务ID'}
            elif path=='/api/special-batch':
                properties={'parameters':{'type':'object','additionalProperties':True},'items':{'type':'array','items':{'type':'object','additionalProperties':True}},'output':{'type':'string','enum':['images','xlsx','docx','data']},'format':{'type':'string','enum':['png','bmp','jpg','gif','tiff']}}
                required=['parameters','items','output'];example={'parameters':{'module':'trend','file_id':'sample-0','exam_type':'变负荷','reference':13},'items':[{'channel':0}],'output':'images','format':'png'}
            elif path == '/api/special':
                properties={'module':{'type':'string','enum':['orbit','correlation','trend','balance','balance_sample','balance_decompose','jigger','efficiency','cam','airgap']},'file_id':FILE,'condition':CONDITION,'x_channel':CHANNEL,'y_channel':CHANNEL}
                required=['module'];example={'module':'orbit','file_id':'sample-0','condition':0,'x_channel':0,'y_channel':1}
            elif path == '/api/special-report':
                properties={'source_request':{'type':'object','additionalProperties':True},'format':{'type':'string','enum':['xlsx','docx','xls','doc']},'include_graphs':{'type':'boolean','default':True},'columns':{'type':'array','items':{'type':'string'}},'rows':{'type':'array','items':{'type':'array','items':{}}}}
                required=[];example={'columns':['项目','数值'],'rows':[['结果',1]]}
            elif path == '/api/waterfall-data':
                properties={'file_id':FILE,'channel':CHANNEL,'reference':CHANNEL,'exam_type':{'type':'string'},'mode':{'type':'string','enum':['spectrum','wave']}}
                example={'file_id':'sample-0','channel':0,'reference':13,'mode':'spectrum'}
            elif path == '/api/open':
                properties, example = {'file_id': FILE}, {'file_id': 'sample-0'}
            elif path == '/api/chart':
                properties = {'analysis_id': dict(type='string', description='使用分析结果中真实的 analysis_id。'),
                              'plot': dict(type='string', enum=['wave', 'spectrum']),
                              'action': dict(type='string', enum=['nearest', 'detail', 'extrema', 'index'], default='nearest'),
                              'x': dict(type='number'), 'index': dict(type='integer', minimum=0),
                              'x_min': dict(type='number'), 'x_max': dict(type='number')}
                required, example = ['analysis_id', 'plot'], dict(analysis_id='替换为分析结果中的 analysis_id', plot='wave', action='nearest', x=1)
            elif path.startswith('/api/batch-'):
                properties, required, example = {'id': {'type': 'string'}}, ['id'], {'id': '替换为批量任务 id'}
            elif path == '/api/batch':
                properties.update(items=dict(type='array', minItems=1, items=obj({'condition': CONDITION, 'channel': CHANNEL}, ['condition', 'channel'])),
                                  output=dict(type='string', enum=['images', 'data', 'excel', 'word'], default='images'))
                required += ['items']; example.update(output='images', items=[{'condition': 0, 'channel': 0}])
            elif path == '/api/strip-data':
                properties = {'file_id': FILE, 'condition': CONDITION,
                              'channels': dict(type='array', minItems=1, items=CHANNEL),
                              'start': COMMON['start'], 'end': dict(type='number', exclusiveMinimum=0),
                              'width': dict(type='integer', minimum=300, maximum=22500, default=2000)}
                required += ['channels', 'end']; example = dict(file_id='sample-0', condition=0, channels=[0], start=0, end=5, width=2000)
            elif path == '/api/overlays':
                properties.update(actual_start=dict(type='number'), actual_end=dict(type='number'), overlays=dict(type='array', items={'type': 'object', 'additionalProperties': True}))
                required += ['actual_start', 'actual_end']; example.update(actual_start=0, actual_end=5, overlays=[])
            elif path in ('/api/trends', '/api/trend-export'):
                properties['trends'] = dict(type='array', items=TREND)
                example['trends'] = [dict(id='mean-1', metric='mean', width=10, step=10, tail='complete')]
            elif path == '/api/throwload':
                properties.update(width=dict(type='integer', minimum=1, maximum=10000, default=50), base=dict(type='number'), final=dict(type='number'), rising=dict(type='boolean', default=True))
                required += ['base', 'final']; example.update(width=50, base=1, final=5, rising=True)
            elif path == '/api/export':
                properties['kind'] = dict(type='string', enum=['json', 'waveform', 'spectrum'], default='json'); example['kind']='json'
            elif path == '/api/report':
                properties['format'] = dict(type='string', enum=['docx', 'xlsx', 'doc', 'xls'], default='docx'); example['format']='docx'
            elif path == '/api/image':
                properties['format'] = dict(type='string', enum=['png', 'jpg', 'bmp', 'gif', 'tiff'], default='png'); example['format']='png'
            elif path == '/api/legacy-data':
                properties['kind'] = dict(type='string', enum=['current', 'full', 'peaks'], default='current'); example['kind']='current'
            elif path == '/api/image-convert':
                properties = {'image': dict(type='string', description='PNG data URL，包含 data:image/png;base64, 前缀。'), 'format': dict(type='string', enum=['png', 'jpg', 'bmp', 'gif', 'tiff'])}
                required, example = ['image', 'format'], dict(image='data:image/png;base64,替换为实际图像数据', format='jpg')
            operation['requestBody'] = {'required': True, 'content': {'application/json': {
                'schema': obj(properties, required), 'example': example}}}
    app.openapi_schema = schema
    return schema

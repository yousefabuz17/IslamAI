
from .ai_blueprint import *

quran_bp = Blueprint('quran_blueprint', __name__, url_prefix=api_endpoint)
quran_api = Api(quran_bp, prefix='/quran')

quran_file = all_files['list_of_surahs']
quran_stats = all_files['quran_stats']

surah_ids = {str(values['id']): values['surah_name'] for _, (_keys, values) in enumerate(quran_file.items(), start=1)}
surah_authors = list(nested('verses', quran_file['1'])[0].keys())

quran_index = {
                'message': 'Redirect to `/api/quran/index` endpoint for more reference',
                'status': 302,
                'location': '/api/quran/index',
                'quran-endpoints': [
                                    '/index',
                                    '/stats',
                                    '/search?surah_id=None&author=None',
                                    '/translate?surah_id=None&lang=None'
                                    ]
            }, 302

class QuranIndex(Resource):
    def get(self):
        return {
                'message': 'Quran Index Page',
                'status': '200',
                'all-endpoints': '',
                'author-translators': surah_authors,
                'languages': {
                            'Arabic': 'ar',
                            'English': 'en',
                            'Transliteration': 'trans'
                            },
                'surah-id': surah_ids
                }
class SurahRequestSchema(Schema):
    surah_id = fields.Int(required=False)
    author = fields.Str(required=False)
    lang = fields.Str(requires=False)

class SurahContentsResource(Resource):
    @use_args(SurahRequestSchema(), location="query")
    def get(self, args):
        
        surah_id = str(args.get('surah_id'))
        author = args.get('author')
        
        if args is None:
            return quran_index
        try:
            if surah_id not in surah_ids.keys():
                return quran_index
            
            surah_content = quran_file.get(surah_id)
            if not author:
                return surah_content
            else:
                author = process.extractOne(author, choices=surah_authors, scorer=fuzz.ratio)[0]
                author_contents = nested('verses', surah_content)[0].get(author)
                if author_contents:
                    return {author: author_contents}
                else:
                    return {'message': 'Invalid author name. Check quran index for more reference'}
        except ValueError:
            abort(400, message="Invalid paramters")

class SurahLangResource(Resource):
    @use_args(SurahRequestSchema(), location="query")
    def get(self, args):
        #** Available at the moment for only Sahih International
        #^ 'ar', 'en', 'trans'
        surah_id = str(args.get('surah_id'))
        lang = args.get('lang')
        
        def grabber(key):
            return nested(key, nested('Sahih International', surah_content)[0])[:]
        
        if args is None:
            return quran_index
        try:
            surah_content = quran_file.get(surah_id)
            match lang:
                case 'ar':
                    return grabber('translation_ar')
                case 'en':
                    return grabber('translation_eng')
                case 'trans':
                    return grabber('transliteration')
        except ValueError:
            abort(400, message="Invalid paramters")

class QuranStatsResource(Resource):
    def get(self):
        return quran_stats

class CustomJSONEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        super(CustomJSONEncoder, self).__init__(*args, **kwargs)
    #!> Needs fixing. Content still is ascii
    def default(self, o):
        if isinstance(o, str):
            return o.encode('utf-8').decode('unicode_escape')
        elif isinstance(o, dict):
            return {key: self.default(value) for key, value in o.items()}
        elif isinstance(o, list):
            return [self.default(item) for item in o]
        return super(CustomJSONEncoder, self).default(o)

quran_api.json_encoder = CustomJSONEncoder

quran_api.add_resource(QuranIndex, '/index')
quran_api.add_resource(SurahContentsResource, '/search')
quran_api.add_resource(QuranStatsResource, '/stats')
quran_api.add_resource(SurahLangResource, '/translate')
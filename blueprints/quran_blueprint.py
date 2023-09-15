
from .ai_blueprint import *

quran_bp = Blueprint('quran_blueprint', __name__, url_prefix=api_endpoint)
quran_api = Api(quran_bp, prefix='/quran')

quran_file = all_files['list_of_surahs']
quran_stats = all_files['quran_stats']

surahIDs = {str(values['id']): values['surah_name'] for _, (_keys, values) in enumerate(quran_file.items(), start=1)}
surah_authors = list(nested('verses', quran_file['1'])[0].keys())

quran_index = {
                'message': 'Redirect to `/index` endpoint for more reference',
                'status': 302,
                'location': '/api/quran/index'
            }, 302

class QuranIndex(Resource):
    def get(self):
        return {
                'message': 'Quran API Reference Page',
                'status': 200,
                'api_endpoint': '/api/quran',
                'quran-endpoints': [
                                    '/index',
                                    '/stats',
                                    '/search?surahID=None&author=None',
                                    '/translate?surahID=None&lang=None',
                                    '/keyword'
                                    ],
                'author-translators': surah_authors,
                'supported_languages': {
                            'Arabic': 'ar',
                            'English': 'en',
                            'Transliteration': 'translit'
                            },
                'surah-ids': surahIDs
                }

class SurahRequestSchema(Schema):
    surahID = fields.Int(required=False)
    author = fields.Str(required=False)
    lang = fields.Str(requires=False)

class SurahContentsResource(Resource):
    @use_args(SurahRequestSchema(), location="query")
    def get(self, args):
        
        surahID = str(args.get('surahID'))
        author = args.get('author')
        
        if args is None:
            return quran_index
        try:
            if surahID not in surahIDs.keys():
                return quran_index
            
            surah_content = quran_file.get(surahID)
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
        #** Other authors only has translations in EN for now.
        #^ 'ar', 'en', 'trans'
        surahID = str(args.get('surahID'))
        lang = args.get('lang')
        
        if args is None:
            return quran_index
        
        def grabber(key, extractor=False):
            if not extractor:
                return {key: nested(key, surah_content)[0]}
            return {key: nested(key, nested('Sahih International', surah_content)[0])}
        
        try:
            surah_content = quran_file.get(surahID)
            match lang:
                case 'ar':
                    return grabber('full_surah_ar')
                case 'en':
                    return grabber('full_surah_en')
                case 'translit':
                    return grabber('translation_eng', extractor=True)
        except ValueError:
            abort(400, message="Invalid paramters")

class QuranStatsResource(Resource):
    def get(self):
        return quran_stats

class QuranKeywordResource(Resource):
    @use_args(SurahRequestSchema(), location="query")
    def get(self, args):
        keyword = args.get('keyword')
        total = args.get('total')

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
# quran_api.add_resource(SurahLangResource, '/keyword')

from .ai_blueprint import *

quran_bp = Blueprint('quran_blueprint', __name__, url_prefix=api_endpoint)
quran_api = Api(quran_bp, prefix='/quran')

quran_file = all_files.get('list_of_surahs')
surah_ids = {str(values['id']): values['surah_name'] for _, (_keys, values) in enumerate(quran_file.items(), start=1)}

class QuranIndex(Resource):
    def get(self):
        return {
                'message': 'Quran Index Page',
                'status': 'Quran API is working',
                'surah_id_endpoints': surah_ids
                }

class SurahResource(Resource):
    def get(self, surah_id):
        try:
            if surah_id not in surah_ids.keys():
                abort(404, message="Invalid Surah ID")
            else:
                surah_content = quran_file.get(surah_id)
                if surah_content:
                    return surah_content
                else:
                    abort(404, message="Surah content not found")
        except ValueError:
            abort(400, message="Invalid Surah ID format")

class SurahAuthorResource(Resource):
    def get(self, author):
        try:
            pass
        except:
            pass

quran_api.add_resource(QuranIndex, '/')
quran_api.add_resource(SurahResource, '/surah/<string:surah_id>')
quran_api.add_resource(SurahResource, '/surah/<string:surah_id>/<string:author>')

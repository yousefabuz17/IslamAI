
#** All App modules
from flask import (Blueprint, Flask, jsonify, redirect, render_template, url_for)
from flask_restful import Api, Resource, reqparse, abort

#** (pathlib, json, concurrent)
from .data_loader import *

main_endpoint, api_endpoint = '/ai/v1/data', '/api'
ai_bp = Blueprint('ai_blueprint', __name__, url_prefix=main_endpoint)
ai_api = Api(ai_bp)

islamic_data = {
    1: {
        "api": "Quran",
        "desc": "Quran verses/translations/keywords",
        'endpoint': '/quran'},
    2: {
        "api": "All Hadiths",
        "desc": "List of hadiths by author",
        'endpoint': '/hadiths'},
    3: {
        "api": "All Islamic Laws",
        "desc": "List of Islamic Laws",
        'endpoint': '/islamic-laws'},
    4: {
        "api": "All Prophet Stories",
        "desc": "List of Prophet Stories",
        'endpoint': '/prophet-stories'},
    5: {
        "api": "99 Names of Allah",
        "desc": "Names of Allah with meaning",
        'endpoint': '/99allah'},
    6: {
        "api": "All Islamic Terms",
        "desc": "Islamic Terms",
        'endpoint': '/islamic-terms'},
    7: {
        "api": "Qibla Directions",
        "desc": "Qibla Data",
        'endpoint': '/qibla'},
    8: {
        "api": "Islamic Timeline",
        "desc": "Timeline History",
        'endpoint': '/islamic-timeline'},
    9: {
        "api": "Books",
        "desc": "Islamic Books",
        "endpoint": "/islamic-books"}
}

# parser = reqparse.RequestParser()
# parser.add_argument('api', type=str, required=True, help='Name of the api')
# parser.add_argument('desc', type=str, required=True, help='Description for the item')
# parser.add_argument('endpoint', type=str, required=False, help='API Endpoint for the item')

class AIResource(Resource):
    def get(self):
        return islamic_data

ai_api.add_resource(AIResource, '/')

#TODO IslamAI API Endpoints
#!> Main API Endpoint (/api/v1/)
#**     - url_prefix for all = (/api/v1/)
#?      - JSON of all items with its relevant endpoint
#?      - 1: {"item": "Item", "data": "Items Data", "endpoint": <endpoint>}
#!>  Main Quran API Endpoint (/quran)
#**     - url_prefix for all quran=(/quran)
#?      - JSON of all 114 surahs
#!      Quran Verse (/<int: surah_id>)
#?          - JSON of surahs full contents
#!      Quran Translate Only (/translate/<str: language>)
#**         - url_prefix = (/<int: surah_id>/translate/<str: language>)
#**         - languages only for now: ['ar', 'en']
#?          - JSON or str of the surah in specified language
#!      Quran Authors (/authors)
#**        - url_prefix = (/authors)
#**        - url redirects to endpoint (/author/<str: authors_name>)
#?         - JSON of all author translators
#!      Quran By Author (/author/<str: authors_name>)
#?         - JSON or str of authors contents
#!  
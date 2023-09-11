import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return 'Test Run'

@app.route('/api/data', methods=['GET'])
def get_data():
    data = {"message": "API Endpoint and GitLab working successfully"}
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=int(os.environ.get('PORT', 5000)))

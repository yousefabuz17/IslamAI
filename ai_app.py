from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Test Run'

@app.route('/api/data', methods=['GET'])
def get_data():
    data = {"message": "API Endpoint and GitLab working successfully"}
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

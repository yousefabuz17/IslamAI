import os
import subprocess

from flask import Flask
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from blueprints.ai_blueprint import ai_bp
from blueprints.quran_blueprint import quran_bp

app = Flask(__name__)
app.register_blueprint(ai_bp)
app.register_blueprint(quran_bp)

@app.route('/')
def ai_index():
    return {
            'message': 'API is running',
            'status': 200
            }

class MyHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(".py"):
            print("Restarting server due to file change...")
            subprocess.run(["pkill", "-HUP", "gunicorn"])

if __name__ == '__main__':
    observer = Observer()
    observer.schedule(MyHandler(), path='.', recursive=True)
    observer.start()
    
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), use_reloader=True)


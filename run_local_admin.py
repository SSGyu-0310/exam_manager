"""Local admin entrypoint."""
import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app(os.environ.get('FLASK_CONFIG') or 'local_admin')

if __name__ == '__main__':
    app.run(debug=True, port=5001)

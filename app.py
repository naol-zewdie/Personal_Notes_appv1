import os
import sys
from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__, instance_relative_config=True, template_folder='templates', static_folder='static')

# ensure instance folder exists before creating DB path
try:
    os.makedirs(app.instance_path, exist_ok=True)
except OSError:
    pass

# use absolute path for sqlite DB inside the instance folder
db_path = os.path.abspath(os.path.join(app.instance_path, 'notes.db'))
app.config.from_mapping(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)

# initialize shared DB instance
from extensions import db
db.init_app(app)

# import models so model classes are registered with SQLAlchemy
from models import Note


@app.route('/')
def index():
    return render_template('index.html', title='My Notes App')


@app.route('/learn')
def learn():
    return render_template('learn.html', title='Learn Flask')


@app.route('/create', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        if not title:
            # minimal validation: title required
            return render_template('create.html', title='Create Note', error='Title is required', form_title=title, form_content=content)

        note = Note(title=title, content=content)
        db.session.add(note)
        db.session.commit()
        return redirect(url_for('notes'))

    return render_template('create.html', title='Create Note')


@app.route('/notes')
def notes():
    notes = Note.query.order_by(Note.created_at.desc()).all()
    return render_template('notes.html', title='Notes', notes=notes)


if __name__ == '__main__':
    # support simple DB initialization: `python app.py init-db`
    if len(sys.argv) > 1 and sys.argv[1] == 'init-db':
        with app.app_context():
            db.create_all()
            print('Database initialized at', app.config['SQLALCHEMY_DATABASE_URI'])
    else:
        app.run(debug=True)

import os
import sys
import sqlalchemy as sa
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
    notes = Note.query.order_by(Note.created_at.desc()).all()
    return render_template('index.html', title='My Notes App', notes=notes)


@app.route('/learn')
def learn():
    return render_template('learn.html', title='Learn Flask')


@app.route('/create', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        category = request.form.get('category', '').strip() or None
        favorite = True if request.form.get('favorite') in ('on', 'true', '1') else False
        if not title:
            # minimal validation: title required
            return render_template('create.html', title='Create Note', error='Title is required', form_title=title, form_content=content)

        note = Note(title=title, content=content, category=category, favorite=favorite)
        db.session.add(note)
        db.session.commit()
        return redirect(url_for('notes'))

    return render_template('create.html', title='Create Note')


@app.route('/notes')
def notes():
    notes = Note.query.order_by(Note.created_at.desc()).all()
    return render_template('notes.html', title='Notes', notes=notes)


@app.route('/note/<int:note_id>')
def note(note_id):
    note = Note.query.get_or_404(note_id)
    return render_template('note.html', title=note.title, note=note)


@app.route('/edit/<int:note_id>', methods=['GET', 'POST'])
def edit(note_id):
    note = Note.query.get_or_404(note_id)
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        category = request.form.get('category', '').strip() or None
        favorite = True if request.form.get('favorite') in ('on', 'true', '1') else False
        if not title:
            return render_template('edit.html', title='Edit Note', note=note, error='Title is required', form_title=title, form_content=content, form_category=category)

        note.title = title
        note.content = content
        note.category = category
        note.favorite = favorite
        db.session.commit()
        return redirect(url_for('note', note_id=note.id))

    return render_template('edit.html', title='Edit Note', note=note, form_title=note.title, form_content=note.content)


@app.route('/delete/<int:note_id>', methods=['POST'])
def delete(note_id):
    note = Note.query.get_or_404(note_id)
    db.session.delete(note)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    results = []
    if q:
        # case-insensitive search on title or content
        pattern = f"%{q}%"
        results = Note.query.filter((Note.title.ilike(pattern)) | (Note.content.ilike(pattern))).order_by(Note.created_at.desc()).all()

    return render_template('search.html', title=f"Search: {q}", q=q, results=results)


@app.route('/category/<category_name>')
def category(category_name):
    notes = Note.query.filter(Note.category == category_name).order_by(Note.created_at.desc()).all()
    return render_template('notes.html', title=f'Category: {category_name}', notes=notes)


@app.route('/favorite/<int:note_id>', methods=['POST'])
def favorite_toggle(note_id):
    note = Note.query.get_or_404(note_id)
    note.favorite = not bool(note.favorite)
    db.session.commit()
    # redirect back to referrer if available, else to the note
    ref = request.referrer
    if ref:
        return redirect(ref)
    return redirect(url_for('note', note_id=note.id))


if __name__ == '__main__':
    # support DB initialization or small migration helpers
    if len(sys.argv) > 1 and sys.argv[1] == 'init-db':
        with app.app_context():
            db.create_all()
            print('Database initialized at', app.config['SQLALCHEMY_DATABASE_URI'])

    elif len(sys.argv) > 1 and sys.argv[1] == 'migrate-db':
        # safe small migration: add `category` column if missing (SQLite ALTER TABLE supported)
        with app.app_context():
            engine = db.engine
            inspector = sa.inspect(engine)
            cols = [c['name'] for c in inspector.get_columns('note')]
            if 'category' in cols:
                print('No action — `category` column already exists.')
            else:
                print('Adding `category` column to `note` table...')
                # SQLite supports ADD COLUMN; run with a connection/transaction
                try:
                    with engine.begin() as conn:
                        conn.execute(sa.text("ALTER TABLE note ADD COLUMN category VARCHAR(100)"))
                    print('Column added.')
                except Exception as exc:
                    print('Failed to add column:', exc)
            # ensure `favorite` column exists as well
            cols = [c['name'] for c in inspector.get_columns('note')]
            if 'favorite' in cols:
                print('No action — `favorite` column already exists.')
            else:
                print('Adding `favorite` column to `note` table...')
                try:
                    with engine.begin() as conn:
                        conn.execute(sa.text("ALTER TABLE note ADD COLUMN favorite BOOLEAN DEFAULT 0"))
                    print('`favorite` column added.')
                except Exception as exc:
                    print('Failed to add `favorite` column:', exc)

    else:
        app.run(debug=True)

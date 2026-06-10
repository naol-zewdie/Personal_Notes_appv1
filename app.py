import os
import sys
import sqlalchemy as sa
from sqlalchemy import func
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from markupsafe import Markup
import markdown as md
import io
import re
from flask import send_file
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
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

# setup Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))


# Jinja filter to render Markdown to safe HTML
def render_markdown(text):
    if not text:
        return ''
    html = md.markdown(text, extensions=['fenced_code', 'tables', 'nl2br'])
    return Markup(html)


app.jinja_env.filters['markdown'] = render_markdown


def notes_to_pdf_bytes(notes):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    for n in notes:
        title = n.title or ''
        elements.append(Paragraph(title, styles['Heading2']))
        # convert markdown to HTML then strip tags for simple plain rendering
        html = md.markdown(n.content or '')
        text = re.sub(r'<[^>]+>', '', html)
        # keep simple line breaks
        text = text.replace('\n', '<br/>')
        elements.append(Paragraph(text or '', styles['BodyText']))
        elements.append(Spacer(1, 12))
    doc.build(elements)
    buf.seek(0)
    return buf


@app.route('/export/note/<int:note_id>')
@login_required
def export_note(note_id):
    fmt = request.args.get('format', 'txt').lower()
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    if fmt == 'pdf':
        pdf = notes_to_pdf_bytes([note])
        return send_file(pdf, as_attachment=True, download_name=f'note-{note.id}.pdf', mimetype='application/pdf')

    # default: txt
    txt = f"{note.title}\n\n{note.content or ''}\n"
    bio = io.BytesIO(txt.encode('utf-8'))
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name=f'note-{note.id}.txt', mimetype='text/plain; charset=utf-8')


@app.route('/export/all')
@login_required
def export_all():
    fmt = request.args.get('format', 'txt').lower()
    notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.created_at.desc()).all()
    if fmt == 'pdf':
        pdf = notes_to_pdf_bytes(notes)
        return send_file(pdf, as_attachment=True, download_name='notes-all.pdf', mimetype='application/pdf')

    # default: txt
    parts = []
    for n in notes:
        title = n.title or ''
        parts.append(title)
        parts.append('-' * len(title))
        parts.append(n.content or '')
        parts.append('\n')
    txt = '\n'.join(parts)
    bio = io.BytesIO(txt.encode('utf-8'))
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name='notes-all.txt', mimetype='text/plain; charset=utf-8')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        from models import User
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('Username and password required')
            return render_template('register.html')
        if User.query.filter_by(username=username).first():
            flash('Username already taken')
            return render_template('register.html')
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        from models import User
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash('Invalid username or password')
            return render_template('login.html')
        login_user(user)
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/')
@login_required
def index():
    sort = request.args.get('sort', 'newest')
    base = Note.query.filter_by(user_id=current_user.id)
    if sort == 'oldest':
        q = base.order_by(Note.created_at.asc())
    elif sort == 'favorites':
        q = base.filter(Note.favorite == True).order_by(Note.created_at.desc())
    else:
        q = base.order_by(Note.created_at.desc())

    notes = q.all()
    return render_template('index.html', title='My Notes App', notes=notes, sort=sort)


@app.route('/learn')
def learn():
    return render_template('learn.html', title='Learn Flask')


@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        category = request.form.get('category', '').strip() or None
        favorite = True if request.form.get('favorite') in ('on', 'true', '1') else False
        if not title:
            # minimal validation: title required
            return render_template('create.html', title='Create Note', error='Title is required', form_title=title, form_content=content)
        # require login to create personal notes
        if not current_user.is_authenticated:
            flash('Please login to create a note.')
            return redirect(url_for('login'))

        note = Note(title=title, content=content, category=category, favorite=favorite, user_id=current_user.id)
        db.session.add(note)
        db.session.commit()
        return redirect(url_for('notes'))

    return render_template('create.html', title='Create Note')


@app.route('/notes')
@login_required
def notes():
    sort = request.args.get('sort', 'newest')
    base = Note.query.filter_by(user_id=current_user.id)
    if sort == 'oldest':
        q = base.order_by(Note.created_at.asc())
    elif sort == 'favorites':
        q = base.filter(Note.favorite == True).order_by(Note.created_at.desc())
    else:
        q = base.order_by(Note.created_at.desc())

    notes = q.all()
    return render_template('notes.html', title='Notes', notes=notes, sort=sort)


@app.route('/note/<int:note_id>')
@login_required
def note(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if note is None:
        abort(404)
    return render_template('note.html', title=note.title, note=note)


@app.route('/edit/<int:note_id>', methods=['GET', 'POST'])
@login_required
def edit(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if note is None:
        flash('Not authorized')
        return redirect(url_for('notes'))
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
@login_required
def delete(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if note is None:
        flash('Not authorized')
        return redirect(url_for('notes'))

    db.session.delete(note)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/search')
@login_required
def search():
    q = request.args.get('q', '').strip()
    results = []
    if q:
        # case-insensitive search on title or content within user's notes
        pattern = f"%{q}%"
        results = Note.query.filter(Note.user_id == current_user.id).filter((Note.title.ilike(pattern)) | (Note.content.ilike(pattern))).order_by(Note.created_at.desc()).all()

    return render_template('search.html', title=f"Search: {q}", q=q, results=results)


@app.route('/category/<category_name>')
@login_required
def category(category_name):
    notes = Note.query.filter_by(user_id=current_user.id).filter(Note.category == category_name).order_by(Note.created_at.desc()).all()
    return render_template('notes.html', title=f'Category: {category_name}', notes=notes)


@app.route('/favorite/<int:note_id>', methods=['POST'])
@login_required
def favorite_toggle(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if note is None:
        flash('Not authorized')
        return redirect(url_for('notes'))

    note.favorite = not bool(note.favorite)
    db.session.commit()
    # redirect back to referrer if available, else to the note
    ref = request.referrer
    if ref:
        return redirect(ref)
    return redirect(url_for('note', note_id=note.id))


@app.route('/dashboard')
def dashboard():
    total = Note.query.count()
    favorites = Note.query.filter(Note.favorite == True).count()
    # count distinct non-null categories
    categories_count = db.session.query(func.count(func.distinct(Note.category))).filter(Note.category != None).scalar() or 0
    # list categories with counts
    categories = db.session.query(Note.category, func.count(Note.id)).filter(Note.category != None).group_by(Note.category).all()
    return render_template('dashboard.html', title='Dashboard', total=total, favorites=favorites, categories_count=categories_count, categories=categories)


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
            # check and add `category` column
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

            # check and add `favorite` column
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

            # check and add `user_id` column
            cols = [c['name'] for c in inspector.get_columns('note')]
            if 'user_id' in cols:
                print('No action — `user_id` column already exists.')
            else:
                print('Adding `user_id` column to `note` table...')
                try:
                    with engine.begin() as conn:
                        conn.execute(sa.text("ALTER TABLE note ADD COLUMN user_id INTEGER"))
                    print('`user_id` column added.')
                except Exception as exc:
                    print('Failed to add `user_id` column:', exc)

            # create User table if missing and ensure all models' tables exist
            try:
                db.create_all()
                print('Ensured all tables exist (created missing tables).')
            except Exception as exc:
                print('Failed to create missing tables:', exc)

    else:
        app.run(debug=True)

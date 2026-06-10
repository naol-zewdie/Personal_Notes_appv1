# Personal Notes App (Phase 1 scaffold)

This repository contains the Phase 1 scaffold for a Personal Notes Flask app.

Quick start

1. (Optional) Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the app:

```powershell
python app.py
```

Files created

- `app.py`: Flask application and SQLAlchemy setup.
- `models.py`: basic `Note` and `Category` models (placeholder).
- `templates/index.html`: base index template.
- `static/style.css`: minimal stylesheet.
- `instance/`: instance folder (kept with `.gitkeep`).
- `requirements.txt`: core dependencies.

Next steps

- Implement CRUD routes and templates.
- Add migrations and seed data.

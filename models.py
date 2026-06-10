from datetime import datetime
from extensions import db


class Note(db.Model):
    """Note model representing a note entry.

    Fields:
      - id: Integer primary key
      - title: short string title
      - content: text body
      - category: optional category name
      - created_at: timestamp when created
      - updated_at: timestamp when last updated
    """

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True)
    favorite = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Note {self.id} {self.title!r}>"

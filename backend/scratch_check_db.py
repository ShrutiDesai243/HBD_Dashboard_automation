from app import app
from extensions import db
from sqlalchemy import text

with app.app_context():
    try:
        res = db.session.execute(text('DESCRIBE bigbasket_dbmapping'))
        print('DESCRIBE bigbasket_dbmapping:')
        for r in res:
            print(r)
    except Exception as e:
        print(f'Error: {e}')

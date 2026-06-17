import os
from flask import Flask
from extensions import db
from sqlalchemy import text
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

def run():
    with app.app_context():
        sql_file = "sql/002_create_dynamic_tier_tables.sql"
        if not os.path.exists(sql_file):
            print(f"Error: Could not find {sql_file}")
            return
            
        with open(sql_file, 'r') as f:
            sql_statements = f.read().split(';')
            
        print(f"Found {len(sql_statements)} statements. Executing...")
        
        for statement in sql_statements:
            if statement.strip():
                try:
                    db.session.execute(text(statement))
                    db.session.commit()
                except Exception as e:
                    print(f"Warning/Error on statement: {e}")
                    db.session.rollback()
        
        print("SQL execution complete!")

if __name__ == "__main__":
    run()

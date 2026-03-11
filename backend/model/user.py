from extensions import db

class User(db.Model):
    __tablename__ = "users"   # Force SQLAlchemy to use 'users' table

    # These 5 columns EXACTLY match your database image. Nothing else allowed.
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=True) 
    reset_otp = db.Column(db.String(10), nullable=True)
    reset_otp_expiry = db.Column(db.DateTime, nullable=True)

    def set_password(self, plain_password):
        self.password = plain_password

    def check_password(self, plain_password):
        if not self.password:
            return False
        return self.password == plain_password
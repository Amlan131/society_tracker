from app import create_app, db
from app.models import User

app = create_app()

def seed_admin():
    with app.app_context():
        if not User.query.filter_by(email="admin@society.com").first():
            admin = User(name="Society Admin", email="admin@society.com", role="admin")
            admin.set_password("Admin@123")
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: admin@society.com / Admin@123")

if __name__ == "__main__":
    seed_admin()
    app.run(host="0.0.0.0", port=5000, debug=True)

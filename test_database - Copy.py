from app_old import app, db, Admin

print("🔍 Testing database setup...")

with app.app_context():
    # Create all tables
    print("📁 Creating database tables...")
    db.create_all()
    
    # Delete existing admin (if any) to start fresh
    existing_admin = Admin.query.filter_by(username='admin').first()
    if existing_admin:
        print("🗑️ Removing existing admin...")
        db.session.delete(existing_admin)
        db.session.commit()
    
    # Create new admin user
    print("👤 Creating new admin user...")
    admin = Admin(username='admin')
    admin.set_password('admin123')
    admin.is_admin = True
    
    db.session.add(admin)
    db.session.commit()
    print("✅ Admin user created successfully!")
    
    # Test password verification
    test_admin = Admin.query.filter_by(username='admin').first()
    if test_admin and test_admin.check_password('admin123'):
        print("✅ Password verification works!")
        print(f"Admin ID: {test_admin.id}")
        print(f"Username: {test_admin.username}")
        print(f"Is Admin: {test_admin.is_admin}")
    else:
        print("❌ Password verification failed!")
    
    print("🎉 Database setup complete!")

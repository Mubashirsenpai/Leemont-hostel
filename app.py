import json
import os
import secrets # For generating session key
from flask import Flask, request, jsonify, redirect, url_for, render_template, flash, session, current_app, g
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash # Import for password hashing

# NEW: Import Cloudinary
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Initialize Flask app, specifying static and template folders
app = Flask(__name__, static_folder='static', template_folder='templates')

# --- Configuration ---
# IMPORTANT: Flask-Login requires 'SECRET_KEY' for session management
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(16))

# Use PostgreSQL database URI from environment variable
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# NEW: Cloudinary Configuration (Uncommented and using environment variables)
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')
)

CORS(app) # Enable CORS for all routes

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'user_login' # Default redirect for non-logged-in users

# User model now includes is_admin flag
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False) # Increased length for stronger hashes
    is_admin = db.Column(db.Boolean, default=False) # To distinguish admin users

    def __repr__(self):
        return f'<User {self.email}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Data Loading and Saving (using JSON file for hostel/room data) ---
DATA_FILE = os.path.join(app.root_path, 'data', 'rooms.json')

def load_hostel_data():
    """Loads hostel data from the JSON file. Creates default if not exists."""
    
    # Ensure the data directory exists before trying to read/write
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

    if not os.path.exists(DATA_FILE):
        # Create a default empty structure if file doesn't exist
        
        # Define the 15 individual rooms
        rooms_data = []
        num_individual_rooms = 15
        
        for i in range(1, num_individual_rooms + 1):
            room_id = f"room_{i}"
            room_name = f"Room {i}"
            
            # Alternate capacity and adjust price
            if i % 2 != 0: # Odd numbered rooms are single capacity
                capacity = 1
                price = 4800.00 + (i * 10)
                description = f"A comfortable single room (Room {i}) with a private bathroom and study desk, ideal for focused study."
                amenities = ["WiFi", "Private Toilet", "Single Bed", "Study Desk", "Wardrobe"]
            else: # Even numbered rooms are double capacity
                capacity = 2
                price = 3200.00 + (i * 10)
                description = f"Spacious double room (Room {i}), perfect for sharing with a roommate, featuring two beds and ample storage."
                amenities = ["WiFi", "Shared Bathroom", "Two Beds", "Study Desk", "Wardrobe"]
            
            rooms_data.append({
                "id": room_id,
                "name": room_name,
                "capacity": capacity,
                "price_per_academic_year": round(price, 2),
                "available_rooms": 1, # Each entry now represents one physical room
                "description": description,
                "amenities": amenities,
                "images": [f"https://placehold.co/400x300/6c5ce7/ffffff?text=Room+{i}"], # Generic image for each room
                "video_url": "",
                "is_deleted": False # New field: default to not deleted
            })

        default_data = {
            "hostel_name": "Leemont Hostel", # Hostel name is Leemont Hostel
            "general_video_url": "", # Keep empty for now, or add a placeholder
            "general_images": [ # Added more placeholder images for the slider
                '/static/images/Leemont Hostel Img.jpg', # Using direct static path
                "https://placehold.co/800x600/a29bfe/ffffff?text=Hostel+Lounge+2",
                "https://placehold.co/800x600/00b894/ffffff?text=Hostel+Room+3",
                "https://placehold.co/800x600/d63031/ffffff?text=Hostel+Study+4",
                "https://placehold.co/800x600/fdcb6e/ffffff?text=Hostel+Kitchen+5",
                "https://placehold.co/800x600/0984e3/ffffff?text=Hostel+Gym+6",
                "https://placehold.co/800x600/636e72/ffffff?text=Hostel+Entrance+7",
                "https://placehold.co/800x600/1a1933/ffffff?text=Hostel+Garden+8"
            ],
            "hostel_amenities": ["WiFi", "Laundry", "Private Toilet", "Kitchen", "24/7 Security", "Study Areas", "Gym", "Parking"],
            "rooms": rooms_data # Assign the generated rooms data
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(default_data, f, indent=2)
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
        # Ensure 'is_deleted' flag exists for all rooms loaded from existing file
        for room in data['rooms']:
            if 'is_deleted' not in room:
                room['is_deleted'] = False # Add flag for old entries
        return data

def save_hostel_data(data):
    """Saves hostel data to the JSON file."""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Load hostel_data immediately within an application context
hostel_data = {} # Initialize as empty dict for global scope
with app.app_context():
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    hostel_data = load_hostel_data()
    
    db.create_all()
    
    admin_email = 'admin@leemonthostel.com'
    admin_user = User.query.filter_by(email=admin_email).first()

    if not admin_user:
        admin_user = User(email=admin_email, is_admin=True)
        admin_user.set_password(os.environ.get('ADMIN_PASSWORD', 'Agent@2008')) 
        db.session.add(admin_user)
        db.session.commit()
        print(f"Default admin user '{admin_email}' created in PostgreSQL.")
    else:
        new_admin_password = os.environ.get('ADMIN_PASSWORD')
        if new_admin_password and not admin_user.check_password(new_admin_password):
            admin_user.set_password(new_admin_password)
            db.session.commit()
            print(f"Admin user '{admin_email}' password updated from environment variable.")
        print(f"Default admin user '{admin_email}' already exists in PostgreSQL.")

# Helper function to get only active rooms for public views
def get_active_rooms():
    global hostel_data 
    if hostel_data is None or 'rooms' not in hostel_data:
        hostel_data = load_hostel_data()
    return [room for room in hostel_data['rooms'] if not room.get('is_deleted', False)]


# --- Routes for Public Pages ---

@app.route('/')
@app.route('/home')
def home():
    """Renders the home page with general hostel info and some room highlights."""
    active_rooms = get_active_rooms()
    featured_rooms = active_rooms[:3] 
    return render_template('home.html', hostel=hostel_data, featured_rooms=featured_rooms)

@app.route('/gallery')
def gallery():
    """Renders the gallery page showing all hostel images and videos."""
    return render_template('gallery.html', hostel=hostel_data) 

@app.route('/rooms')
def rooms():
    """Renders the rooms page displaying all available rooms with details."""
    active_rooms = get_active_rooms()
    return render_template('rooms.html', rooms=active_rooms, hostel=hostel_data)

@app.route('/room/<room_id>')
def room_detail(room_id):
    """Renders a detailed page for a specific room."""
    room = next((r for r in get_active_rooms() if r['id'] == room_id), None)
    if room is None:
        flash('Room not found or is currently unavailable!', 'error')
        return redirect(url_for('rooms'))
    return render_template('room_detail.html', room=room, hostel=hostel_data)


@app.route('/book/<room_id>', methods=['GET', 'POST'])
@login_required 
def book(room_id):
    """Handles room booking requests."""
    if current_user.is_authenticated and current_user.is_admin:
        flash('Admin users cannot make bookings. Please log in as a regular user.', 'error')
        return redirect(url_for('home')) 

    room = next((r for r in get_active_rooms() if r['id'] == room_id), None)
    if room is None:
        flash('Room not found or is currently unavailable for booking!', 'error')
        return redirect(url_for('rooms'))

    if request.method == 'POST':
        num_students = int(request.form.get('num_students'))
        payment_method = request.form.get('payment_method')
        duration = request.form.get('duration') 

        if num_students > room['capacity']:
            flash(f'This is a {room["capacity"]}-person room. You selected {num_students} students.', 'error')
            return render_template('book.html', room=room, hostel=hostel_data)

        if room['available_rooms'] <= 0:
            flash('Sorry, this room is currently booked.', 'error') 
            return render_template('book.html', room=room, hostel=hostel_data)

        # --- Simulate Payment Process ---
        room['available_rooms'] -= 1 
        save_hostel_data(hostel_data) 

        flash(f'Booking for {room["name"]} successful! Payment via {payment_method} simulated. We will contact you shortly.', 'success')
        return redirect(url_for('rooms')) 

    return render_template('book.html', room=room, hostel=hostel_data)

# --- Routes for Regular User Authentication ---

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handles user registration."""
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        if current_user.is_admin: 
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('home')) 

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not email or not password or not confirm_password:
            flash('All fields are required.', 'error')
            return render_template('signup.html', hostel=hostel_data)

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html', hostel=hostel_data)

        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please login or use a different email.', 'error')
            return render_template('signup.html', hostel=hostel_data)

        new_user = User(email=email)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('user_login')) 

    return render_template('signup.html', hostel=hostel_data)

@app.route('/login', methods=['GET', 'POST'])
def user_login():
    """Handles regular user login."""
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        if current_user.is_admin: 
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('home')) 

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home')) 
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html', hostel=hostel_data)

@app.route('/logout')
@login_required
def logout():
    """Handles logging out both regular users and admin users."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home')) 

# --- Routes for Admin Pages ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Handles admin login."""
    if current_user.is_authenticated:
        if current_user.is_admin: 
            return redirect(url_for('admin_dashboard'))
        flash('Please log out of your regular account to log in as admin.', 'info')
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form.get('username') 
        password = request.form.get('password')

        admin_user = User.query.filter_by(email=email, is_admin=True).first()

        if admin_user and admin_user.check_password(password):
            login_user(admin_user)
            flash('Admin logged in successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin email or password.', 'error') 
    return render_template('admin_login.html', hostel=hostel_data)


@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Renders the admin dashboard with an overview of rooms."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))

    total_active_rooms = sum(room['available_rooms'] for room in get_active_rooms())
    return render_template('admin_dashboard.html', hostel=hostel_data, rooms=hostel_data['rooms'], total_available=total_active_rooms)

@app.route('/admin/edit_room/<room_id>', methods=['GET', 'POST'])
@login_required
def edit_room(room_id):
    """Handles editing details for a specific room."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))

    room = next((r for r in hostel_data['rooms'] if r['id'] == room_id), None)
    if room is None:
        flash('Room not found!', 'error')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        room['name'] = request.form.get('name')
        room['capacity'] = int(request.form.get('capacity'))
        room['price_per_academic_year'] = float(request.form.get('price_per_academic_year'))
        room['available_rooms'] = int(request.form.get('available_rooms'))
        room['description'] = request.form.get('description')
        room['amenities'] = [a.strip() for a in request.form.get('amenities').split(',') if a.strip()]

        # MODIFIED: These will now come from hidden inputs populated by JS upload
        room['images'] = [img.strip() for img in request.form.get('images').split('\n') if img.strip()]
        room['video_url'] = request.form.get('video_url').strip()

        save_hostel_data(hostel_data)
        flash('Room updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_room.html', room=room, hostel=hostel_data)

@app.route('/admin/add_room', methods=['GET', 'POST'])
@login_required
def add_room():
    """Handles adding a new room."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))

    if request.method == 'POST':
        new_room_id = 'room_' + secrets.token_hex(4)
        
        current_room_numbers = [int(r['name'].replace('Room ', '')) for r in hostel_data['rooms'] if r['name'].startswith('Room ')]
        next_room_number = max(current_room_numbers) + 1 if current_room_numbers else 1

        new_room = {
            "id": new_room_id,
            "name": f"Room {next_room_number}",
            "capacity": int(request.form.get('capacity')),
            "price_per_academic_year": float(request.form.get('price_per_academic_year')),
            "available_rooms": int(request.form.get('available_rooms')),
            "description": request.form.get('description'),
            "amenities": [a.strip() for a in request.form.get('amenities').split(',') if a.strip()],
            # MODIFIED: These will now come from hidden inputs populated by JS upload
            "images": [img.strip() for img in request.form.get('images').split('\n') if img.strip()],
            "video_url": request.form.get('video_url').strip(),
            "is_deleted": False
        }
        hostel_data['rooms'].append(new_room)
        save_hostel_data(hostel_data)
        flash('New room added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('add_room.html', hostel=hostel_data)

@app.route('/admin/delete_room/<room_id>', methods=['POST'])
@login_required
def delete_room(room_id):
    """Handles soft-deleting a room."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))

    global hostel_data
    room_found = False
    for room in hostel_data['rooms']:
        if room['id'] == room_id:
            room['is_deleted'] = True
            room_found = True
            break
    if room_found:
        save_hostel_data(hostel_data)
        flash(f'Room {room_id} marked as deleted successfully!', 'success')
    else:
        flash('Room not found.', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/restore_room/<room_id>', methods=['POST'])
@login_required
def restore_room(room_id):
    """Handles restoring a soft-deleted room."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))

    global hostel_data
    room_found = False
    for room in hostel_data['rooms']:
        if room['id'] == room_id:
            room['is_deleted'] = False
            room_found = True
            break
    if room_found:
        save_hostel_data(hostel_data)
        flash(f'Room {room_id} restored successfully!', 'success')
    else:
        flash('Room not found.', 'error')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/edit_hostel_details', methods=['GET', 'POST'])
@login_required
def edit_hostel_details():
    """Allows admin to edit general hostel details like name, general video/images, amenities."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))

    if request.method == 'POST':
        hostel_data['hostel_name'] = request.form.get('hostel_name')
        hostel_data['general_video_url'] = request.form.get('general_video_url').strip()
        hostel_data['general_images'] = [img.strip() for img in request.form.get('general_images').split('\n') if img.strip()]
        hostel_data['hostel_amenities'] = [a.strip() for a in request.form.get('hostel_amenities').split(',') if a.strip()]
        
        save_hostel_data(hostel_data)
        flash('Hostel details updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_hostel_details.html', hostel=hostel_data)


if __name__ == '__main__':
    app.run(debug=False)

import json
import os
import secrets # For generating session key
from flask import Flask, request, jsonify, redirect, url_for, render_template, flash, session, current_app, g
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash # Import for password hashing

# Initialize Flask app, specifying static and template folders
app = Flask(__name__, static_folder='static', template_folder='templates')

# --- Configuration ---
# IMPORTANT: Flask-Login requires 'SECRET_KEY' for session management
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(16))

# Debug print to confirm SECRET_KEY is set
print(f"--- APP STARTUP DEBUG ---")
print(f"Flask SECRET_KEY is set: {app.config['SECRET_KEY'] is not None}")
if app.config['SECRET_KEY'] is not None:
    print(f"Length of SECRET_KEY: {len(app.config['SECRET_KEY'])}")
else:
    print(f"SECRET_KEY is None.")
print(f"--- END APP STARTUP DEBUG ---")


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///leemonthostel.db' # Using SQLite for both hostel data and users
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Cloudinary Configuration (Uncomment and fill with your actual credentials)
# cloudinary.config(
#     cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
#     api_key = os.environ.get('CLOUDINARY_API_KEY'),
#     api_secret = os.environ.get('CLOUDINARY_API_SECRET')
# )

CORS(app) # Enable CORS for all routes

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'user_login' # Default redirect for non-logged-in users (changed from admin_login)

# User model for regular users
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False) # To distinguish from admin user

    def __repr__(self):
        return f'<User {self.email}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Simple AdminUser class for Flask-Login (for hardcoded admin only)
class AdminUser(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.is_admin = True # Mark as admin

    def get_id(self):
        return str(self.id)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Hardcoded admin user for demonstration. Password is hashed once at startup.
_ADMIN_USERNAME = "Mubashiruna"
_ADMIN_PLAINTEXT_PASSWORD = "Agent@2008"

# Hash the password once when the application starts
with app.app_context():
    _ADMIN_HASHED_PASSWORD = generate_password_hash(_ADMIN_PLAINTEXT_PASSWORD)
    ADMIN_USER_INSTANCE = AdminUser(id=9999, username=_ADMIN_USERNAME, password_hash=_ADMIN_HASHED_PASSWORD) # Use a distinct ID for admin

@login_manager.user_loader
def load_user(user_id):
    # Try to load as a regular user first
    user = User.query.get(int(user_id))
    if user:
        return user
    # If not a regular user, check if it's the hardcoded admin
    if user_id == str(ADMIN_USER_INSTANCE.id):
        return ADMIN_USER_INSTANCE
    return None

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
# This ensures it's populated when the app is imported by 'flask run'
hostel_data = {} # Initialize as empty dict for global scope
with app.app_context():
    # Ensure the data directory exists before loading/creating data
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    hostel_data = load_hostel_data()
    # Create database tables for User model if they don't exist
    db.create_all()
    print("DEBUG: hostel_data loaded and database tables created successfully during app initialization.")


# Helper function to get only active rooms for public views
def get_active_rooms():
    global hostel_data # Ensure we are working with the global variable
    if hostel_data is None or 'rooms' not in hostel_data:
        # Fallback if hostel_data somehow isn't loaded (shouldn't happen with current setup)
        hostel_data = load_hostel_data()
    return [room for room in hostel_data['rooms'] if not room.get('is_deleted', False)]


# --- Routes for Public Pages ---

@app.route('/')
@app.route('/home')
def home():
    """Renders the home page with general hostel info and some room highlights."""
    active_rooms = get_active_rooms()
    featured_rooms = active_rooms[:3] # Still show only a few featured rooms
    return render_template('home.html', hostel=hostel_data, featured_rooms=featured_rooms)

@app.route('/gallery')
def gallery():
    """Renders the gallery page showing all hostel images and videos."""
    return render_template('gallery.html', hostel=hostel_data) # Gallery doesn't filter rooms directly, shows general images

@app.route('/rooms')
def rooms():
    """Renders the rooms page displaying all available rooms with details."""
    active_rooms = get_active_rooms()
    return render_template('rooms.html', rooms=active_rooms, hostel=hostel_data)

@app.route('/room/<room_id>')
def room_detail(room_id):
    """Renders a detailed page for a specific room."""
    # Find the room among active rooms only
    room = next((r for r in get_active_rooms() if r['id'] == room_id), None)
    if room is None:
        flash('Room not found or is currently unavailable!', 'error')
        return redirect(url_for('rooms'))
    return render_template('room_detail.html', room=room, hostel=hostel_data)


@app.route('/book/<room_id>', methods=['GET', 'POST'])
@login_required # Only logged-in users can book
def book(room_id):
    """Handles room booking requests."""
    # Ensure the current_user is not the admin user for booking
    if current_user.is_authenticated and hasattr(current_user, 'is_admin') and current_user.is_admin:
        flash('Admin users cannot make bookings. Please log in as a regular user.', 'error')
        return redirect(url_for('home')) # Redirect admin away from booking

    # Find the room among active rooms only
    room = next((r for r in get_active_rooms() if r['id'] == room_id), None)
    if room is None:
        flash('Room not found or is currently unavailable for booking!', 'error')
        return redirect(url_for('rooms'))

    if request.method == 'POST':
        num_students = int(request.form.get('num_students'))
        payment_method = request.form.get('payment_method')
        duration = request.form.get('duration') # e.g., 'academic_year'

        if num_students > room['capacity']:
            flash(f'This is a {room["capacity"]}-person room. You selected {num_students} students.', 'error')
            return render_template('book.html', room=room, hostel=hostel_data)

        if room['available_rooms'] <= 0:
            flash('Sorry, this room is currently booked.', 'error') # Changed message to reflect single room
            return render_template('book.html', room=room, hostel=hostel_data)

        # --- Simulate Payment Process ---
        room['available_rooms'] -= 1 # Decrement available rooms (will go to 0 for a booked room)
        save_hostel_data(hostel_data) # Save updated data

        flash(f'Booking for {room["name"]} successful! Payment via {payment_method} simulated. We will contact you shortly.', 'success')
        return redirect(url_for('rooms')) # Redirect back to rooms or a confirmation page

    return render_template('book.html', room=room, hostel=hostel_data)

# --- Routes for Regular User Authentication ---

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handles user registration."""
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        # Redirect to a user dashboard or home page if already logged in
        if hasattr(current_user, 'is_admin') and current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('home')) # Or a user-specific dashboard

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
        return redirect(url_for('user_login')) # Redirect to the new user login route

    return render_template('signup.html', hostel=hostel_data)

@app.route('/login', methods=['GET', 'POST'])
def user_login():
    """Handles regular user login."""
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        # Redirect to appropriate dashboard if already logged in
        if hasattr(current_user, 'is_admin') and current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('home')) # Or a user-specific dashboard

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home')) # Redirect to original requested page or home
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html', hostel=hostel_data)

@app.route('/logout')
@login_required
def logout():
    """Handles logging out both regular users and admin users."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home')) # Redirect to home after logout

# --- Routes for Admin Pages (existing) ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Handles admin login."""
    print(f"DEBUG: Entering admin_login route. Request method: {request.method}")

    if current_user.is_authenticated:
        print("DEBUG: User is already authenticated. Redirecting to dashboard.")
        # If already logged in as a regular user, log them out first or redirect
        if not (hasattr(current_user, 'is_admin') and current_user.is_admin):
            flash('Please log out of your regular account to log in as admin.', 'info')
            return redirect(url_for('home')) # Redirect regular user away from admin login

        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        print(f"DEBUG: Attempting login with username: '{username}'")
        print(f"DEBUG: Admin username: '{_ADMIN_USERNAME}'")
        
        try:
            if username == _ADMIN_USERNAME and check_password_hash(ADMIN_USER_INSTANCE.password_hash, password):
                print("DEBUG: Password check successful. Attempting login_user.")
                login_user(ADMIN_USER_INSTANCE)
                print("DEBUG: login_user successful. Flashing success message.")
                flash('Logged in successfully!', 'success')
                print("DEBUG: Redirecting to admin_dashboard.")
                return redirect(url_for('admin_dashboard'))
            else:
                print("DEBUG: Invalid username or password. Flashing error message.")
                flash('Invalid username or password.', 'error')
        except Exception as e:
            print(f"ERROR: Exception during login process: {e}")
            flash('An unexpected error occurred during login. Please try again.', 'error')

    print("DEBUG: Rendering admin_login.html.")
    return render_template('admin_login.html', hostel=hostel_data)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Renders the admin dashboard with an overview of rooms."""
    # Ensure only admins can access this dashboard
    if not (hasattr(current_user, 'is_admin') and current_user.is_admin):
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home')) # Redirect non-admins

    total_active_rooms = sum(room['available_rooms'] for room in get_active_rooms())
    return render_template('admin_dashboard.html', hostel=hostel_data, rooms=hostel_data['rooms'], total_available=total_active_rooms)

@app.route('/admin/edit_room/<room_id>', methods=['GET', 'POST'])
@login_required
def edit_room(room_id):
    """Handles editing details for a specific room."""
    if not (hasattr(current_user, 'is_admin') and current_user.is_admin):
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
    if not (hasattr(current_user, 'is_admin') and current_user.is_admin):
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
    if not (hasattr(current_user, 'is_admin') and current_user.is_admin):
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
    if not (hasattr(current_user, 'is_admin') and current_user.is_admin):
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
    if not (hasattr(current_user, 'is_admin') and current_user.is_admin):
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
    app.run(debug=True)

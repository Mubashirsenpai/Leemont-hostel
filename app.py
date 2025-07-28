import json
import os
import secrets
import requests
import uuid
from flask import Flask, request, redirect, url_for, render_template, flash, session, g, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

# Initialize Flask app, specifying static and template folders
app = Flask(__name__, static_folder='static', template_folder='templates')

# --- Configuration ---
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(16))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///leemonthostel.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'user_login'

# NEW: Paystack Configuration
PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY', 'pk_test_YOUR_PAYSTACK_PUBLIC_KEY')
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', 'sk_test_YOUR_PAYSTACK_SECRET_KEY')
PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/"
PAYSTACK_INITIALIZE_URL = "https://api.paystack.co/transaction/initialize"

# --- DEBUGGING PAYSTACK KEYS (TEMPORARY) ---
# These print statements will show up in your Render deployment/runtime logs.
# For security, avoid printing the full secret key in production logs.
print(f"DEBUG: PAYSTACK_PUBLIC_KEY as seen by app: {PAYSTACK_PUBLIC_KEY}")
print(f"DEBUG: PAYSTACK_SECRET_KEY is set: {bool(PAYSTACK_SECRET_KEY)}")
if PAYSTACK_SECRET_KEY:
    print(f"DEBUG: PAYSTACK_SECRET_KEY prefix: {PAYSTACK_SECRET_KEY[:10]}...")
# --- END DEBUGGING ---

# --- SQLAlchemy Models ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    bookings = db.relationship('Booking', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    price_per_academic_year = db.Column(db.Float, nullable=False)
    available_rooms = db.Column(db.Integer, default=0)
    description = db.Column(db.Text, nullable=True)
    images_json = db.Column(db.Text, default='[]')
    videos_json = db.Column(db.Text, default='[]')
    amenities_json = db.Column(db.Text, default='[]')
    is_deleted = db.Column(db.Boolean, default=False)

    bookings = db.relationship('Booking', backref='room', lazy=True)

    def get_images(self):
        return json.loads(self.images_json) if self.images_json else []

    def set_images(self, image_list):
        self.images_json = json.dumps(image_list)

    def get_videos(self):
        return json.loads(self.videos_json) if self.videos_json else []

    def set_videos(self, video_list):
        self.videos_json = json.dumps(video_list)

    def get_amenities(self):
        return json.loads(self.amenities_json) if self.amenities_json else []

    def set_amenities(self, amenity_list):
        self.amenities_json = json.dumps(amenity_list)

    def __repr__(self):
        return f'<Room {self.name}>'

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    check_in_date = db.Column(db.Date, nullable=False)
    check_out_date = db.Column(db.Date, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='pending_payment')
    payment_reference = db.Column(db.String(100), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Booking {self.id} by User {self.user_id} for Room {self.room_id}>'

class HostelDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostel_name = db.Column(db.String(100), nullable=False, default='Leemont Hostel')
    general_video_url = db.Column(db.Text, default='')
    general_images_json = db.Column(db.Text, default='[]')
    hostel_amenities_json = db.Column(db.Text, default='[]')

    def get_general_images(self):
        return json.loads(self.general_images_json) if self.general_images_json else []

    def set_general_images(self, image_list):
        self.general_images_json = json.dumps(image_list)

    def get_hostel_amenities(self):
        return json.loads(self.hostel_amenities_json) if self.hostel_amenities_json else []

    def set_hostel_amenities(self, amenity_list):
        self.hostel_amenities_json = json.dumps(amenity_list)

    def __repr__(self):
        return f'<HostelDetails {self.hostel_name}>'


# --- Flask-Login User Loader ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Database Initialization and Data Seeding ---
def initialize_database():
    with app.app_context():
        db.create_all()

        admin_email = 'admin@leemonthostel.com'
        admin_user = User.query.filter_by(email=admin_email, is_admin=True).first()
        if not admin_user:
            admin_user = User(email=admin_email, is_admin=True)
            admin_user.set_password(os.environ.get('ADMIN_PASSWORD', 'adminpass'))
            db.session.add(admin_user)
            db.session.commit()
            print(f"Default admin user '{admin_email}' created.")
        else:
            print(f"Default admin user '{admin_email}' already exists.")
            new_admin_password = os.environ.get('ADMIN_PASSWORD')
            if new_admin_password and not admin_user.check_password(new_admin_password):
                admin_user.set_password(new_admin_password)
                db.session.commit()
                print(f"Admin user '{admin_email}' password updated from environment variable.")

        hostel_details_entry = HostelDetails.query.first()
        if not hostel_details_entry:
            hostel_details_entry = HostelDetails(
                hostel_name='Leemont Hostel',
                general_video_url='https://res.cloudinary.com/daxcvn02g/video/upload/v1708688009/hostel_general_video.mp4'
            )
            hostel_details_entry.set_general_images([
                '/static/images/Leemont Hostel Img.jpg',
                "https://placehold.co/800x600/a29bfe/ffffff?text=Hostel+Lounge+2",
                "https://placehold.co/800x600/00b894/ffffff?text=Hostel+Room+3",
                "https://placehold.co/800x600/d63031/ffffff?text=Hostel+Study+4",
                "https://placehold.co/800x600/fdcb6e/ffffff?text=Hostel+Kitchen+5",
                "https://placehold.co/800x600/0984e3/ffffff?text=Hostel+Gym+6",
                "https://placehold.co/800x600/636e72/ffffff?text=Hostel+Entrance+7",
                "https://placehold.co/800x600/1a1933/ffffff?text=Hostel+Garden+8"
            ])
            hostel_details_entry.set_hostel_amenities([
                'Free Wi-Fi', '24/7 Security', 'Laundry Service',
                'Study Rooms', 'Common Area', 'Backup Generator',
                'On-site Cafeteria', 'Parking', 'Cleaning Service'
            ])
            db.session.add(hostel_details_entry)
            db.session.commit()
            print("Default hostel details created.")
        else:
            print("Hostel details already exist.")

        if not Room.query.first():
            print("No rooms found, seeding initial room data...")
            rooms_data = []
            num_individual_rooms = 15
            for i in range(1, num_individual_rooms + 1):
                room_name = f"Room {i}"
                if i % 2 != 0:
                    capacity = 1
                    price = 4800.00 + (i * 10)
                    description = f"A comfortable single room (Room {i}) with a private bathroom and study desk, ideal for focused study."
                    amenities = ["WiFi", "Private Toilet", "Single Bed", "Study Desk", "Wardrobe"]
                else:
                    capacity = 2
                    price = 3200.00 + (i * 10)
                    description = f"Spacious double room (Room {i}), perfect for sharing with a roommate, featuring two beds and ample storage."
                    amenities = ["WiFi", "Shared Bathroom", "Two Beds", "Study Desk", "Wardrobe"]

                room = Room(
                    name=room_name,
                    capacity=capacity,
                    price_per_academic_year=round(price, 2),
                    available_rooms=1,
                    description=description,
                    is_deleted=False
                )
                room.set_images([f"https://placehold.co/400x300/6c5ce7/ffffff?text=Room+{i}"])
                room.set_videos([])
                room.set_amenities(amenities)
                db.session.add(room)
            db.session.commit()
            print("Initial room data seeded.")
        else:
            print("Rooms already exist in DB, skipping initial room data seeding.")

with app.app_context():
    initialize_database()

@app.teardown_request
def teardown_request(exception=None):
    db.session.remove()

@app.before_request
def load_hostel_details_for_request():
    g.hostel = HostelDetails.query.first()
    if not g.hostel:
        initialize_database()
        g.hostel = HostelDetails.query.first()


# --- Routes for Public Pages ---

@app.route('/')
@app.route('/home')
def home():
    """Renders the home page with general hostel info and some room highlights."""
    active_rooms = Room.query.filter_by(is_deleted=False).order_by(Room.id.asc()).limit(3).all()
    return render_template('home.html', hostel=g.hostel, featured_rooms=active_rooms)

@app.route('/gallery')
def gallery():
    """Renders the gallery page showing all hostel images and videos."""
    rooms = Room.query.filter_by(is_deleted=False).order_by(Room.id.asc()).all()
    return render_template('gallery.html', hostel=g.hostel, rooms=rooms)

@app.route('/rooms')
def rooms():
    """Renders the rooms page displaying all available rooms with details."""
    active_rooms = Room.query.filter_by(is_deleted=False).order_by(Room.id.asc()).all()
    return render_template('rooms.html', rooms=active_rooms, hostel=g.hostel)

@app.route('/room/<int:room_id>')
def room_detail(room_id):
    """Renders a detailed page for a specific room."""
    room = Room.query.get_or_404(room_id)
    if room.is_deleted and not (current_user.is_authenticated and current_user.is_admin):
        flash('This room is not available.', 'error')
        return redirect(url_for('rooms'))
    return render_template('room_detail.html', room=room, hostel=g.hostel)


@app.route('/book/<int:room_id>', methods=['GET', 'POST'])
@login_required
def book_room(room_id):
    """Handles room booking requests and initiates Paystack payment."""
    if current_user.is_authenticated and current_user.is_admin:
        flash('Admin users cannot make bookings. Please log in as a regular user.', 'error')
        return redirect(url_for('home'))

    room = Room.query.get_or_404(room_id)
    if room.is_deleted:
        flash('This room is not available for booking.', 'error')
        return redirect(url_for('rooms'))

    if request.method == 'POST':
        check_in_str = request.form.get('check_in_date')
        check_out_str = request.form.get('check_out_date')
        payment_method = request.form.get('payment_method')

        if not check_in_str or not check_out_str or not payment_method:
            flash('All booking fields are required.', 'error')
            return render_template('book.html', room=room, hostel=g.hostel)

        try:
            check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
            return render_template('book.html', room=room, hostel=g.hostel)

        if check_in >= check_out:
            flash('Check-out date must be after check-in date.', 'error')
            return render_template('book.html', room=room, hostel=g.hostel)

        if check_in < date.today():
            flash('Check-in date cannot be in the past.', 'error')
            return render_template('book.html', room=room, hostel=g.hostel)

        if room.available_rooms <= 0:
            flash('Sorry, this room is currently fully booked.', 'error')
            return render_template('book.html', room=room, hostel=g.hostel)

        total_price = room.price_per_academic_year

        payment_reference = str(uuid.uuid4())

        new_booking = Booking(
            user_id=current_user.id,
            room_id=room.id,
            check_in_date=check_in,
            check_out_date=check_out,
            total_price=total_price,
            status='pending_payment',
            payment_reference=payment_reference
        )
        db.session.add(new_booking)
        db.session.commit()

        amount_pesewas = int(total_price * 100)

        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "email": current_user.email,
            "amount": amount_pesewas,
            "reference": payment_reference,
            "callback_url": url_for('paystack_payment_callback', _external=True),
            "metadata": {
                "booking_id": new_booking.id,
                "room_id": room.id,
                "user_id": current_user.id
            }
        }

        try:
            response = requests.post(PAYSTACK_INITIALIZE_URL, headers=headers, json=payload)
            response.raise_for_status()
            paystack_data = response.json()

            if paystack_data['status'] and paystack_data['data']['authorization_url']:
                return jsonify({
                    'status': 'success',
                    'authorization_url': paystack_data['data']['authorization_url'],
                    'access_code': paystack_data['data']['access_code'],
                    'reference': payment_reference
                })
            else:
                db.session.rollback()
                flash('Payment initialization failed. Please try again.', 'error')
                return jsonify({'status': 'error', 'message': 'Payment initialization failed.'}), 500

        except requests.exceptions.RequestException as e:
            db.session.rollback()
            print(f"Paystack API error: {e}")
            flash('Could not connect to payment gateway. Please try again later.', 'error')
            return jsonify({'status': 'error', 'message': f'Payment gateway error: {e}'}), 500
        except Exception as e:
            db.session.rollback()
            print(f"An unexpected error occurred: {e}")
            flash('An unexpected error occurred during payment. Please try again.', 'error')
            return jsonify({'status': 'error', 'message': f'An unexpected error occurred: {e}'}), 500

    return render_template('book.html', room=room, hostel=g.hostel, paystack_public_key=PAYSTACK_PUBLIC_KEY)


@app.route('/paystack/callback')
def paystack_payment_callback():
    """Handles the redirect from Paystack after a payment attempt."""
    reference = request.args.get('trxref') or request.args.get('reference')

    if not reference:
        flash('Payment reference not found. Payment could not be verified.', 'error')
        return redirect(url_for('payment_failure'))

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
    }

    try:
        response = requests.get(f"{PAYSTACK_VERIFY_URL}{reference}", headers=headers)
        response.raise_for_status()
        paystack_data = response.json()

        if paystack_data['status'] and paystack_data['data']['status'] == 'success':
            booking = Booking.query.filter_by(payment_reference=reference).first()

            if booking:
                if booking.status == 'pending_payment':
                    booking.status = 'approved'
                    room = Room.query.get(booking.room_id)
                    if room and room.available_rooms > 0:
                        room.available_rooms -= 1
                    db.session.commit()
                    flash('Your booking has been successfully approved and confirmed!', 'success')
                    return redirect(url_for('payment_success', booking_id=booking.id))
                else:
                    flash('Payment already processed for this booking.', 'info')
                    return redirect(url_for('payment_success', booking_id=booking.id))
            else:
                flash('Payment successful, but associated booking not found. Please contact support.', 'warning')
                return redirect(url_for('payment_failure'))
        else:
            booking = Booking.query.filter_by(payment_reference=reference).first()
            if booking:
                booking.status = 'failed'
                db.session.commit()
            flash('Your payment was not successful. Please try again.', 'error')
            return redirect(url_for('payment_failure'))

    except requests.exceptions.RequestException as e:
        print(f"Paystack verification API error: {e}")
        flash('Payment verification failed due to a network error. Please contact support.', 'error')
        return redirect(url_for('payment_failure'))
    except Exception as e:
        print(f"An unexpected error occurred during payment verification: {e}")
        flash('An unexpected error occurred during payment verification. Please contact support.', 'error')
        return redirect(url_for('payment_failure'))


@app.route('/payment/success')
def payment_success():
    booking_id = request.args.get('booking_id')
    booking = None
    if booking_id:
        booking = Booking.query.get(booking_id)
    return render_template('payment_success.html', hostel=g.hostel, booking=booking)

@app.route('/payment/failure')
def payment_failure():
    return render_template('payment_failure.html', hostel=g.hostel)


# --- Routes for User Authentication ---

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
            return render_template('signup.html', hostel=g.hostel)

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html', hostel=g.hostel)

        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please login or use a different email.', 'error')
            return render_template('signup.html', hostel=g.hostel)

        new_user = User(email=email, is_admin=False)
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('user_login'))
        except Exception as e:
            db.session.rollback()
            print(f"Database error during signup: {e}")
            flash('An error occurred during signup. Please try again.', 'error')
            return render_template('signup.html', hostel=g.hostel)

    return render_template('signup.html', hostel=g.hostel)

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

    return render_template('login.html', hostel=g.hostel)

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
    return render_template('admin_login.html', hostel=g.hostel)


@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Renders the admin dashboard with an overview of rooms."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))

    rooms = Room.query.order_by(Room.id.asc()).all()
    total_active_rooms = Room.query.filter_by(is_deleted=False).count()
    return render_template('admin_dashboard.html', hostel=g.hostel, rooms=rooms, total_available=total_active_rooms)

@app.route('/admin/edit_room/<int:room_id>', methods=['GET', 'POST'])
@login_required
def edit_room(room_id):
    """Handles editing details for a specific room."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))

    room = Room.query.get_or_404(room_id)

    if request.method == 'POST':
        room.name = request.form.get('name')
        room.capacity = int(request.form.get('capacity'))
        room.price_per_academic_year = float(request.form.get('price_per_academic_year'))
        room.available_rooms = int(request.form.get('available_rooms'))
        room.description = request.form.get('description')

        images_str = request.form.get('images', '')
        if images_str == '':
            room.set_images([])
        else:
            image_urls = [url.strip() for url in images_str.split('\n') if url.strip()]
            room.set_images(image_urls)

        video_url_str = request.form.get('video_url', '')
        if video_url_str == '':
            room.set_videos([])
        else:
            room.set_videos([video_url_str])

        amenities_str = request.form.get('amenities', '')
        room.set_amenities([a.strip() for a in amenities_str.split(',') if a.strip()])

        db.session.commit()
        flash(f'Room {room.name} updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_room.html', room=room, hostel=g.hostel)

@app.route('/admin/add_room', methods=['GET', 'POST'])
@login_required
def add_room():
    """Handles adding a new room."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))

    if request.method == 'POST':
        name = request.form.get('name')
        capacity = int(request.form.get('capacity'))
        price_per_academic_year = float(request.form.get('price_per_academic_year'))
        available_rooms = int(request.form.get('available_rooms'))
        description = request.form.get('description')

        images_str = request.form.get('images', '')
        if images_str == '':
            images_list = []
        else:
            images_list = [url.strip() for url in images_str.split('\n') if url.strip()]

        video_url_str = request.form.get('video_url', '')
        if video_url_str == '':
            videos_list = []
        else:
            videos_list = [video_url_str]

        amenities_str = request.form.get('amenities', '')
        amenities_list = [a.strip() for a in amenities_str.split(',') if a.strip()]

        new_room = Room(
            name=name,
            capacity=capacity,
            price_per_academic_year=price_per_academic_year,
            available_rooms=available_rooms,
            description=description,
            is_deleted=False
        )
        new_room.set_images(images_list)
        new_room.set_videos(videos_list)
        new_room.set_amenities(amenities_list)

        db.session.add(new_room)
        db.session.commit()
        flash(f'New room "{name}" added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('add_room.html', hostel=g.hostel)

@app.route('/admin/delete_room/<int:room_id>', methods=['POST'])
@login_required
def delete_room(room_id):
    """Handles soft-deleting a room."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))

    room = Room.query.get_or_404(room_id)
    room.is_deleted = True
    db.session.commit()
    flash(f'Room "{room.name}" marked as deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/restore_room/<int:room_id>', methods=['POST'])
@login_required
def restore_room(room_id):
    """Handles restoring a soft-deleted room."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))

    room = Room.query.get_or_404(room_id)
    room.is_deleted = False
    db.session.commit()
    flash(f'Room "{room.name}" restored successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/edit_hostel_details', methods=['GET', 'POST'])
@login_required
def edit_hostel_details():
    """Allows admin to edit general hostel details like name, general video/images, amenities."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))

    hostel_details_entry = g.hostel

    if request.method == 'POST':
        hostel_details_entry.hostel_name = request.form.get('hostel_name')

        general_video_url_str = request.form.get('general_video_url', '')
        hostel_details_entry.general_video_url = general_video_url_str

        general_images_str = request.form.get('general_images', '')
        hostel_details_entry.set_general_images([img.strip() for img in general_images_str.split('\n') if img.strip()])

        hostel_amenities_str = request.form.get('hostel_amenities', '')
        hostel_details_entry.set_hostel_amenities([a.strip() for a in hostel_amenities_str.split(',') if a.strip()])

        db.session.commit()
        flash('Hostel details updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_hostel_details.html', hostel=hostel_details_entry)

# NEW: Route for My Bookings
@app.route('/my_bookings')
@login_required
def my_bookings():
    """Displays a list of bookings for the currently logged-in user."""
    # Ensure only regular users can view their bookings, not admins
    if current_user.is_admin:
        flash('Admin users do not have personal bookings.', 'info')
        return redirect(url_for('admin_dashboard'))

    # Fetch bookings for the current user, ordered by creation date descending
    user_bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()
    return render_template('my_bookings.html', hostel=g.hostel, bookings=user_bookings)


if __name__ == '__main__':
    app.run(debug=True)
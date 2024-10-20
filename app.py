import os
import cv2
from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
from rembg import remove
import numpy as np
from werkzeug.utils import secure_filename
import uuid
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash


print(cv2.__version__)  # Check the version
print(hasattr(cv2, 'dnn_superres'))  # Check if dnn_superres exists

app = Flask(__name__)
app.secret_key = 'your_secure_secret_key'  # Replace with a strong, unpredictable secret key

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'static/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max 16MB upload size

# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database configuration
db_config = {
    'host': 'database-2.cnqokwycqp5w.ap-south-1.rds.amazonaws.com',  # AWS RDS host
    'user': 'admin',  # Your MySQL RDS username
    'password': 'teja1234',  # Your MySQL RDS password
    'database': 'pixelperfection'  # Your database name
}

def create_connection():
    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            print("Connected to MySQL Database")
    except Error as e:
        print(f"Error: '{e}'")
    return connection

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Helper function to get logged-in user's ID
def get_logged_in_user_id():
    user_id = session.get('user_id')
    if user_id:
        return user_id
    else:
        flash('You need to be logged in to access this service.')
        return redirect(url_for('login'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username or not email or not password:
            flash('All fields are required.')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        conn = create_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""INSERT INTO users (username, email, password) VALUES (%s, %s, %s)""", (username, email, hashed_password))
            conn.commit()
            flash('Registration successful. Please log in.')
        except Error as e:
            flash(f"Error registering user: {e}")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = create_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']  # Store user ID in session
                flash('Login successful!')
                return redirect(url_for('imageAI'))
            else:
                flash('Invalid credentials, please try again.')

        except Error as e:
            flash(f"Error logging in: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template('login.html')

@app.route('/imageAI')
def imageAI():
    return render_template('imageAI.html')

@app.route('/removebg', methods=['GET', 'POST'])
def removebg():
    if request.method == 'POST':
        if 'image' not in request.files:
            flash('No file part in the form.')
            return redirect(request.url)
        file = request.files['image']
        if file.filename == '':
            flash('No file selected for uploading.')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_id = uuid.uuid4().hex
            unique_filename = f"{unique_id}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)

            # Remove background
            try:
                with open(filepath, 'rb') as input_file:
                    input_data = input_file.read()
                    output_data = remove(input_data)
            except Exception as e:
                flash(f'Error processing image: {e}')
                return redirect(request.url)

            processed_filename = f'no_bg_{unique_filename}'
            processed_filepath = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
            with open(processed_filepath, 'wb') as output_file:
                output_file.write(output_data)

            original_image_url = url_for('static', filename='uploads/' + unique_filename)
            processed_image_url = url_for('static', filename='uploads/' + processed_filename)

            user_id = get_logged_in_user_id()
            if isinstance(user_id, int):
                conn = create_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("""INSERT INTO services_used (user_id, service_type) VALUES (%s, %s)""", (user_id, 'Remove Background'))
                    conn.commit()
                except Error as e:
                    flash(f"Error recording service usage: {e}")
                finally:
                    cursor.close()
                    conn.close()

            return render_template('removebg.html', original_image=original_image_url, processed_image=processed_image_url)
        else:
            flash('Allowed image types are - png, jpg, jpeg, gif.')
            return redirect(request.url)
    return render_template('removebg.html')

@app.route('/cartoon', methods=['GET', 'POST'])
def cartoon():
    if request.method == 'POST':
        if 'image' not in request.files:
            flash('No file part in the form.')
            return redirect(request.url)
        file = request.files['image']
        if file.filename == '':
            flash('No file selected for uploading.')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_id = uuid.uuid4().hex
            unique_filename = f"{unique_id}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)

            # Cartoon effect logic
            img = cv2.imread(filepath)

            # Step 1: Use bilateral filter for a smooth yet detailed look
            img_color = cv2.bilateralFilter(img, d=9, sigmaColor=150, sigmaSpace=150)

            # Step 2: Convert to grayscale and smoothen it
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray_blur = cv2.medianBlur(gray, 7)

            # Step 3: Edge detection using adaptive thresholding for a sketch-like effect
            edges = cv2.adaptiveThreshold(
                gray_blur,
                255,
                cv2.ADAPTIVE_THRESH_MEAN_C,
                cv2.THRESH_BINARY,
                blockSize=9,
                C=2
            )

            # Step 4: Stylize the image using cv2.stylization to create a more painterly effect
            stylized_img = cv2.stylization(img_color, sigma_s=150, sigma_r=0.5)

            # Step 5: Convert edges to color and combine with stylized image
            edges_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            cartoon = cv2.bitwise_and(stylized_img, edges_colored)

            # Save the processed image
            processed_filename = f'cartoon_{unique_filename}'
            processed_filepath = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
            cv2.imwrite(processed_filepath, cartoon)

            original_image_url = url_for('static', filename='uploads/' + unique_filename)
            processed_image_url = url_for('static', filename='uploads/' + processed_filename)

            # Record service usage in the database
            user_id = get_logged_in_user_id()
            conn = create_connection()
            cursor = conn.cursor()

            try:
                cursor.execute("""INSERT INTO services_used (user_id, service_type) VALUES (%s, %s)""", (user_id, 'Convert to Cartoon Image'))
                conn.commit()
            except Error as e:
                flash(f"Error recording service usage: {e}")
            finally:
                cursor.close()
                conn.close()

            return render_template('cartoon.html', original_image=original_image_url, processed_image=processed_image_url)
        else:
            flash('Allowed image types are - png, jpg, jpeg, gif.')
            return redirect(request.url)
    return render_template('cartoon.html')

@app.route('/deblur', methods=['GET', 'POST'])
def deblur():
    if request.method == 'POST':
        if 'image' not in request.files:
            flash('No file part in the form.')
            return redirect(request.url)
        file = request.files['image']
        if file.filename == '':
            flash('No file selected for uploading.')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_id = uuid.uuid4().hex
            unique_filename = f"{unique_id}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)

            # Image deblurring logic using OpenCV
            img = cv2.imread(filepath)

            # Define a kernel for blurring (or sharpening, depending on the kernel values)
            kernel = np.array([[1, 4, 6, 4, 1],
                               [4, 16, 24, 16, 4],
                               [6, 24, -476, 24, 6],
                               [4, 16, 24, 16, 4],
                               [1, 4, 6, 4, 1]])

            kernel = kernel / (-256)  # Normalize the kernel

            deblurred_img = cv2.filter2D(img, -1, kernel)

            # Save the processed image
            processed_filename = f'deblurred_{unique_filename}'
            processed_filepath = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
            cv2.imwrite(processed_filepath, deblurred_img)

            original_image_url = url_for('static', filename='uploads/' + unique_filename)
            processed_image_url = url_for('static', filename='uploads/' + processed_filename)

            return render_template('deblur.html', original_image=original_image_url, processed_image=processed_image_url)
        else:
            flash('Allowed image types are - png, jpg, jpeg, gif.')
            return redirect(request.url)
    return render_template('deblur.html')


if __name__ == '__main__':
    app.run(debug=True)

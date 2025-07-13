import os
import cv2
import numpy as np
import pytesseract
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

# Set Tesseract path (update this to your Tesseract installation path)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Windows example
# For Linux/Mac: pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# SMTP Configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_ADDRESS = 'mi.jesko.x@gmail.com'
EMAIL_PASSWORD = 'mxpn pceq udon bdmh'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Define Database Model
class User(db.Model):
    id = db.Column(db.String(10), primary_key=True, unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(20), nullable=True)
    license_number = db.Column(db.String(50), nullable=True)
    photo_path = db.Column(db.String(200), nullable=True)
    license_photo_path = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f"User('{self.id}', '{self.name}', '{self.email}')"

# License Plate Recognition Functions
def preprocess_image(image_path):
    """Preprocess image for better OCR results"""
    img = cv2.imread(image_path)
    if img is None:
        return None
        
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply noise reduction
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    
    # Increase contrast
    contrast = cv2.convertScaleAbs(denoised, alpha=1.5, beta=0)
    
    # Apply thresholding
    _, thresh = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return thresh

def detect_license_plate(image_path):
    """Detect and extract license plate number using OCR"""
    # Preprocess the image
    processed_img = preprocess_image(image_path)
    if processed_img is None:
        return "OCR_FAILED: Image not found"
    
    # Use Tesseract to extract text
    try:
        # Configure Tesseract for license plate recognition
        custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        text = pytesseract.image_to_string(processed_img, config=custom_config)
        
        # Clean and validate the recognized text
        clean_text = ''.join(e for e in text if e.isalnum()).upper()
        if 5 <= len(clean_text) <= 10:  # Typical license plate length
            return clean_text
        return "OCR_FAILED: Invalid format"
    except Exception as e:
        return f"OCR_FAILED: {str(e)}"

# Email Sending Function
def send_email(to_email, name):
    """Send registration confirmation email"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_email
        msg['Subject'] = 'Registration Successful'

        body = f"""
        <html>
        <body>
            <h2>Welcome to our platform, {name}!</h2>
            <p>Your registration was successful. Here are your details:</p>
            <p><strong>Name:</strong> {name}</p>
            <p><strong>Email:</strong> {to_email}</p>
            <p>Thank you for joining us!</p>
            <br>
            <p>Best regards,</p>
            <p>The Registration Team</p>
        </body>
        </html>
        """

        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

# Photo Saving Function
def save_photo(file, folder):
    """Save uploaded photo and return its path"""
    if file and file.filename != '':
        filename = f"{uuid.uuid4().hex}.{file.filename.rsplit('.', 1)[1].lower()}"
        filepath = os.path.join(folder, filename)
        file.save(filepath)
        return filepath
    return None

@app.route('/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        mobile = request.form.get('mobile')
        
        # Save profile photo
        profile_photo = request.files.get('profile_photo')
        profile_photo_path = save_photo(profile_photo, UPLOAD_FOLDER)

        # Save license photo and process it
        license_photo = request.files.get('license_photo')
        license_photo_path = save_photo(license_photo, UPLOAD_FOLDER)
        
        # Extract license number using OCR
        license_number = "NOT_DETECTED"
        if license_photo_path:
            license_number = detect_license_plate(license_photo_path)
            if license_number.startswith("OCR_FAILED"):
                flash(f'License plate detection failed: {license_number[11:]}', 'warning')

        # Generate unique ID
        if email:
            prefix = email[0].upper()
            suffix = uuid.uuid4().hex[:5].upper()
            user_id = f"{prefix}{suffix}"
        else:
            user_id = uuid.uuid4().hex[:6].upper()

        # Save to Database
        try:
            new_user = User(
                id=user_id,
                name=name,
                email=email,
                mobile=mobile,
                license_number=license_number,
                photo_path=profile_photo_path,
                license_photo_path=license_photo_path
            )
            db.session.add(new_user)
            db.session.commit()
            
            # Send email notification
            if send_email(email, name):
                flash('Registration successful! Confirmation email has been sent.', 'success')
            else:
                flash('Registration successful! But email notification failed to send.', 'warning')

        except Exception as e:
            db.session.rollback()
            print(f"Database error: {e}")
            flash('Registration failed due to a database error. Please try again.', 'danger')

        return redirect(url_for('register'))

    return render_template('index.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
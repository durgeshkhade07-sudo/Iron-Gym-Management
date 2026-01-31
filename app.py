import os, io
from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)

# --- CONFIG ---
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gym.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15))
    membership_type = db.Column(db.String(50))
    photo = db.Column(db.String(200), default='default.png')
    status = db.Column(db.String(20), default='Absent')
    weight = db.Column(db.Float, default=0.0)
    height = db.Column(db.Float, default=0.0)
    join_date = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    members = Member.query.order_by(Member.join_date.desc()).all()
    for m in members:
        # BMI & Advice Logic
        if m.height > 0 and m.weight > 0:
            bmi = round(m.weight / ((m.height/100)**2), 1)
            m.bmi_val = bmi
            if bmi < 18.5:
                m.diet = "Weight Gain: Eat 500+ surplus calories."
                m.advice = "Focus on heavy compound lifts and protein."
            elif 18.5 <= bmi < 25:
                m.diet = "Maintain: Balanced Macros."
                m.advice = "Consistency is key. Focus on form."
            else:
                m.diet = "Weight Loss: 500 calorie deficit."
                m.advice = "Add cardio & HIIT. Drink more water."
        else:
            m.bmi_val = "N/A"
            m.diet = "Update Info"
            m.advice = "Add Weight/Height to see tips."

        # Expiry Tracking
        days = 30 if m.membership_type == 'Monthly' else 90 if m.membership_type == 'Quarterly' else 365
        expiry = m.join_date + timedelta(days=days)
        m.exp_date = expiry.strftime('%d %b %Y')
        m.is_expired = datetime.utcnow() > expiry

    return render_template('index.html', members=members)

@app.route('/register', methods=['GET', 'POST'])
def add_member():
    if request.method == 'POST':
        img = request.files.get('photo')
        img_name = 'default.png'
        if img and img.filename != '':
            img_name = secure_filename(img.filename)
            img.save(os.path.join(app.config['UPLOAD_FOLDER'], img_name))

        db.session.add(Member(
            name=request.form.get('name'),
            phone=request.form.get('phone'),
            membership_type=request.form.get('membership'),
            weight=float(request.form.get('weight', 0)),
            height=float(request.form.get('height', 0)),
            photo=img_name
        ))
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_member.html')

@app.route('/attendance/<int:id>')
def toggle_attendance(id):
    m = Member.query.get_or_404(id)
    m.status = 'Present' if m.status == 'Absent' else 'Absent'
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/download_report/<int:id>')
def download_report(id):
    m = Member.query.get_or_404(id)
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 20)
    p.drawString(100, 750, "IRON GYM - FITNESS REPORT")
    p.setFont("Helvetica", 12)
    p.drawString(100, 720, f"Athlete: {m.name} | Date: {datetime.now().strftime('%Y-%m-%d')}")
    p.line(100, 710, 500, 710)
    bmi = round(m.weight / ((m.height/100)**2), 1) if m.height > 0 else "N/A"
    p.drawString(100, 680, f"Weight: {m.weight}kg | Height: {m.height}cm | BMI: {bmi}")
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, 640, "Fitness Advice:")
    p.setFont("Helvetica", 12)
    advice = "Eat surplus calories for weight gain." if (isinstance(bmi, float) and bmi < 18.5) else "Eat in deficit for weight loss." if (isinstance(bmi, float) and bmi > 25) else "Maintain current balance."
    p.drawString(100, 620, f"-> {advice}")
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"{m.name}_IronGym_Report.pdf")

@app.route('/delete/<int:id>')
def delete_member(id):
    m = Member.query.get_or_404(id)
    db.session.delete(m)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
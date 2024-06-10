from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
import os
from flask_migrate import Migrate
import subprocess
import logging
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///patients.db')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Ensure necessary directories exist
os.makedirs('logs', exist_ok=True)
os.makedirs('plots', exist_ok=True)
os.makedirs('RR', exist_ok=True)
os.makedirs('QT', exist_ok=True)
os.makedirs('RESULT', exist_ok=True)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    prenom = db.Column(db.String(100))
    sexe = db.Column(db.String(10))
    date_naissance = db.Column(db.String(20))
    adresse = db.Column(db.String(200))
    poids = db.Column(db.String(20))
    taille = db.Column(db.String(20))
    imc = db.Column(db.String(20))
    medicaments = db.Column(db.String(500))
    historique_medical = db.Column(db.String(1000))
    nad_result = db.Column(db.String(100))
    timestamp = db.Column(db.String(20))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/patient_form', methods=['GET', 'POST'])
def patient_form():
    if request.method == 'POST':
        try:
            form_data = request.form
            nom = form_data['nom']
            prenom = form_data['prenom']
            sexe = form_data['sexe']
            date_naissance = form_data['date_naissance']
            adresse = form_data['adresse']
            poids = form_data['poids']
            taille = form_data['taille']
            imc = form_data['imc']
            medicaments = form_data['medicaments']
            historique_medical = form_data['historique_medical']
            existing_patient = Patient.query.filter_by(nom=nom, prenom=prenom, date_naissance=date_naissance).first()
            if existing_patient:
                flash('Ce patient existe déjà dans la base de données', 'danger')
                return redirect(url_for('patient_form'))
            new_patient = Patient(
                nom=nom, prenom=prenom, sexe=sexe, date_naissance=date_naissance,
                adresse=adresse, poids=poids, taille=taille, imc=imc, medicaments=medicaments,
                historique_medical=historique_medical, timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            db.session.add(new_patient)
            db.session.commit()
            patient_id = new_patient.id
            command = f"python analyse.py {patient_id}"
            logging.debug(f"Running command: {command}")
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"Error running QRS detector: {result.stderr}")
                flash(f"Erreur lors de l'exécution du détecteur QRS: {result.stderr}", 'danger')
                return redirect(url_for('patient_form'))
            with open(os.path.join("RESULT", f"result_{patient_id}.txt"), "r") as f:
                nad_result = f.readlines()[1].strip().split(":")[1].strip()
            new_patient.nad_result = nad_result
            db.session.commit()
            flash('Le patient a été ajouté avec succès.', 'success')
            return redirect(url_for('report.html'))
        except Exception as e:
            logging.error(f"Error in patient_form: {e}")
            flash(f"Erreur lors de l'ajout du patient: {e}", 'danger')
            return redirect(url_for('patient_form'))
    return render_template('patient_form.html')

@app.route('/get_image/<path:filename>')
def get_image(filename):
    return send_file(filename, mimetype='image/png')

@app.route('/get_file/<path:filename>')
def get_file(filename):
    return send_file(filename, mimetype='text/plain')

@app.route('/report')
def report():
    patients = Patient.query.all()
    data = []
    images = []
    imagesRR = []
    log_contents = []
    rr_log_contents = []
    qt_log_contents = []
    imagesQT = []
    for patient in patients:
        data.append(patient)
        patient_id = patient.id
        images.append(os.path.join('plots', f'QRS_offline_detector_plot_{patient_id}.png'))
        imagesRR.append(os.path.join('RR', f'RR_intervals_{patient_id}.png'))
        imagesQT.append(os.path.join('QT', f'QT_intervals_plot_{patient_id}.png'))
        log_file_path = os.path.join('logs', f'QRS_offline_detector_log_summary_{patient_id}.txt')
        log_fileRR_path = os.path.join('RR', f'RR_intervals_summary_{patient_id}.txt')
        log_fileQT_path = os.path.join('QT', f'QT_intervals_summary_{patient_id}.txt')
        try:
            with open(log_file_path, 'r') as file:
                log_contents.append(file.read())
        except FileNotFoundError:
            log_contents.append('Le fichier journal n\'a pas été trouvé!')
        try:
            with open(log_fileRR_path, 'r') as file:
                rr_log_contents.append(file.read())
        except FileNotFoundError:
            rr_log_contents.append('Le fichier journal des intervalles RR n\'a pas été trouvé!')
        try:
            with open(log_fileQT_path, 'r') as file:
                qt_log_contents.append(file.read())
        except FileNotFoundError:
            qt_log_contents.append('Le fichier journal des intervalles QT n\'a pas été trouvé!')
    max_length = max(len(data), len(images), len(imagesRR), len(imagesQT), len(log_contents), len(rr_log_contents), len(qt_log_contents))
    data += [None] * (max_length - len(data))
    images += [None] * (max_length - len(images))
    imagesRR += [None] * (max_length - len(imagesRR))
    imagesQT += [None] * (max_length - len(imagesQT))
    log_contents += [None] * (max_length - len(log_contents))
    rr_log_contents += [None] * (max_length - len(rr_log_contents))
    qt_log_contents += [None] * (max_length - len(qt_log_contents))
    return render_template('report.html', data=data, images=images, imagesRR=imagesRR, imagesQT=imagesQT, log_contents=log_contents, rr_log_contents=rr_log_contents, qt_log_contents=qt_log_contents)

@app.route('/manage_patients')
def manage_patients():
    patients = Patient.query.all()
    return render_template('manage_patients.html', patients=patients)

@app.route('/edit_patient/<int:patient_id>', methods=['GET', 'POST'])
def edit_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        try:
            form_data = request.form
            patient.nom = form_data['nom']
            patient.prenom = form_data['prenom']
            patient.sexe = form_data['sexe']
            patient.date_naissance = form_data['date_naissance']
            patient.adresse = form_data['adresse']
            patient.poids = form_data['poids']
            patient.taille = form_data['taille']
            patient.imc = form_data['imc']
            patient.medicaments = form_data['medicaments']
            patient.historique_medical = form_data['historique_medical']
            db.session.commit()
            flash('Les données du patient ont été mises à jour avec succès.', 'success')
            return redirect(url_for('manage_patients'))
        except Exception as e:
            logging.error(f"Error updating patient: {e}")
            flash(f"Erreur lors de la mise à jour des données du patient : {e}", 'danger')
            return redirect(url_for('edit_patient', patient_id=patient_id))
    return render_template('edit_patient.html', patient=patient)

@app.route('/delete_patient/<int:patient_id>', methods=['GET', 'POST'])
def delete_patient(patient_id):
    try:
        patient = Patient.query.get_or_404(patient_id)
        db.session.delete(patient)
        db.session.commit()
        flash('Le patient a été supprimé avec succès.', 'success')
        return redirect(url_for('manage_patients'))
    except Exception as e:
        logging.error(f"Error deleting patient: {e}")
        flash(f"Erreur lors de la suppression du patient : {e}", 'danger')
        return redirect(url_for('manage_patients'))

@app.route('/update_report', methods=['GET', 'POST'])
def update_report():
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        if patient_id:
            command = f"python analyse.py {patient_id}"
            logging.debug(f"Running command: {command}")
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"Error running QRS detector: {result.stderr}")
                flash(f"Erreur lors de la mise à jour du rapport: {result.stderr}", 'danger')
            else:
                flash('Le rapport a été mis à jour avec succès.', 'success')
    patients = Patient.query.all()
    return render_template('update_report.html', patients=patients)

def init_db():
    db.create_all()

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)

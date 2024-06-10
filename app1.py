from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
import os
from flask_migrate import Migrate
import subprocess
import logging
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///patients.db'
app.config['SECRET_KEY'] = 'GHOFRANE MHAMDI'  # Ajout de la clé secrète
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Ensure necessary directories exist
os.makedirs('logs', exist_ok=True)
os.makedirs('plots', exist_ok=True)
os.makedirs('RR', exist_ok=True)
os.makedirs('QT', exist_ok=True)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    prenom = db.Column(db.String(100))
    sexe = db.Column(db.String(10))
    date_naissance = db.Column(db.String(20))
    adresse = db.Column(db.String(200))
    assurance = db.Column(db.String(100))
    id_social = db.Column(db.String(100))
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
            # Retrieve form data
            nom = request.form['nom']
            prenom = request.form['prenom']
            sexe = request.form['sexe']
            date_naissance = request.form['date_naissance']
            adresse = request.form['adresse']
            assurance = request.form['assurance']
            id_social = request.form['id_social']
            poids = request.form['poids']
            taille = request.form['taille']
            imc = request.form['imc']
            medicaments = request.form['medicaments']
            historique_medical = request.form['historique_medical']
            
            # Check if the patient already exists
            existing_patient = Patient.query.filter_by(nom=nom, prenom=prenom, date_naissance=date_naissance).first()
            if existing_patient:
                return "Ce patient existe déjà dans la base de données", 400
            
            # Create a new patient object
            new_patient = Patient(nom=nom, prenom=prenom, sexe=sexe, date_naissance=date_naissance,
                                  adresse=adresse, assurance=assurance, id_social=id_social,
                                  poids=poids, taille=taille, imc=imc, medicaments=medicaments,
                                  historique_medical=historique_medical, timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            # Add the patient to the database
            db.session.add(new_patient)
            db.session.commit()
            
            # Get the ID of the newly created patient
            patient_id = new_patient.id
            
            # Call the QRS detector with the patient ID
            command = f"python analyse.py {patient_id}"
            logging.debug(f"Running command: {command}")
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"Error running QRS detector: {result.stderr}")
                return f"Error running QRS detector: {result.stderr}", 500
            
            # Retrieve the NAD result from the QRS detector
            with open(f"RESULTS/NAD_detection_result_{patient_id}.csv", "r") as f:
                nad_result = f.readlines()[1].strip().split(",")[1]
            
            # Update the patient record with the NAD result
            new_patient.nad_result = nad_result
            db.session.commit()
            
            return redirect(url_for('report'))
        except Exception as e:
            logging.error(f"Error in patient_form: {e}")
            return str(e), 500
    return render_template('patient_form.html')

@app.route('/get_image/<path:filename>')
def get_image(filename):
    # Return the image file from the specified path
    return send_file(filename, mimetype='image/png')

@app.route('/get_file/<path:filename>')
def get_file(filename):
    # Return the text file from the specified path
    return send_file(filename, mimetype='text/plain')

@app.route('/report')
def report():
    patients = Patient.query.all()
    data = []
    images = []  # List to store paths to images for each patient
    imagesRR = []  # List to store paths to RR interval images for each patient
    log_contents = []  # List to store log content for each patient
    rr_log_contents = []
    qt_log_contents = []  # List to store RR interval log content for each patient
    imagesQT = []
    
    for patient in patients:
        data.append(patient)
        patient_id = patient.id
        image_path = f'plots/QRS_offline_detector_plot_{patient_id}.png'
        images.append(image_path)
        log_file_path = f'logs/QRS_offline_detector_log_summary_{patient_id}.txt'
        imagRR_Path = f'RR/RR_intervals_{patient_id}.png'
        imagesRR.append(imagRR_Path)
        log_fileRR_path = f'RR/RR_intervals_summary_{patient_id}.txt'
        imagQT_Path = f'QT/QT_intervals_plot_{patient_id}.png'
        imagesQT.append(imagQT_Path)
        log_fileQT_path = f'QT/QT_intervals_summary_{patient_id}.txt'
        
        try:
            with open(log_file_path, 'r') as file:
                log_content = file.read()
                log_contents.append(log_content)
        except FileNotFoundError:
            log_contents.append('Le fichier journal n\'a pas été trouvé!')

        try:
            with open(log_fileRR_path, 'r') as file:
                rr_log_content = file.read()
                rr_log_contents.append(rr_log_content)
        except FileNotFoundError:
            rr_log_contents.append('Le fichier journal des intervalles RR n\'a pas été trouvé!')

        try:
            with open(log_fileQT_path, 'r') as file:
                qt_log_content = file.read()
                qt_log_contents.append(qt_log_content)
        except FileNotFoundError:
            qt_log_contents.append('Le fichier journal des intervalles QT n\'a pas été trouvé!')

    # Pad lists with None values to ensure they have the same length
    max_length = max(len(data), len(images), len(imagesRR), len(imagesQT), len(log_contents), len(rr_log_contents), len(qt_log_contents))
    data += [None] * (max_length - len(data))
    images += [None] * (max_length - len(images))
    imagesRR += [None] * (max_length - len(imagesRR))
    imagesQT += [None] * (max_length - len(imagesQT))
    log_contents += [None] * (max_length - len(log_contents))
    rr_log_contents += [None] * (max_length - len(rr_log_contents))
    qt_log_contents += [None] * (max_length - len(qt_log_contents))
    
    return render_template('report.html', data=data, images=images, imagesRR=imagesRR,  imagesQT=imagesQT, log_contents=log_contents, rr_log_contents=rr_log_contents, qt_log_contents=qt_log_contents)

@app.route('/manage_patients')
def manage_patients():
    patients = Patient.query.all()
    return render_template('manage_patients.html', patients=patients)

@app.route('/edit_patient/<int:patient_id>', methods=['GET', 'POST'])
def edit_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        try:
            # Update patient data
            patient.nom = request.form['nom']
            patient.prenom = request.form['prenom']
            patient.sexe = request.form['sexe']
            patient.date_naissance = request.form['date_naissance']
            patient.adresse = request.form['adresse']
            patient.assurance = request.form['assurance']
            patient.id_social = request.form['id_social']
            patient.poids = request.form['poids']
            patient.taille = request.form['taille']
            patient.imc = request.form['imc']
            patient.medicaments = request.form['medicaments']
            patient.historique_medical = request.form['historique_medical']
            
            db.session.commit()
            flash('Les données du patient ont été mises à jour avec succès.', 'success')
            return redirect(url_for('manage_patients'))
        except Exception as e:
            logging.error(f"Error updating patient: {e}")
            flash(f"Erreur lors de la mise à jour des données du patient : {e}", 'danger')
            return str(e), 500
        
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
        return str(e), 500
    
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

# Function to create the database and tables
def init_db():
    db.create_all()

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)

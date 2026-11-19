from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from main import PatientQueue

# Initialize the Flask web application
app = Flask(__name__)

# Enable CORS so your HTML/JS frontend can call this API without browser security blocks
CORS(app)

# Create a single shared PatientQueue instance in memory
queue = PatientQueue()


# Helper function to validate incoming patient data for normal & emergency routes
def validate_patient_data(data):
    required_fields = ['name', 'age', 'ailment', 'gender']
    missing = [field for field in required_fields if data.get(field) is None or str(data.get(field)).strip() == '']
    if missing:
        return None, f"Missing required field(s): {', '.join(missing)}"

    try:
        age = int(data['age'])
        if age <= 0 or age > 120:
            return None, "Age must be a valid number between 1 and 120."
    except (ValueError, TypeError):
        return None, "Age must be a valid integer."

    cleaned = {
        'name': str(data['name']).strip(),
        'age': age,
        'ailment': str(data['ailment']).strip(),
        'gender': str(data['gender']).strip()
    }
    return cleaned, None


# 1. Home / Health Check Route
# 1. Serve the Frontend HTML Page
@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

# 2. View Entire Waiting Queue (GET)
@app.route('/api/queue', methods=['GET'])
def get_queue():
    patients = queue.show()
    return jsonify({
        'count': len(patients),
        'queue': patients
    }), 200


# 3. Add a Normal Patient & Issue Token (POST)
@app.route('/api/queue/add', methods=['POST'])
def add_patient():
    # silent=True prevents a crash if the client sends empty or invalid JSON
    data = request.get_json(silent=True) or {}
    cleaned, error = validate_patient_data(data)

    if error:
        return jsonify({'error': error}), 400

    result = queue.add(
        cleaned['name'],
        cleaned['age'],
        cleaned['ailment'],
        cleaned['gender']
    )
    return jsonify({
        'message': 'Token issued successfully',
        'data': result
    }), 201  # 201 = Created


# 4. Add an Emergency Patient to the Front of the Queue (POST)
@app.route('/api/queue/emergency', methods=['POST'])
def add_emergency_patient():
    data = request.get_json(silent=True) or {}
    cleaned, error = validate_patient_data(data)

    if error:
        return jsonify({'error': error}), 400

    result = queue.add_emergency(
        cleaned['name'],
        cleaned['age'],
        cleaned['ailment'],
        cleaned['gender']
    )
    return jsonify({
        'message': 'Emergency token issued and prioritized',
        'data': result
    }), 201


# 5. Call / Serve Next Patient in Queue (POST)
@app.route('/api/queue/next', methods=['POST'])
def call_next_patient():
    result = queue.remove()
    if result is None:
        return jsonify({'message': 'The queue is empty'}), 404

    return jsonify({
        'message': 'Calling next patient',
        'patient': result
    }), 200


# 6. Check a Specific Token's Position & Status (GET)
@app.route('/api/token/<int:token_number>', methods=['GET'])
def get_token_status(token_number):
    status_info = queue.check_status(token_number)
    if status_info['status'] == 'Invalid Token':
        return jsonify(status_info), 404

    return jsonify(status_info), 200


# 7. Cancel a Waiting Token (DELETE)
@app.route('/api/token/<int:token_number>', methods=['DELETE'])
def cancel_patient_token(token_number):
    result = queue.cancel_token(token_number)
    if result is None:
        return jsonify({
            'error': f'Token {token_number} is not currently in the waiting queue.'
        }), 404

    return jsonify({
        'message': 'Token cancelled successfully',
        'data': result
    }), 200


# 8. Live Queue Dashboard Statistics (GET)
@app.route('/api/stats', methods=['GET'])
def get_stats():
    stats = queue.queue_stats()
    return jsonify(stats), 200


if __name__ == '__main__':
    # debug=True auto-restarts the server whenever you save changes to app.py
    app.run(host='127.0.0.1', port=5000, debug=True)
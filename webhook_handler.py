from flask import Flask, request, jsonify
from payments import PaymentSystem
from utils import LOGGER

app = Flask(__name__)

@app.route('/chapa/callback', methods=['POST'])
def chapa_callback():
    """Handle Chapa payment callbacks"""
    try:
        data = request.get_json()
        
        # Verify the transaction
        tx_ref = data.get('tx_ref')
        if not tx_ref:
            return jsonify({'error': 'Missing tx_ref'}), 400

        success, message = PaymentSystem.verify_payment(tx_ref)
        
        if success:
            return jsonify({'status': 'success', 'message': message}), 200
        else:
            return jsonify({'status': 'error', 'message': message}), 400

    except Exception as e:
        LOGGER.error(f"Callback error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(port=5000) 
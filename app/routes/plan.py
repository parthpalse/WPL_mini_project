from flask import Blueprint, jsonify

plan_bp = Blueprint('plan', __name__, url_prefix='/plan')


@plan_bp.route('/', methods=['GET'])
def index():
    return jsonify({'status': 'plan endpoint', 'message': 'Under construction'})

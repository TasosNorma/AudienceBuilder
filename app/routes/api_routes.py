from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from ..database.database import SessionLocal
from ..database.models import BlogProfileComparison,ProcessingResult
import logging
from ..api.general import Scheduler, Blog_Profile_Comparison_Handler,Processing_Result_Handler

api = Blueprint('api',__name__)

# Disables a schedule
@api.route('/disable_schedule/<int:schedule_id>', methods=['POST'])
@login_required
def disable_schedule(schedule_id):
    try:
        schedule_handler = Scheduler(current_user.id)
        result = schedule_handler.disable_schedule(schedule_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error disabling schedule: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        })


@api.route('/comparison/<int:comparison_id>/ignore', methods=['POST'])
@login_required
def ignore_comparison(comparison_id):
    try:
        comparison_handler = Blog_Profile_Comparison_Handler(current_user.id)
        result = comparison_handler.update_comparison_status(comparison_id, "Ignored Article")
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error ignoring comparison: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@api.route('/comparison/<int:comparison_id>/post', methods=['POST'])
@login_required
def post_comparison(comparison_id):
    try:
        comparison_handler = Blog_Profile_Comparison_Handler(current_user.id)
        result = comparison_handler.update_comparison_status(comparison_id, "Posted")
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error posting comparison: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": str(e)
        })


@api.route('/comparison/<int:comparison_id>/draft', methods=['POST'])
@login_required
def draft_comparison(comparison_id):
    try:
        comparison_handler = Blog_Profile_Comparison_Handler(current_user.id)
        result = comparison_handler.trigger_process_url_for_whatsapp_task(comparison_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error drafting comparison: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        })


@api.route('/comparison/<int:comparison_id>/ignore_draft', methods=['POST'])
@login_required
def ignore_draft_comparison(comparison_id):
    try:
        comparison_handler = Blog_Profile_Comparison_Handler(current_user.id)
        result = comparison_handler.update_comparison_status(comparison_id, "Ignored Draft")
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error ignoring draft comparison: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        })

        
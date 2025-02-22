from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from ..database.database import SessionLocal
from ..database.models import BlogProfileComparison,Post
import logging
from ..core.helper_handlers import Schedule_Handler, Blog_Profile_Comparison_Handler
from ..celery_worker.tasks import generate_post_from_comparison

api = Blueprint('api',__name__)

# Disables a schedule
@api.route('/disable_schedule/<int:schedule_id>', methods=['POST'])
@login_required
def disable_schedule(schedule_id):
    try:
        schedule_handler = Schedule_Handler(current_user.id)
        schedule_handler.disable_schedule(schedule_id)
        return jsonify({
            "status": "success"
        })
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
        Blog_Profile_Comparison_Handler.update_comparison_status(comparison_id, BlogProfileComparison.STATUS_INGNORED_COMPARISON,user_id=current_user.id)
        return jsonify({
            "status": "success"
        })
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
        Blog_Profile_Comparison_Handler.update_comparison_status(comparison_id, BlogProfileComparison.STATUS_POSTED,user_id=current_user.id)
        return jsonify({
            "status": "success"
        })
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
        generate_post_from_comparison.delay(comparison_id = comparison_id, user_id = current_user.id )
        return jsonify({
            "status": "success"
        })
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
        Blog_Profile_Comparison_Handler.update_comparison_status(comparison_id, BlogProfileComparison.STATUS_INGORED_DRAFT,user_id=current_user.id)
        return jsonify({
            "status": "success"
        })
    except Exception as e:
        logging.error(f"Error ignoring draft comparison: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        })

        
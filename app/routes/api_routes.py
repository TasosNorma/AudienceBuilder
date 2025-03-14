from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ..database.database import SessionLocal
from ..database.models import BlogProfileComparison,Post, Prompt
import logging
import os
import secrets
from ..core.helper_handlers import Schedule_Handler, Blog_Profile_Comparison_Handler, LinkedIn_Client_Handler
from ..celery_worker.tasks import redraft_linkedin_post_from_comparison, redraft_post_task, comparison_draft, draft_draft



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
        with SessionLocal() as db:
            linkedin_client = LinkedIn_Client_Handler(current_user.id)
            post_text = db.query(Post).filter(Post.blog_comparison_id == comparison_id, Post.user_id == current_user.id).first().plain_text
            linkedin_client.post(post_text)
            db.query(Post).filter(Post.blog_comparison_id == comparison_id, Post.user_id == current_user.id).update({Post.status: Post.STATUS_POSTED_LINKEDIN})
            db.commit()
        Blog_Profile_Comparison_Handler.update_comparison_status(comparison_id, BlogProfileComparison.STATUS_POSTED_LINKEDIN,user_id=current_user.id)
        return jsonify({
            "status": "success"
        })
    except Exception as e:
        logging.error(f"Error posting comparison: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": str(e)
        })

@api.route('/comparison/draft', methods=['POST'])
@login_required
def draft_comparison():
    try:
        data = request.get_json()
        comparison_id = data.get('comparison_id')
        prompt_id = data.get('prompt_id')
        if not comparison_id or not prompt_id:
            return jsonify({
                "status": "error",
                "message": "Comparison ID and prompt ID are required"
            })
        comparison_draft.delay(comparison_id = comparison_id, prompt_id = prompt_id, user_id = current_user.id)
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

@api.route('/comparison/<int:comparison_id>/redraft', methods=['POST'])
@login_required
def redraft_comparison(comparison_id):
    try:
        redraft_linkedin_post_from_comparison.delay(current_user.id, comparison_id)
        return jsonify({"status": "success", "message": "Re-drafting post..."})
    except Exception as e:
        logging.error(f"Error re-drafting comparison {comparison_id}: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

@api.route('/draft/draft', methods=['POST'])
@login_required
def drafts_draft():
    try:
        data = request.get_json()
        url = data.get('url')
        prompt_id = data.get('prompt_id')
        # print(url, prompt_id)
        
        if not url or not prompt_id:
            return jsonify({
                "status": "error",
                "message": "URL and prompt_id are required"
            })
            
        draft_draft.delay(url=url, prompt_id=prompt_id, user_id=current_user.id)
        return jsonify({
            "status": "success",
            "message": "Draft generation started"
        })
    except Exception as e:
        logging.error(f"Error creating draft: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@api.route('/draft/<int:post_id>/post', methods=['POST'])
@login_required
def post_draft(post_id):
    try:
        with SessionLocal() as db:
            post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
            if not post:
                return jsonify({"status": "error", "message": "Post not found"})
            
            linkedin_client = LinkedIn_Client_Handler(current_user.id)
            linkedin_client.post(post.plain_text)
            post.status = Post.POSTED_LINKEDIN
            # If post is linked to a comparison, update comparison status too
            if post.blog_comparison_id:
                Blog_Profile_Comparison_Handler.update_comparison_status(
                    post.blog_comparison_id, 
                    BlogProfileComparison.STATUS_POSTED_LINKEDIN,
                    user_id=current_user.id
                )
            db.commit()
        return jsonify({"status": "success", "message": "Post published to LinkedIn"})
    except Exception as e:
        logging.error(f"Error posting draft: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

@api.route('/draft/<int:post_id>/redraft', methods=['POST'])
@login_required
def redraft_draft(post_id):
    try:
        with SessionLocal() as db:
            post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
            if not post:
                return jsonify({"status": "error", "message": "Post not found"})
            redraft_post_task.delay(current_user.id, post_id)
        return jsonify({"status": "success", "message": "Re-drafting post..."})
    except Exception as e:
        logging.error(f"Error redrafting post: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

@api.route('/comparison/<int:comparison_id>/get_post', methods=['GET'])
@login_required
def get_comparison_post(comparison_id):
    try:
        with SessionLocal() as db:
            comparison = db.query(BlogProfileComparison).get(comparison_id)
            
            if not comparison or comparison.user_id != current_user.id:
                return jsonify({"status": "error", "message": "Comparison not found"}), 404
                
            if comparison.post_id:
                post = db.query(Post).get(comparison.post_id)
                if post:
                    return jsonify({
                        "status": "success",
                        "post": {
                            "id": post.id,
                            "plain_text": post.plain_text,
                            "markdown_text": post.markdown_text
                        }
                    }), 200
            
            return jsonify({"status": "error", "message": "No post found for this comparison"}), 404
    except Exception as e:
        logging.error(f"Error fetching post data: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    
@api.route('/user/prompts', methods=['GET'])
@login_required
def get_user_prompts():
    try:
        prompt_type = request.args.get('type', type=int)
        
        with SessionLocal() as db:
            prompts = db.query(Prompt).filter(
                Prompt.user_id == current_user.id,
                Prompt.is_active == True
            )
            if not prompts.first():
                return jsonify({"status": "error", "message": "No prompts found"}), 404
            
            if prompt_type:
                prompts = prompts.filter(Prompt.type == prompt_type)
                
            prompts = prompts.all()
            
            result = [{
                "id": prompt.id,
                "name": prompt.name,
            } for prompt in prompts]
            
            return jsonify({
                "status": "success",
                "prompts": result
            }), 200
    except Exception as e:
        logging.error(f"Error fetching user prompts: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
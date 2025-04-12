from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ..database.database import SessionLocal
from ..database.models import BlogProfileComparison,Post, Prompt, Group, Group_Comparison
import logging
import os
import secrets
from ..core.helper_handlers import Blog_Profile_Comparison_Handler, LinkedIn_Client_Handler, X_Client_Handler, AirflowHandler, Schedule_Handler


api = Blueprint('api',__name__)


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
        AirflowHandler().trigger_dag(dag_id='draft_action_task', conf={'action_id': comparison_id, 'prompt_id': prompt_id, 'user_id': current_user.id})
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

@api.route('/draft/draft', methods=['POST'])
@login_required
def drafts_draft():
    try:
        data = request.get_json()
        url = data.get('url')
        prompt_id = data.get('prompt_id')
        
        if not url or not prompt_id:
            return jsonify({
                "status": "error",
                "message": "URL and prompt_id are required"
            })
        
        # Initialize AirflowHandler to trigger DAG
        airflow_handler = AirflowHandler()
        
        # Prepare configuration for the DAG run
        conf = {
            "url": url,
            "prompt_id": prompt_id,
            "user_id": current_user.id
        }
        
        # Trigger the DAG
        airflow_handler.trigger_dag(dag_id="draft_draft_task", conf=conf)
        
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
    
# You have to specify if you want system prompts or not.
@api.route('/user/prompts', methods=['GET'])
@login_required
def get_user_prompts():
    try:
        prompt_type = request.args.get('type', type=int)
        system_prompts = request.args.get('system_prompts', 'false').lower() == 'true'
        
        with SessionLocal() as db:
            prompts = db.query(Prompt).filter(
                Prompt.user_id == current_user.id,
                Prompt.is_active == True,
                Prompt.system_prompt == system_prompts
            )
            
            if prompt_type:
                prompts = prompts.filter(Prompt.type == prompt_type)
            
            prompts_list = prompts.all()
            
            if not prompts_list:
                return jsonify({"status": "success", "prompts": []}), 200
            
            result = [{
                "id": prompt.id,
                "name": prompt.name,
            } for prompt in prompts_list]
            
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
    
    
@api.route('/draft/post_thread_x', methods=['POST'])
@login_required
def post_thread_x():
    try:
        data = request.get_json()
        post_id = data.get('post_id')
        
        if not post_id:
            return jsonify({
                "status": "error",
                "message": "Post ID is required"
            }), 400
            
        with SessionLocal() as db:
            post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
            if not post:
                return jsonify({"status": "error", "message": "Post not found"}), 404
            
            # Check if post has thread content
            if not post.thread_list_text:
                return jsonify({"status": "error", "message": "No thread content available for this post"}), 400
            
            # Check if user is connected to X
            if not current_user.x_connected:
                return jsonify({"status": "error", "message": "Please connect your X account first"}), 403
                
            import json
            thread_list = json.loads(post.thread_list_text)
            
            if not thread_list or not isinstance(thread_list, list) or len(thread_list) == 0:
                return jsonify({"status": "error", "message": "Invalid thread content"}), 400
            
            # Initialize X client and post thread
            x_client = X_Client_Handler(current_user.id)
            x_client.create_thread_text(thread_list)
            
            # Update post status
            post.status = Post.POSTED_X
            
            # If post is linked to a comparison, update comparison status too
            if post.blog_comparison_id:
                Blog_Profile_Comparison_Handler.update_comparison_status(
                    post.blog_comparison_id, 
                    BlogProfileComparison.STATUS_POSTED_X,
                    user_id=current_user.id
                )
            db.commit()
            
        return jsonify({"status": "success", "message": "Thread posted to X successfully"})
    except Exception as e:
        logging.error(f"Error posting thread: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    
@api.route('/user/groups', methods=['GET'])
@login_required
def get_user_groups():
    try:
        with SessionLocal() as db:
            groups = db.query(Group).filter(
                Group.user_id == current_user.id,
                Group.status.in_([Group.STATUS_PENDING_TO_DRAFT, Group.STATUS_DRAFTING])
            ).all()
            
            if not groups:
                return jsonify({"status": "success", "groups": []}), 200
            
            result = [{
                "id": group.id,
                "name": group.name,
                "status": group.status
            } for group in groups]
            
            return jsonify({
                "status": "success",
                "groups": result
            }), 200
    except Exception as e:
        logging.error(f"Error fetching user groups: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@api.route('/groups/add_action', methods=['POST'])
@login_required
def add_action_to_group():
    try:
        data = request.get_json()
        comparison_id = data.get('comparison_id')
        group_id = data.get('group_id')
        
        if not comparison_id or not group_id:
            return jsonify({
                "status": "error",
                "message": "Comparison ID and group ID are required"
            }), 400
            
        with SessionLocal() as db:
            # Check if comparison exists and belongs to the user
            comparison = db.query(BlogProfileComparison).filter(
                BlogProfileComparison.id == comparison_id,
                BlogProfileComparison.user_id == current_user.id
            ).first()
            
            if not comparison:
                return jsonify({
                    "status": "error",
                    "message": "Comparison not found"
                }), 404
                
            # Check if group exists and belongs to the user
            group = db.query(Group).filter(
                Group.id == group_id,
                Group.user_id == current_user.id
            ).first()
            
            if not group:
                return jsonify({
                    "status": "error",
                    "message": "Group not found"
                }), 404
                
            # Check if this comparison is already in the group
            existing_link = db.query(Group_Comparison).filter(
                Group_Comparison.group_id == group_id,
                Group_Comparison.blog_profile_comparison_id == comparison_id
            ).first()
            
            if existing_link:
                return jsonify({
                    "status": "error",
                    "message": "This article is already in the selected group"
                }), 400
                
            # Create new group_comparison link
            new_link = Group_Comparison(
                group_id=group_id,
                blog_profile_comparison_id=comparison_id
            )
            
            db.add(new_link)
            
            # Update the comparison's group_id
            comparison.group_id = group_id
            
            db.commit()
            
        return jsonify({
            "status": "success",
            "message": "Article added to group successfully"
        }), 200
    except Exception as e:
        logging.error(f"Error adding action to group: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    
@api.route('/groups/remove_action', methods=['POST'])
@login_required
def remove_action_from_group():
    try:
        data = request.get_json()
        logging.info(f"Received remove_action request with data: {data}")
        comparison_id = data.get('comparison_id')
        group_id = data.get('group_id')
        logging.info(f"Processing remove_action: comparison_id={comparison_id}, group_id={group_id}, user_id={current_user.id}")
        
        if not comparison_id or not group_id:
            error_msg = "Comparison ID and group ID are required"
            logging.error(f"Validation error: {error_msg}")
            return jsonify({
                "status": "error",
                "message": error_msg
            }), 400
            
        with SessionLocal() as db:
            # Check if comparison exists and belongs to the user
            comparison = db.query(BlogProfileComparison).filter(
                BlogProfileComparison.id == comparison_id,
                BlogProfileComparison.user_id == current_user.id
            ).first()
            
            if not comparison:
                error_msg = f"Comparison not found: id={comparison_id}, user={current_user.id}"
                logging.error(error_msg)
                return jsonify({
                    "status": "error",
                    "message": "Comparison not found"
                }), 404
                
            # Check if group exists and belongs to the user
            group = db.query(Group).filter(
                Group.id == group_id,
                Group.user_id == current_user.id
            ).first()
            
            if not group:
                error_msg = f"Group not found: id={group_id}, user={current_user.id}"
                logging.error(error_msg)
                return jsonify({
                    "status": "error",
                    "message": "Group not found"
                }), 404
                
            # Check if this comparison is in the group
            existing_link = db.query(Group_Comparison).filter(
                Group_Comparison.group_id == group_id,
                Group_Comparison.blog_profile_comparison_id == comparison_id
            ).first()
            
            if not existing_link:
                error_msg = f"No link found between group={group_id} and comparison={comparison_id}"
                logging.error(error_msg)
                return jsonify({
                    "status": "error",
                    "message": "This article is not in the selected group"
                }), 400
            
            # Remove the link
            logging.info(f"Removing link: group={group_id}, comparison={comparison_id}")
            db.delete(existing_link)
            
            # Update the comparison's group_id to None
            comparison.group_id = None
            
            db.commit()
            
        return jsonify({
            "status": "success",
            "message": "Article removed from group successfully"
        }), 200
    except Exception as e:
        logging.error(f"Error removing action from group: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    
@api.route('/groups/draft', methods=['POST'])
@login_required
def draft_groups():
    try:
        data = request.get_json()
        group_id = data.get('group_id')
        with SessionLocal() as db:
            prompt_id = db.query(Group).filter(Group.id == group_id, Group.user_id == current_user.id).first().prompt_id
        if not prompt_id:
            return jsonify({
                "status": "error",
                "message": "Prompt not found"
            }), 404
        
        if not group_id:
            return jsonify({
                "status": "error",
                "message": "Group ID is required"
            }), 400
        
        AirflowHandler().trigger_dag(dag_id='draft_group_task', conf={'group_id': group_id, 'prompt_id': prompt_id, 'user_id': current_user.id})

        return jsonify({
            "status": "success",
            "message": "Group draft generation started"
        }), 200
    except Exception as e:
        logging.error(f"Error drafting group: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@api.route('/comparison/ignore_and_learn', methods=['POST'])
@login_required
def ignore_and_learn():
    try:
        data = request.get_json()
        comparison_id = data.get('comparison_id')
        if not comparison_id:
            return jsonify({
                "status": "error",
                "message": "Comparison ID is required"
            }), 400
        AirflowHandler().trigger_dag(dag_id='ignore_and_learn_task', conf={'user_id': current_user.id, 'comparison_id': comparison_id})
        return jsonify({
            "status": "success",
            "message": "Ignore and learn started"
        }), 200
    except Exception as e:
        logging.error(f"Error in ignore and learn: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    
@api.route('/disable_schedule/<int:schedule_id>', methods=['POST'])
@login_required
def disable_schedule(schedule_id):
    try:
        schedule_handler = Schedule_Handler(user_id=current_user.id)
        schedule_handler.disable_schedule(schedule_id=schedule_id)
        return jsonify({
            "status": "success",
            "message": "Schedule disabled successfully"
        })
    except Exception as e:
        logging.error(f"Error disabling schedule: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500




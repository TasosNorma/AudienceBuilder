from app.database.database import SessionLocal
from app.database.models import User, ProfileComparison, Profile, BlogProfileComparison
from app.core.content_processor import SyncAsyncContentProcessor
from datetime import datetime, timezone
import logging

def compare_profile( url: str, user_id: int):
    with SessionLocal() as db:
        """
        Takes url and user_id.
        Creates a profile_comparison object, and compares the profile to the summary of the article of the url.
        Updates the profile_comparison object with the result.
        """
        try:
            profile = db.query(Profile).filter_by(user_id=user_id).first()
            user = db.query(User).get(user_id)
            profile_comparison = ProfileComparison(
                    user_id=user_id,
                    url=url,
                    status=ProfileComparison.PROCESSING,
                    created_at=datetime.utcnow(),
                    profile_interests=profile.interests_description 
                )
            db.add(profile_comparison)
            db.commit()
            db.flush()

            processor = SyncAsyncContentProcessor(user)
            article = processor.extract_article_content(profile_comparison.url)
            short_summary = processor.write_small_summary(article)
            relevance_result = processor.is_article_relevant_short_summary(
                short_summary=short_summary
            )

            profile_comparison.comparison_result = relevance_result
            profile_comparison.short_summary = short_summary
            profile_comparison.status = ProfileComparison.COMPLETED
        except Exception as e:
            profile_comparison.error_message= str(e)
            profile_comparison.status = ProfileComparison.FAILED
            logging.error(f"Error comparing profile: {str(e)}")
            raise e
        db.commit()


def ignore_and_learn(user_id:int, comparison_id:int):
    try:
        logging.warning(f"Starting ignore and learn task for user {user_id} and comparison {comparison_id}")
        with SessionLocal() as db:
            comparison = db.query(BlogProfileComparison).get(comparison_id)
            user = db.query(User).get(user_id)
            processor = SyncAsyncContentProcessor(user)
            new_profile_description = processor.ignore_and_learn(comparison_id)
            profile = db.query(Profile).filter_by(user_id=user_id).first()
            profile.interests_description = new_profile_description
            comparison.status = BlogProfileComparison.STATUS_INGNORED_COMPARISON
            db.commit()
            logging.warning(f"Successfully completed ignore and learn task for user {user_id} and comparison {comparison_id}")
    except Exception as e:
        logging.error(f"Error in the ignore and learn task: {str(e)}")
        raise e
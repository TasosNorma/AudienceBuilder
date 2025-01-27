from langchain_openai import ChatOpenAI
import os
from typing import Dict, Optional
from app.database.database import *
from app.database.models import Profile
from langchain.prompts import PromptTemplate
from .crawl4ai import *
import asyncio
import logging
from app.api.prompt_operations import get_prompt
from cryptography.fernet import Fernet

# This class is the Synchronous content processor
class SyncAsyncContentProcessor:

    def __init__(self,user):
        self.user = user
        try:
            fernet = Fernet(os.environ['ENCRYPTION_KEY'].encode())
            if not user.openai_api_key:
                logging.error(f"OpenAI API key not set for user {user.id}")
                raise ValueError("User's OpenAI API key is not set")
                
            self.decripted_api_key = fernet.decrypt(user.openai_api_key).decode()
            
            logging.info(f"Setting up LLM for user {user.id}...")
            self.llm = ChatOpenAI(openai_api_key=self.decripted_api_key, model_name='gpt-4o-mini')
            
            logging.info("Setting up crawler...")
            self.crawler = ArticleCrawler(self.decripted_api_key)
            
            logging.info("SyncAsyncContentProcessor initialization complete")
            
        except Exception as e:
            logging.error(f"Error during SyncAsyncContentProcessor initialization: {str(e)}")
            raise

    # This method creates a chain with the proper chain template so that we can insert the primary and secondary articles.
    def setup_chain(self):
        self.prompt = get_prompt(1,self.user.id)
        self.prompt_template = PromptTemplate(template=self.prompt,input_variables=["primary","secondary"])
        self.post_chain = self.prompt_template | self.llm

    # This method takes the string of the final post and breaks it down to sub-tweets.
    @staticmethod
    def _parse_tweets(social_post: str) -> list:
        content = social_post.content if hasattr(social_post, 'content') else social_post
        return [tweet.strip() for tweet in content.split('\n\n') 
                if tweet.strip() and not tweet.isspace()]

    # This method takes one URL and returns a dictionary that inside has the list of tweets.
    def process_url(self, url:str) -> Optional[Dict]:
        try:
            # Get the article
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    self.article = loop.run_until_complete(extract_article_content(url,self.decripted_api_key))
                except Exception as e:
                    print(f"Error getting the article content with async operation.{str(e)}")
            except Exception as e:
                print(f"Error extracting article content: {str(e)}")
                raise
            finally:
                loop.close()
            # Setup the chain
            try:
                print('Setting up the chains')
                self.setup_chain()
            except Exception as e:
                print(f'Error setting up the chains : {str(e)}')
                raise

            # Setting Secondary articles to None for now
            self.secondary_articles = "None"
            try:
                self.result = self.post_chain.invoke({
                    "primary": self.article,
                    "secondary": self.secondary_articles
                })
            except Exception as e:
                print(f"Error invoking post chain: {str(e)}")
                raise

            try:
                self.tweets = self._parse_tweets(self.result)
            except Exception as e:
                print(f"Error parsing tweets: {str(e)}")
                raise

            self.result = {
                "status": "success",
                "tweets": self.tweets,
                "tweet_count": len(self.tweets),
                "url": url
            }
            return self.result
        except Exception as e:
            return {
            "status": "error",
            "message": f"An error occurred: {str(e)}",
            "url": url
            }
    
    # This method takes a url and it judges whether it is relevant to the user or not.
    def is_article_relevant(self, url:str) -> bool:
        db = SessionLocal()
        try:
            # Get user's profile description from database
            profile_description = db.query(Profile).filter(
                Profile.user_id == self.user.id
            ).first().interests_description
            
            # Get article summary
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                summary = loop.run_until_complete(self.crawler.write_small_summary(url))
            except Exception as e:
                print(f"Error getting article summary: {str(e)}")
                raise
            finally:
                loop.close()
            
            # Setup the chain
            profile_prompt = get_prompt(2,self.user.id)
            profile_template = PromptTemplate(
                template=profile_prompt,
                input_variables=["profile","article"]
            )
            profile_chain = profile_template | self.llm

            # Run chain
            result = profile_chain.invoke({
                "profile": profile_description,
                "article": summary
            })

            # Parse result - should be just "Yes" or "No"
            print(result)
            return result.content.strip().lower() == "yes"

        except Exception as e:
            print(f"Error checking article relevance: {str(e)}")
            return False
        finally:
            db.close()
    
    # This method takes a short summary and compares relevance to the profile 
    def is_article_relevant_short_summary(self, short_summary:str) -> bool:
        db = SessionLocal()
        try:
            # Get user's profile description from database
            profile_description = db.query(Profile).filter(
                Profile.user_id == self.user.id
            ).first().interests_description
            
            # Get article summary
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Setup the chain
            profile_prompt = get_prompt(2,self.user.id)
            profile_template = PromptTemplate(
                template=profile_prompt,
                input_variables=["profile","article"]
            )
            profile_chain = profile_template | self.llm

            # Run chain
            result = profile_chain.invoke({
                "profile": profile_description,
                "article": short_summary
            })

            # Parse result - should be just "Yes" or "No"
            print(result)
            return result.content.strip().lower() == "yes"

        except Exception as e:
            print(f"Error checking article relevance: {str(e)}")
            return False
        finally:
            db.close()


        




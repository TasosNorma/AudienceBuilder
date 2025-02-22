from langchain_openai import ChatOpenAI
import os
from typing import Dict, Optional
from app.database.database import *
from app.database.models import Profile,ProfileComparison
from langchain.prompts import PromptTemplate
from .crawl4ai import ArticleCrawler
import asyncio
import logging
from cryptography.fernet import Fernet
from app.core.helper_handlers import Prompt_Handler

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
        self.prompt = Prompt_Handler.get_prompt_template(1,self.user.id)
        self.prompt_template = PromptTemplate(template=self.prompt,input_variables=["primary","secondary"])
        self.post_chain = self.prompt_template | self.llm

    # This method takes the string of the final post and breaks it down to sub-parts.
    @staticmethod
    def _parse_parts(social_post: str) -> list:
        content = social_post.content if hasattr(social_post, 'content') else social_post
        return [tweet.strip() for tweet in content.split('\n\n') 
                if tweet.strip() and not tweet.isspace()]

    # This method takes one URL and returns a dictionary that inside has the list of parts.
    def process_url(self, url:str) -> Optional[Dict]:
        try:
            # Get the article
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    self.article = loop.run_until_complete(self.crawler.extract_article_content(url))
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
                self.parts = self._parse_parts(self.result)
            except Exception as e:
                print(f"Error parsing parts: {str(e)}")
                raise

            self.result = {
                "status": "success",
                "parts": self.parts,
                "part_count": len(self.parts),
                "url": url
            }
            return self.result
        except Exception as e:
            return {
            "status": "error",
            "message": f"An error occurred: {str(e)}",
            "url": url
            }
    

    def is_article_relevant_for_profile_comparison(self, profile_description:str, summary:str) -> bool:
        try:
            # Setup the chain
            profile_prompt = Prompt_Handler.get_prompt_template(2,self.user.id)
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
            return result.content.strip().lower() == "yes"
        except Exception as e:
            raise e
    
    # This method takes a short summary and compares relevance to the profile 
    def is_article_relevant_short_summary(self, short_summary:str) -> bool:
        with SessionLocal() as db:
            # Get user's profile description from database
            profile_description = db.query(Profile).filter(
                Profile.user_id == self.user.id
            ).first().interests_description
            
            # Get article summary
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Setup the chain
            profile_prompt = Prompt_Handler.get_prompt_template(2,self.user.id)
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
            return result.content.strip().lower() == "yes"


        




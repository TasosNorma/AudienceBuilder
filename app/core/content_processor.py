from langchain_openai import ChatOpenAI
import os
from typing import Dict, Optional
from app.database.database import *
from app.database.models import Profile,ProfileComparison,Prompt
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
            
            logging.info("Setting up crawler...")
            self.crawler = ArticleCrawler(self.decripted_api_key)
            
            logging.info("SyncAsyncContentProcessor initialization complete")
            
        except Exception as e:
            logging.error(f"Error during SyncAsyncContentProcessor initialization: {str(e)}")
            raise e

    # This method takes prompt and model name and creates the chain to be invoked.
    def setup_chain(self,prompt_name:str,openai_llm_model_name:str):
        try:
            with SessionLocal() as db:
                self.prompt = db.query(Prompt).filter(
                    Prompt.name == prompt_name,
                    Prompt.user_id == self.user.id
                ).first()
            self.prompt_template = PromptTemplate(
                template=self.prompt.template,
                input_variables=self.prompt.input_variables
                )
            self.llm = ChatOpenAI(openai_api_key=self.decripted_api_key, model_name=openai_llm_model_name)
            self.post_chain = self.prompt_template | self.llm
        except Exception as e:
            logging.error(f"Error setting up chain: {str(e)}")
            raise e

    # This method takes one URL and returns a dictionary that inside has the list of parts.
    def generate_linkedin_informative_post_from_url(self, url:str):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.article = loop.run_until_complete(self.crawler.extract_article_content(url))
            loop.close()
            
            self.setup_chain(Prompt.NAME_LINKEDININFORMATIVEPOSTGENERATOR,'gpt-4o')
            self.result = self.post_chain.invoke({"article": self.article}).content
            
            return self.result
        except Exception as e:
            logging.error(f"Error processing URL {url}: {str(e)}")
            raise e
    
    def is_article_relevant_for_profile_comparison(self, profile_description:str, summary:str) -> bool:
        try:
            # Setup the chain
            profile_prompt = Prompt_Handler.get_prompt_template(Prompt.NAME_PROFILECOMPARISONPROMPT,self.user.id)
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
        try:
            with SessionLocal() as db:
                profile_description = db.query(Profile).filter(
                    Profile.user_id == self.user.id
                ).first().interests_description
            
            # Get article summary
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            self.setup_chain(Prompt.NAME_PROFILECOMPARISONPROMPT,'gpt-4o')
            self.result = self.post_chain.invoke({"profile": profile_description, "article": short_summary}).content
            # Parse result - should be just "Yes" or "No"
            return self.result.strip().lower() == "yes"
        except Exception as e:
            logging.error(f"Error in comparing article relevance to profile: {str(e)}")
            raise e


        




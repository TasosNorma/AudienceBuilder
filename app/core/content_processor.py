from langchain.chains import LLMChain, SimpleSequentialChain
from langchain.chains.base import Chain
from langchain.schema.runnable import RunnableBranch,RunnablePassthrough
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain_openai import ChatOpenAI
import os
from typing import Dict, Optional
from app.database.database import *
from app.database.models import Prompt,Profile,User
from langchain.prompts import PromptTemplate
from .crawl4ai import *
import time
from datetime import datetime
import json
from pathlib import Path
import asyncio
import logging
import urllib3
import warnings
from app.api.prompt_operations import get_prompt
from cryptography.fernet import Fernet


# This class can take a url and write a tweet.
class ContentProcessor:
    # Initialize the class with LLM, it takes the API key from an environment variable.
    def __init__(self,user):
        self.user = user
        fernet = Fernet(os.environ['ENCRYPTION_KEY'].encode())
        self.decripted_api_key = fernet.decrypt(self.user.openai_api_key).decode()
        self.llm = ChatOpenAI(openai_api_key=self.decripted_api_key, model_name='gpt-4o-mini')
        self.traces_dir = Path("traces")
        self.traces_dir.mkdir(exist_ok=True)

    # This method takes a dictionary and saves the trace in the traces folder
    def _save_trace(self,trace_data:dict):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        trace_file = self.traces_dir / f"trace_{timestamp}.json"
        
        if not isinstance(trace_data, dict):
            raise ValueError(f"trace_data must be a dictionary, got {type(trace_data)}")

        with open(trace_file, 'w') as f:
            json.dump(trace_data,f,indent=2)
            
    # This method fetches the prompt template of a prompt in the database and takes its ID as an arguement.
    # def get_prompt(self, id: int) -> Optional[str]:
    #     db = SessionLocal()
    #     try:
    #         prompt = db.query(Prompt).filter(Prompt.id == id).first()
    #         print(f"Fetched the template from the database and the template is :{prompt.template[:50]}")
    #         return prompt.template if prompt else None
    #     except Exception as e:
    #         print(f"Error fetching prompt from database {str(e)}")
    #         return None
    #     finally:
    #         db.close()

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
    async def process_url(self, url:str) -> Optional[Dict]:
        trace = {
            "url": url,
            "start_time": datetime.now().isoformat(),
            "steps": [],
            "content": {}
        }

        try:
            # Extract the article
            step_start = time.time()
            self.article = await extract_article_content(url,self.decripted_api_key)
            trace["steps"].append({
                "name": "extract_article",
                "duration": time.time() - step_start,
                "success": True
            })
            trace["content"]["article_preview"] = self.article
            
            # Setup the chain
            try:
                print('Setting up the chains')
                self.setup_chain()
            except Exception as e:
                print(f'Error setting up the chains : {str(e)}')

            # Get all the secondary articles in a long string
            step_start = time.time()
            self.secondary_articles = await get_formatted_summaries(url,self.decripted_api_key)
            trace["steps"].append({
                "name": "get_secondary_articles",
                "duration": time.time() - step_start,
                "success": True
            })
            trace["content"]["secondary_articles"] = self.secondary_articles

            
            # Run the chain
            step_start = time.time()
            trace["content"]["prompt_template"] = self.prompt  # Store the template
            trace["content"]["final_prompt"] = self.prompt_template.format(  # Store the formatted prompt
                primary=self.article,
                secondary=self.secondary_articles
            )
            self.result = self.post_chain.invoke({
                "primary": self.article,
                "secondary": self.secondary_articles
            })
            trace["steps"].append({
                "name": "run_chain",
                "duration": time.time() - step_start,
                "success": True
            })
            
            #break down the result in tweets
            step_start = time.time()
            self.tweets = self._parse_tweets(self.result)
            trace["steps"].append({
                "name": "parse_tweets",
                "duration": time.time() - step_start,
                "success": True
            })
            trace["content"]["tweets"] = self.tweets
            
            result = {
                "status": "success",
                "tweets": self.tweets,
                "tweet_count": len(self.tweets),
                "url": url
            }
            trace["status"] = "success"
            self._save_trace(trace)
            return result
        
        except Exception as e:
            trace["status"] = "error"
            trace["error"] = str(e)
            self._save_trace(trace)
            return {
            "status": "error",
            "message": f"An error occurred: {str(e)}",
            "url": url
            }
    
        # Setup a chain that will take only the primary article as input varibles and will create a chain, the purpose is for tests
    

# This class is the Synchronous content processor
class SyncContentProcessor:

    def __init__(self,user):
        self.user = user
        fernet = Fernet(os.environ['ENCRYPTION_KEY'].encode())
        self.decripted_api_key = fernet.decrypt(self.user.openai_api_key).decode()
        self.llm = ChatOpenAI(openai_api_key=self.decripted_api_key, model_name='gpt-4o-mini')
        self.crawler = Crawler(self.decripted_api_key)

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
                self.article = self.crawler.extract_article_content(url)
            except Exception as e:
                print(f"Error extracting article content: {str(e)}")
                raise
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


# This class is the Synchronous content processor
class SyncAsyncContentProcessor:

    def __init__(self,user):
        self.user = user
        fernet = Fernet(os.environ['ENCRYPTION_KEY'].encode())
        self.decripted_api_key = fernet.decrypt(self.user.openai_api_key).decode()
        self.llm = ChatOpenAI(openai_api_key=self.decripted_api_key, model_name='gpt-4o-mini')

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



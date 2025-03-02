from langchain_openai import ChatOpenAI
import os
from typing import Dict, Optional
from app.database.database import *
from app.database.models import Profile,ProfileComparison,Prompt
from langchain.prompts import PromptTemplate
import asyncio
import logging
import json
from cryptography.fernet import Fernet
from app.core.helper_handlers import Prompt_Handler
from app.core.scrapfly_crawler import ScrapflyCrawler
# This class is the Synchronous content processor
class SyncAsyncContentProcessor:

    def __init__(self,user):
        self.user = user
        try:
            fernet = Fernet(os.environ['ENCRYPTION_KEY'].encode())
            if not user.openai_api_key:
                raise ValueError("User's OpenAI API key is not set")
                
            self.decripted_api_key = fernet.decrypt(user.openai_api_key).decode()
            self.scrapfly_crawler = ScrapflyCrawler()
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

    def generate_linkedin_informative_post_from_url(self, url:str):
        try:
            self.article = self.extract_article_content(url)
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
    
    def write_small_summary(self, url:str):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            markdown_content = loop.run_until_complete(self.scrapfly_crawler.get_page_content(url))
            loop.close()
            llm = ChatOpenAI(openai_api_key=self.decripted_api_key, model_name='gpt-4o-mini')
            prompt = PromptTemplate(
                template="""You are tasked with creating a concise summary of the provided markdown content.

    INSTRUCTIONS:
    1. Create a summary of approximately 3-4 sentences (100-150 words)
    2. Focus on answering:
        - What is the main topic/announcement?
        - What are the key benefits or implications?
        - What are the most important technical details or facts?

    GUIDELINES:
    - Be factual and objective
    - Use clear, direct language
    - Avoid marketing language or subjective claims
    - Include specific numbers or metrics when present
    - Exclude quotes unless absolutely crucial
    - Do not include background information about the company
    - Do not mention the article's author or publication date

MARKDOWN CONTENT:
{markdown}
            """,
                input_variables=["markdown"]
            )
            
            logging.info("Invoking LLM chain for article extraction")
            chain = prompt | llm
            response = chain.invoke({"markdown": markdown_content})

            return response.content
        except Exception as e:
            logging.error(f"Error in writing small summary: {str(e)}")
            raise e
        
    def extract_article_content(self, url:str):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            markdown_content = loop.run_until_complete(self.scrapfly_crawler.get_page_content(url))
            loop.close()
            llm = ChatOpenAI(openai_api_key=self.decripted_api_key, model_name='gpt-4o-mini')
            prompt = PromptTemplate(
                template="""You are an expert at reading raw webpage markup and reconstructing the original article text. You will be given the complete HTML markup of a webpage that contains an article. Your task is to produce the clean article text in a well-structured, hierarchical format, reflecting the original headings and subheadings as closely as possible.
            # Instructions:
            * Article Content Only: Reproduce only the main article text. Omit any content not integral to the article (e.g., ads, navigation menus, related posts, social media links, comments).
            * No Additional Commentary: Do not include your own explanations or remarks. Present only what the original author wrote.
            * Don't Repeat Yourself: Do not repeat yourself, if you've said something once, do not say it again at the end of the article
            * Clean and Hierarchical Structure:
            * Use a clear hierarchy for titles and headings (e.g., # for the main title, ## for subheadings, etc.)
            * Maintain paragraph structure and any lists the author included.
            * Do not restate content unnecessarily. If something appears once, do not repeat it unless it was repeated in the original text.
            * No Non-textual Elements: Exclude images, URLs, and references that are not essential for understanding the article's core message.
            Your final output should be a neatly organized version of the article's textual content, suitable for further processing or summarization.

MARKDOWN CONTENT:
{markdown}
            """,
                input_variables=["markdown"]
            )
            
            logging.info("Invoking LLM chain for article extraction")
            chain = prompt | llm
            response = chain.invoke({"markdown": markdown_content})

            return response.content
        except Exception as e:
            logging.error(f"Error in extracting article content: {str(e)}")
            raise e
    
    def extract_all_articles_from_page(self, url: str):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            markdown_content = loop.run_until_complete(self.scrapfly_crawler.get_page_content(url))
            print(f"Extracted markdown content for {url}")
            loop.close()
            llm = ChatOpenAI(
                openai_api_key=self.decripted_api_key,
                model_name='gpt-4o'
            )
            prompt = PromptTemplate(
                template="""You are analyzing the markdown content of a webpage that contains multiple articles.

    TASK:
    Extract all main article links from the provided markdown content.

    INSTRUCTIONS:
    1. Extract ALL article links that appear in the main content area
    2. For each article found, extract:
    - The complete URL/href
    - The article title

    3. Exclude only:
    - Navigation menu links (like "new", "past", "comments", etc.)
    - Footer links
    - Login/submit/hide links
    - User profile links
    - Voting links

    Return the results as a JSON array of objects with 'url' and 'title' fields.

    IMPORTANT: Include ALL articles in the main content area, regardless of their topic or type.

    MARKDOWN CONTENT:
    {markdown}

    Return only the JSON array, nothing else.""",
                input_variables=["markdown"]
            )
            chain = prompt | llm
            response = chain.invoke({"markdown": markdown_content})
            content = response.content

            # The below is formating for the response of the LLM to become a nice dictionary that we can use with Code.
            if '```json' in content:
                content = content.split('```json\n')[1].split('```')[0]
            
            articles = json.loads(content)
            
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            base_url = f"https://{domain}"
            
            article_dict = {}
            for article in articles:
                if isinstance(article, dict) and 'url' in article and 'title' in article:
                    article_url = article['url']
                    if not article_url.startswith(('http://', 'https://')):
                        if article_url.startswith('/'):
                            article_url = f"{base_url}{article_url}"
                        else:
                            article_url = f"{base_url}/{article_url}"
                    article_dict[article_url] = article['title']            
            return article_dict
                
    
                
        except Exception as e:
            logging.error(f"Error extracting articles from {url}: {str(e)}")
            raise e
        

if __name__ == "__main__":
    from app.database.database import SessionLocal
    from app.database.models import User
    try:
        with SessionLocal() as db:
            user = db.query(User).get(30)  # Using a test user ID
            processor = SyncAsyncContentProcessor(user)
            url = "https://openai.com/news/"  # Example article URL
            summary = processor.extract_all_articles_from_page(url)
            print(summary)
    except Exception as e:
        print(f"Error occurred: {e}")

            


        




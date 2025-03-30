from langchain_openai import ChatOpenAI
import os
from app.database.database import *
from app.database.models import Profile,Prompt,BlogProfileComparison,Group_Comparison,Group
from langchain.prompts import PromptTemplate
import asyncio
import logging
import json
from cryptography.fernet import Fernet
from app.core.scrapfly_crawler import ScrapflyCrawler
from app.core.helper_handlers import Perplexity_Handler

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
    
    def setup_chain_from_prompt_id(self, prompt_id:int,model_name:str):
        try:
            with SessionLocal() as db:
                self.prompt = db.query(Prompt).get(prompt_id)
            self.prompt_template = PromptTemplate(
                template=self.prompt.template,
                input_variables=self.prompt.input_variables
                )
            self.llm = self.setup_llm(model_name)
            self.final_chain = self.prompt_template | self.llm
            return self.final_chain
        
        except Exception as e:
            logging.error(f"Error setting up chain: {str(e)}")
            raise e
        
    def setup_llm(self,openai_llm_model_name:str):
        self.llm = ChatOpenAI(
            openai_api_key=self.decripted_api_key,
            model_name=openai_llm_model_name,
            timeout=120,
            max_retries=3)
        return self.llm
    
    def is_article_relevant_short_summary(self, short_summary:str):
        try:
            with SessionLocal() as db:
                profile_description = db.query(Profile).filter(
                    Profile.user_id == self.user.id
                ).first().interests_description
                system_prompt = db.query(Prompt).filter(
                    Prompt.user_id == self.user.id,
                    Prompt.system_prompt == True,
                    Prompt.type == Prompt.TYPE_IS_ARTICLE_RELEVANT
                ).first()
                
            self.setup_chain_from_prompt_id(system_prompt.id, 'gpt-4o-mini')
            response = self.final_chain.invoke({"profile": profile_description, "article": short_summary})
            return response.content.strip().lower() == "yes"
        except Exception as e:
            logging.error(f"Error in comparing article relevance to profile: {str(e)}")
            raise e
    
    def draft(self, url:str = None, prompt_id:int = None,model_name:str='gpt-4o',group_id:int = None):
        try:
            with SessionLocal() as db:
                prompt = db.query(Prompt).get(prompt_id)
                if prompt.type == Prompt.TYPE_ARTICLE:
                    return self.draft_article(url,prompt_id,model_name)
                elif prompt.type == Prompt.TYPE_ARTICLE_DEEP_RESEARCH:
                    return self.draft_article_and_deep_research(url,prompt_id,model_name)
                elif prompt.type == Prompt.TYPE_GROUP:
                    return self.draft_group(group_id,prompt_id,model_name)
                else:
                    raise ValueError(f"Invalid prompt type: {prompt.type}")
        except Exception as e:
            logging.error(f"Error processing URL {url}: {str(e)}")
            raise e
    
    def draft_article_and_deep_research(self, url:str, prompt_id:int, model_name:str='gpt-4o'):
        try:
            perplexity_handler = Perplexity_Handler()
            self.article = self.extract_article_content(url)
            self.setup_chain_from_prompt_id(prompt_id,model_name)
            self.deep_research_prompt = self.create_prompt_for_deep_research(prompt_id,self.article)
            self.deep_research_result = perplexity_handler.deep_research(self.deep_research_prompt)
            self.result = self.final_chain.invoke({"article": self.article, "research_results": self.deep_research_result}).content
            return self.result
        except Exception as e:
            logging.error(f"Error processing URL {url}: {str(e)}")
            raise e
        
    def draft_article(self, url:str, prompt_id:int, model_name:str='gpt-4o'):
        try:
            self.article = self.extract_article_content(url)
            self.setup_chain_from_prompt_id(prompt_id,model_name)
            self.result = self.final_chain.invoke({"article": self.article}).content
            return self.result
        except KeyError as ke:
            # Check if this is a variable name mismatch error
            if "Input to PromptTemplate is missing variables" in str(ke):
                # Extract the expected variables from the error message
                error_msg = str(ke)
                user_friendly_error = (
                    f"Variable name mismatch in prompt template (ID: {prompt_id}). "
                    f"The system expects variables named 'article' and 'research_result', but your prompt uses different names. "
                    f"Please update your prompt template to use {{article}} and {{research_result}} as variable names. "
                    f"Original error: {error_msg}"
                )
                logging.error(user_friendly_error)
                raise ValueError(user_friendly_error) from ke
        except Exception as e:
            logging.error(f"Error processing URL {url}: {str(e)}")
            raise e
    
    def draft_group(self, group_id:int, prompt_id:int, model_name:str='gpt-4o'):
        try:
            combined_article_text = ""
            with SessionLocal() as db:
                group = db.query(Group).get(group_id)
                group_comparisons = db.query(Group_Comparison).filter(
                    Group_Comparison.group_id == group.id
                ).all()
                for i, group_comparison in enumerate(group_comparisons, 1):
                    blog_comparison = db.query(BlogProfileComparison).get(group_comparison.blog_profile_comparison_id)
                    combined_article_text += f"Article {i}: {blog_comparison.article_text}\n\n"
                self.setup_chain_from_prompt_id(prompt_id,model_name)
                self.result = self.final_chain.invoke({"group": combined_article_text}).content
                return self.result
        except Exception as e:
            logging.error(f"Error processing group: {str(e)}")
            raise e
        
    def write_small_summary(self, article_text:str):
        try:
            
            with SessionLocal() as db:
                system_prompt = db.query(Prompt).filter(
                    Prompt.user_id == self.user.id,
                    Prompt.system_prompt == True,
                    Prompt.type == Prompt.TYPE_WRITE_SMALL_SUMMARY
                ).first()
                
            self.setup_chain_from_prompt_id(system_prompt.id, 'gpt-4o-mini')
            response = self.final_chain.invoke({"markdown": article_text})
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
            
            with SessionLocal() as db:
                system_prompt = db.query(Prompt).filter(
                    Prompt.user_id == self.user.id,
                    Prompt.system_prompt == True,
                    Prompt.type == Prompt.TYPE_EXTRACT_ARTICLE_CONTENT
                ).first()
                
            self.setup_chain_from_prompt_id(system_prompt.id, 'gpt-4o-mini')
            response = self.final_chain.invoke({"markdown": markdown_content})
            return response.content
        except Exception as e:
            logging.error(f"Error in extracting article content: {str(e)}")
            raise e
    
    def extract_all_articles_from_page(self, url: str):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            markdown_content = loop.run_until_complete(self.scrapfly_crawler.get_page_content(url))
            loop.close()
            
            with SessionLocal() as db:
                system_prompt = db.query(Prompt).filter(
                    Prompt.user_id == self.user.id,
                    Prompt.system_prompt == True,
                    Prompt.type == Prompt.TYPE_EXTRACT_ALL_ARTICLES_FROM_PAGE
                ).first()
                
            self.setup_chain_from_prompt_id(system_prompt.id, 'gpt-4o-mini')
            response = self.final_chain.invoke({"markdown": markdown_content})
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
        
    def convert_markdown_to_plain_text(self, markdown_text:str):
        """Convert markdown formatted text to plain text suitable for LinkedIn posting."""
        try:
            with SessionLocal() as db:
                system_prompt = db.query(Prompt).filter(
                    Prompt.user_id == self.user.id,
                    Prompt.system_prompt == True,
                    Prompt.type == Prompt.TYPE_CONVERT_MARKDOWN_TO_PLAIN_TEXT
                ).first()
                
            self.setup_chain_from_prompt_id(system_prompt.id, 'gpt-4o-mini')
            response = self.final_chain.invoke({"markdown_text": markdown_text})
            return response.content
        except Exception as e:
            logging.error(f"Error converting markdown to plain text: {str(e)}")
            raise e
    
    def convert_markdown_to_tweet_thread(self, markdown_text:str):
        """Convert markdown formatted text to a list of tweets suitable for a Twitter thread."""
        try:
            with SessionLocal() as db:
                system_prompt = db.query(Prompt).filter(
                    Prompt.user_id == self.user.id,
                    Prompt.system_prompt == True,
                    Prompt.type == Prompt.TYPE_CONVERT_MARKDOWN_TO_THREAD_LIST
                ).first()
                
            self.setup_chain_from_prompt_id(system_prompt.id, 'gpt-4o-mini')
            response = self.final_chain.invoke({"markdown_text": markdown_text})
            
            # Process the response to create a list of tweets
            tweet_list = []
            tweet_pattern = r"Tweet \d+:\s*(.*?)(?=Tweet \d+:|$)"
            
            import re
            import json
            matches = re.findall(tweet_pattern, response.content, re.DOTALL)
            
            for match in matches:
                tweet_text = match.strip()
                if tweet_text:  # Only add non-empty tweets
                    tweet_list.append(tweet_text)
            return json.dumps(tweet_list)
        except Exception as e:
            logging.error(f"Error converting markdown to tweet thread: {str(e)}")
            raise e

    def create_prompt_for_deep_research(self, prompt_id:int, article:str):
        try:
            with SessionLocal() as db:
                prompt = db.query(Prompt).get(prompt_id)
                self.setup_llm('gpt-4o')
            prompt_template = PromptTemplate(
                template=prompt.deep_research_prompt,
                input_variables=["article"]
            )
            chain = prompt_template | self.llm
            response = chain.invoke({"article": article})
            return response.content
        except Exception as e:
            logging.error(f"Error creating prompt for deep research: {str(e)}")
            raise e
        
    def ignore_and_learn(self, comparison_id:int):
        try:
            with SessionLocal() as db:
                comparison = db.query(BlogProfileComparison).get(comparison_id)
                profile = db.query(Profile).filter(Profile.user_id == self.user.id).first()
                article = comparison.article_text
                system_prompt = db.query(Prompt).filter(
                    Prompt.user_id == self.user.id,
                    Prompt.system_prompt == True,
                    Prompt.type == Prompt.TYPE_IGNORE_AND_LEARN
                ).first()
                
            self.setup_chain_from_prompt_id(system_prompt.id, 'gpt-4o')
            response = self.final_chain.invoke({"profile": profile.interests_description, "article": article})
            return response.content
        except Exception as e:
            logging.error(f"Error in ignore and learn: {str(e)}")
            raise e
    
    def check_title_similarity(self, title, existing_titles_dict):
        """
        Checks if a title is similar to any existing titles from the past week.
        
        Args:
            title (str): The title to check
            existing_titles_dict (dict): Dictionary of id:title pairs to compare against
            
        Returns:
            str: The ID of the similar article if found, "No" if not similar
        """
        try:
            with SessionLocal() as db:
                system_prompt = db.query(Prompt).filter(
                    Prompt.user_id == self.user.id,
                    Prompt.system_prompt == True,
                    Prompt.type == Prompt.TYPE_CHECK_TITLE_SIMILARITY
                ).first()
                
                if not system_prompt:
                    # If no specific similarity prompt exists, use a default approach
                    self.llm = self.setup_llm('gpt-4o-mini')
                    prompt_template = PromptTemplate(
                        template="""You are helping to identify duplicate or very similar articles.
    Given a new article title and a list of existing article titles, determine if the new title 
    refers to the same news story or topic as any of the existing titles.

    New article title: {new_title}

    Existing article titles with IDs:
    {existing_titles}

    If the new article title refers to the same news story or topic as any of the existing titles,
    respond with only the ID of the most similar article. Respond just with the number of the ID, for example if the ID is 123 respond with "123". If there are no similar articles,
    respond with only "No".

    Your response:""",
                        input_variables=["new_title", "existing_titles"]
                    )
                    
                    # Format the existing titles dictionary for the prompt
                    existing_titles_formatted = "\n".join([f"ID {k}: {v}" for k, v in existing_titles_dict.items()])
                    
                    # Call the LLM
                    chain = prompt_template | self.llm
                    response = chain.invoke({
                        "new_title": title,
                        "existing_titles": existing_titles_formatted
                    })
                    
                    # Process the response - we expect either an ID or "No"
                    result = response.content.strip()
                    
                    # If result starts with "ID", extract just the number
                    if result.startswith("ID "):
                        result = result.split("ID ")[1].split(":")[0].strip()
                    
                    return result
                else:
                    self.setup_chain_from_prompt_id(system_prompt.id, 'gpt-4o-mini')
                    
                    # Format the existing titles dictionary for the prompt
                    existing_titles_formatted = "\n".join([f"ID {k}: {v}" for k, v in existing_titles_dict.items()])
                    
                    response = self.final_chain.invoke({
                        "new_title": title,
                        "existing_titles": existing_titles_formatted
                    })
                    
                    return response.content.strip()
        except Exception as e:
            logging.error(f"Error checking title similarity: {str(e)}")
            # On error, return "No" to be safe (don't want to incorrectly mark as duplicate)
            return "No"

                
                    
if __name__ == "__main__":
    from app.database.database import SessionLocal
    from app.database.models import User
    try:
        with SessionLocal() as db:
            user = db.query(User).get(30)  # Using a test user ID
            processor = SyncAsyncContentProcessor(user)
            article = processor.extract_all_articles_from_page("https://www.snowflake.com/en/blog/")
            print(article)
    except Exception as e:
        print(f"Error occurred: {e}")

            


        




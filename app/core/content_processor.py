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
            self.setup_llm('gpt-4o-mini')
            prompt = PromptTemplate(
                template="""You will receive two inputs: a profile description and an article. Your task is to determine if the person described in the profile would find the article relevant, interesting, and suitable for sharing on their social media.
                You must be very strict: only answer "Yes" if the article strongly aligns with their interests, professional focus, or sharing habits as described in the profile. Otherwise, answer "No".

                Instructions:
                1. Read the profile carefully to understand the individual's professional background, interests, and the types of content they are likely to share.
                2. Read the article and assess its topic, tone, and relevance to the profile's interests.
                3. If the article's content clearly matches the individual's interests or sharing criteria described in the profile, respond with "Yes".
                4. If it does not, respond with "No".
                5. Provide no additional commentary—only "Yes" or "No".

                Profile:
                "{profile}"

                Article:
                "{article}"
            """,
                input_variables=["profile", "article"]
            )
            chain = prompt | self.llm
            response = chain.invoke({"profile": profile_description, "article": short_summary})
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
        

    def write_small_summary(self, url:str):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            markdown_content = loop.run_until_complete(self.scrapfly_crawler.get_page_content(url))
            loop.close()
            self.setup_llm('gpt-4o-mini')
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
            chain = prompt | self.llm
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
            self.setup_llm('gpt-4o-mini')
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
            chain = prompt | self.llm
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
            loop.close()
            self.setup_llm('gpt-4o-mini')
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
            chain = prompt | self.llm
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
        
    def convert_markdown_to_plain_text(self, markdown_text:str):
        """Convert markdown formatted text to plain text suitable for LinkedIn posting."""
        try:
            self.setup_llm('gpt-4o-mini')
            prompt = PromptTemplate(
                template="""You are tasked with converting markdown text to plain text suitable for LinkedIn.

INSTRUCTIONS:
1. Remove all markdown formatting (##, *, _, etc.) but maintain the structure and hierarchy
2. Convert bullet points to appropriate Unicode characters (•)
3. Keep emojis intact
4. Maintain paragraph breaks
5. Format hashtags properly (keep the # symbol)
6. Ensure the text reads naturally on LinkedIn where markdown is not supported
7. Do not add or remove any content - just convert the formatting

MARKDOWN TEXT:
{markdown_text}

Provide ONLY the plain text version without any explanations.
                """,
                input_variables=["markdown_text"]
            )
            chain = prompt | self.llm
            response = chain.invoke({"markdown_text": markdown_text})
            return response.content
        except Exception as e:
            logging.error(f"Error converting markdown to plain text: {str(e)}")
            raise e
    
    def convert_markdown_to_tweet_thread(self, markdown_text:str):
        """Convert markdown formatted text to a list of tweets suitable for a Twitter thread."""
        try:
            self.setup_llm('gpt-4o-mini')
            prompt = PromptTemplate(
                template="""You are tasked with converting markdown text into a well-structured Twitter thread.

    INSTRUCTIONS:
    1. Break the content into multiple tweets of appropriate length (max 280 characters each)
    2. Ensure each tweet can stand on its own while maintaining the flow of the thread
    3. Keep emojis intact
    4. Use markdown formatting in the tweets
    5. Format hashtags properly (keep the # symbol)
    6. Number each tweet in your response as "Tweet 1:", "Tweet 2:", etc.
    7. Make the first tweet engaging to capture attention
    8. End the thread with a compelling conclusion or call to action
    9. Don't sacrifice important information just to fit character limits

    MARKDOWN TEXT:
    {markdown_text}

    Format your response with each tweet clearly numbered and separated:
    Tweet 1: [content of first tweet]
    Tweet 2: [content of second tweet]
    And so on...

    Provide ONLY the formatted tweets without any explanations.
                """,
                input_variables=["markdown_text"]
            )
            chain = prompt | self.llm
            response = chain.invoke({"markdown_text": markdown_text})
            
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
        
            

if __name__ == "__main__":
    from app.database.database import SessionLocal
    from app.database.models import User
    try:
        with SessionLocal() as db:
            user = db.query(User).get(30)  # Using a test user ID
            processor = SyncAsyncContentProcessor(user)
            article = processor.extract_article_content("https://www.bloomberg.com/news/articles/2025-03-03/alibaba-backed-zhipu-raises-140-million-as-deepseek-heats-up-ai?srnd=phx-technology")
            print(article)
    except Exception as e:
        print(f"Error occurred: {e}")

            


        




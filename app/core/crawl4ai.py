import json
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import LLMExtractionStrategy 
from urllib.parse import urlparse
import logging
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

class ArticleCrawler:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.crawler = None
    
    # Initialise the crawler in order to start the context manager
    async def initialize(self):
        if not self.crawler:
            self.crawler = AsyncWebCrawler(verbose=False, log_level=logging.ERROR, silent=True)
            await self.crawler.__aenter__()
        return self
    
    # Close the context manager
    async def cleanup(self):
        if self.crawler:
            await self.crawler.__aexit__(None, None, None)
            self.crawler = None

    async def extract_article_content(self, url: str):
        try:
            async with AsyncWebCrawler(verbose=False, log_level=logging.ERROR, silent=True) as crawler:
                print("Trying to extract the content from the article")
                try:
                    result = await crawler.arun(
                        url=url,
                        word_count_threshold=5,
                        extraction_strategy=LLMExtractionStrategy(
                            provider='openai/gpt-4o-mini',
                            api_token=self.api_key,
                            instruction=""" 
            You are an expert at reading raw webpage markup and reconstructing the original article text. You will be given the complete HTML markup of a webpage that contains an article. Your task is to produce the clean article text in a well-structured, hierarchical format, reflecting the original headings and subheadings as closely as possible.
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
                            """
                        ),
                        bypass_cache=True,
                        silent=True
                    )
                    if not result or not result.extracted_content:
                        print(f"Error: No content could be extracted from {url}")
                except Exception as e:
                    print(f"Error during content extraction: {str(e)}")
                    return f"Error: Failed to extract content from {url}. Reason: {str(e)}"
                
            try:
                if not isinstance(result.extracted_content, (str, bytes, bytearray)):
                    print(f"Error: Invalid content type received from crawler: {type(result.extracted_content)}")
                content_blocks = json.loads(result.extracted_content)
                formatted_article = []
                for block in content_blocks:
                    if 'content' in block:
                        formatted_article.extend(block['content'])
                
                article = "\n\n".join(formatted_article)
                return article
            except Exception as e:
                print(f"Error formatting article content: {str(e)}")
                raise e
        except Exception as e:
            print(f"Unexpected error processing article: {str(e)}")
            raise e

    async def write_small_summary(self, url: str):
        async with AsyncWebCrawler(verbose=False, log_level=logging.ERROR, silent=True) as crawler:
            try:
                result = await crawler.arun(
                    url=url,
                    word_count_threshold=5,
                    extraction_strategy=LLMExtractionStrategy(
                        provider='openai/gpt-4o-mini',
                        api_token=self.api_key,
                        instruction="""You are tasked with creating a concise summary of the provided webpage content.

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

    FORMAT:
    Return only the summary text, with no additional headers or metadata."""
                    ),
                    bypass_cache=True
                )
                if not result or not result.extracted_content:
                    logging.error(f"No content could be extracted from {url}")
                    return None
                
                try:
                    content_blocks = json.loads(result.extracted_content)
                    formatted_article = []
                    for block in content_blocks:
                        if 'content' in block:
                            formatted_article.extend(block['content'])
                
                    summary = "\n\n".join(formatted_article)
                    return summary.strip()
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse JSON from extracted content: {str(e)}")
                    raise e
                except Exception as e:
                    logging.error(f"Error formatting summary: {str(e)}")
                    raise e 
            except Exception as e:
                logging.error(f"Error extracting summary from {url}: {str(e)}")
                raise e
        
    async def extract_all_articles_from_page(self, url: str):
        async with AsyncWebCrawler(verbose=False, log_level=logging.ERROR) as crawler:
            logging.info(f"Starting article extraction from URL: {url}")
            result = await crawler.arun(url)
            logging.info(f"Raw crawler markdown result: {result.markdown[:200]}...")  # Log first 200 chars
            
            logging.info("Initializing ChatOpenAI with GPT-4")
            llm = ChatOpenAI(
                openai_api_key=self.api_key,
                model_name='gpt-4o'
            )
            
            logging.info("Creating prompt template for article extraction")
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
            
            logging.info("Invoking LLM chain for article extraction")
            chain = prompt | llm
            response = chain.invoke({"markdown": result.markdown})
            logging.info(f"LLM response received, content length: {len(response.content)}")
            
            
            # Extract the JSON content from the response
            try:
                logging.info("Processing LLM response")
                # Remove markdown code block syntax if present
                content = response.content
                if '```json' in content:
                    logging.debug("Removing markdown code block syntax")
                    content = content.split('```json\n')[1].split('```')[0]
                
                logging.info("Parsing JSON response")
                articles = json.loads(content)
                domain = urlparse(url).netloc
                base_url = f"https://{domain}"
                logging.debug(f"Base URL determined as: {base_url}")
                
                # Format into a more readable dictionary
                logging.info("Converting articles to dictionary format")
                article_dict = {}
                for article in articles:
                    if isinstance(article, dict) and 'url' in article and 'title' in article:
                        article_url = article['url']
                        # Handle relative URLs
                        if not article_url.startswith(('http://', 'https://')):
                            logging.debug(f"Converting relative URL to absolute: {article_url}")
                            if article_url.startswith('/'):
                                article_url = f"{base_url}{article_url}"
                            else:
                                article_url = f"{base_url}/{article_url}"
                        
                        article_dict[article_url] = article['title']
            
                logging.info(f"Successfully extracted {len(article_dict)} articles from the page")                
                return article_dict
                
                
            except Exception as e:
                logging.error(f"Error processing response: {str(e)}")
                raise e
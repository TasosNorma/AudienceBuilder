import asyncio
import os
import json
from crawl4ai import AsyncWebCrawler, WebCrawler
from crawl4ai.extraction_strategy import LLMExtractionStrategy 
from pydantic import BaseModel, Field
from urllib.parse import urlparse
import logging
import warnings
import urllib3
# This Class is to help the URL extraction function
class UrlSchema(BaseModel):
    title: str = Field(..., description='The title of the link, indicative')
    url: str = Field(..., description='The actual url')

# This function takes a url and tries to re-create the article of the URL as realistically as possible.
async def extract_article_content(url,api_key):
    try:
        async with AsyncWebCrawler(verbose=False, log_level=logging.ERROR, silent=True) as crawler:
            print("Trying to extract the content from the article")
            try:
                result = await crawler.arun(
                    url=url,
                    word_count_threshold=5,
                    extraction_strategy=LLMExtractionStrategy(
                        provider='openai/gpt-4o-mini',
                        api_token=api_key,
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
            return f"Error: Failed to format extracted content. Reason: {str(e)}"
    except Exception as e:
        print(f"Unexpected error processing article: {str(e)}")
        return f"Error: Unexpected error while processing {url}"

# This function takes a url and returns all the relevant urls referenced in the article of this URL
async def extract_relevant_urls(url,api_key):
    domain = urlparse(url).netloc 
    base_url = f"https://{domain}"
    formatted_urls = []
    async with AsyncWebCrawler(verbose = True, log_level=logging.ERROR) as crawler:
        result = await crawler.arun(
            url=url,
            extraction_strategy=LLMExtractionStrategy(
                provider='openai/gpt-4o-mini',
                api_token=api_key,
                schema= UrlSchema.model_json_schema(),
                extraction_type='schema',
                instruction="""You are given an HTML document representing an article. 
                INSTRUCTIONS:
                1. Identify all relevant articles that the current article links to. These will be <a> tags located in the main content area of the article.
                2. Exclude any links that are not relevant to the main content (ignore nav menus, ads, headers, footers).
                3. Extract only the top 5 most relevants, don't return more than 5 articles
                3. Output the final result as a JSON array, where each element is an object with "title" and "url" fields.
                Example:
                [{
                    "title": "Article Title",
                    "url": "https://example.com/article-url"
                }]
                """
            ),
            bypass_cache = True,
            silent=True
        )
        urls = json.loads(result.extracted_content)
        for article in urls:
            article_url = article['url']
            if article_url.startswith('/'):
                article_url = f"{base_url}{article_url}"
                # print(article_url)
            formatted_urls.append(article_url)
        print(formatted_urls)
        return formatted_urls

# This function takes a url and returns a small summary
async def write_small_summary(url):
    async with AsyncWebCrawler(verbose = True) as crawler:
        result = await crawler.arun(
            url=url,
            word_count_threshold=5,
            extraction_strategy=LLMExtractionStrategy(
                provider='openai/gpt-4o-mini',
                api_token=os.getenv('OPENAI_API_KEY'),
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
            bypass_cache = True
        )
        
        content_blocks = json.loads(result.extracted_content)
        formatted_article = []
        for block in content_blocks:
            if 'content' in block:
                formatted_article.extend(block['content'])
    
        summary = "\n\n".join(formatted_article)
        return summary.strip()

# This function takes the url and returns a dictionary of all relevant URLs and their Summary. 
async def get_summaries_of_urls(url:str,api_key:str) -> dict:
    urls = await extract_relevant_urls(url,api_key)
    summaries = {}
    for article_url in urls:
        try:
            summary = await write_small_summary(article_url)
            summaries[article_url]= summary
        except Exception as e:
            print(f"Error processing {article_url}: {str(e)}")
            summaries[article_url] = "Error: Could not generate summary"
    return summaries

# This function takes a dictionary from get_summaries_of_urls and returns a string in nice format to passed into another prompt
async def get_formatted_summaries(url: str,api_key:str) -> str:
    summaries = await get_summaries_of_urls(url,api_key)
    formatted_output = []
    for index, (url, summary) in enumerate(summaries.items(), 1):
        article_block = f"""**Article: {index}**
URL: {url}
Content: {summary}

---
"""
        formatted_output.append(article_block)
    
    return "\n".join(formatted_output)

# This function takes a url and returns all the articles depicted in the url, url might be the techrunch main page.
async def extract_all_articles_from_page(url:str,api_key) -> dict:
    async with AsyncWebCrawler(verbose=False, log_level=logging.ERROR) as crawler:
        result = await crawler.arun(
            url=url,
            extraction_strategy=LLMExtractionStrategy(
                provider='openai/gpt-4o-mini',
                api_token=api_key,
                schema=UrlSchema.model_json_schema(),
                extraction_type='schema',
                instruction="""You are analyzing a webpage that contains multiple articles (like a blog index or news homepage).

INSTRUCTIONS:
1. Identify all article links on the page
2. For each article found, extract:
   - The complete URL (if relative, note it will be handled later)
   - The article title
3. Focus on main content area articles
4. Exclude:
   - Navigation menu links
   - Footer links
   - Sidebar links
   - Advertisement links
   - Author pages
   - Category/tag pages
5. Return results as a JSON array of objects with 'url' and 'title' fields

Example output:
[{
    "url": "/blog/article-1",
    "title": "First Article Title"
}, {
    "url": "https://example.com/article-2",
    "title": "Second Article Title"
}]"""
            ),
            bypass_cache=True,
            silent=True
        )
        # Parse the results
        articles = json.loads(result.extracted_content)
        
        # Process URLs to ensure they're absolute
        domain = urlparse(url).netloc
        base_url = f"https://{domain}"
        article_dict = {}
        for article in articles:
            article_url = article['url']
            # Convert relative URLs to absolute
            if article_url.startswith('/'):
                article_url = f"{base_url}{article_url}"
            article_dict[article_url] = article['title']
            
        return article_dict

async def main():
    articles = await extract_all_articles_from_page('https://www.snowflake.com/en/blog/')
    for url, title in articles.items():
        print(f"Title: {title}")
        print(f"URL: {url}")
        print("---")
# Example usage:
if __name__ == "__main__":
    asyncio.run(main())


class Crawler:
    def __init__(self,api_key) -> None:
        self.api_key = api_key
        print("Initializing WebCrawler...")
        crawler_strategy = LLMExtractionStrategy(verbose=True)
        self.crawler = WebCrawler(crawler_strategy=crawler_strategy, verbose=True)
        print("WebCrawler initialized, starting warmup...")
        try:
            self.crawler.warmup()
            print("Warmup completed successfully")
        except Exception as e:
            print(f"Error during crawler warmup: {str(e)}")
            raise

    # This function takes a url and tries to re-create the article of the URL as realistically as possible. 
    def extract_article_content(self,url):
        try:
            print("Trying to extract the content from the article")
            result = self.crawler.run(
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
        except Exception as e:
            print(f"Error extracting content from article: {str(e)}")
            raise
        try:
            content_blocks = json.loads(result.extracted_content)
            formatted_article = []
            for block in content_blocks:
                if 'content' in block:
                    formatted_article.extend(block['content'])
            
            article = "\n\n".join(formatted_article)
        except Exception as e:
            print(f"Error formatting article content: {str(e)}")
            raise
        return article

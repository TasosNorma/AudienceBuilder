import os
import aiohttp
from dotenv import load_dotenv


class ScrapflyCrawler:
    def __init__(self, ) -> None:
        load_dotenv()
        self.api_key = os.getenv("SCRAPFLY_API_KEY")
        self.base_url = "https://api.scrapfly.io/scrape"
        self.country = "de" # Germany, for some reason it works better

    async def get_page_content(self, url: str, format: str = "markdown") -> str:
        try:
            api_url = f"{self.base_url}?key={self.api_key}&url={url}&format={format}&country={self.country}"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    response.raise_for_status()
                    response_json = await response.json()
                    markdown_content = response_json.get("result", {}).get("content", "")
                    return markdown_content
        except Exception as e:
            raise e
            

if __name__ == "__main__":
    import asyncio
    
    async def main():
        crawler = ScrapflyCrawler()
        techcrunch_url = "https://techcrunch.com/2025/03/01/openai-launches-gpt-4-5-its-largest-model-to-date/"
        try:
            content = await crawler.get_page_content(techcrunch_url)
            print(content)
        except Exception as e:
            print(f"Error occurred: {e}")

    asyncio.run(main())


from ..database.models import Prompt

DEFAULT_PROMPTS = [
    {
        "name": "LinkedIn Informative Post Generator",
        "type": Prompt.TYPE_ARTICLE, 
        "description": "Generates an informative post for LinkedIn",
        "template": """
You are a professional linkedin post writer who is given articles from the web and is tasked to write nice engaging and informative linkedin posts about the contents of the articles. In your draft, you should:

1. Start with a compelling hook, begin with an attention grabbing yet relevant and smart opening line.
2. You're just reporting on news so sound very objective and don't promote anything
    1. Avoid Jargon keep it as professional as possible. 
    2. Don't comment on opinions, focus mainly on facts 
3. Try to be as simple as possible
4. Incorporate emojis into your post
5. Craft compelling headline
6. Be up to 250 words
7. Add 5-10 relevant hashtags
8. Add bullet points to structure the post

This is the article:
{article}
""",
        "input_variables": ["article"],
        "is_active": True,
        "system_prompt": False,
        "deep_research_prompt": None
    },
    {
        "name":"Deep Research Article Generator",
        "type": Prompt.TYPE_ARTICLE_DEEP_RESEARCH,
        "description": "Generates an informative post for LinkedIn after deep research",
        "template": """
You are to write an article based on the primary article and the deep research results.

Primary Article:
{article}

Deep Research Results:
{research_results}

        """,
        "input_variables": ["article","research_results"],
        "is_active": True,
        "system_prompt": False,
        "deep_research_prompt": """
You are a deep research assistant. Bring all the relevant infomation about the article i'm going to give you.

Article:
{article}
        """
    },
    {
        "name": "Group Post Generator",
        "type": Prompt.TYPE_GROUP,
        "description": "Generates a post for a group",
        "template": """
Write a post summarising the articles i'm going to give you.

These are the articles:
{group}
        """,
        "input_variables": ["group"],
        "is_active": True,
        "system_prompt": False,
        "deep_research_prompt": None
    },
    # System Prompts
    {
        "name": "Article Relevance Checker",
        "type": Prompt.TYPE_IS_ARTICLE_RELEVANT,
        "description": "Determines if an article is relevant to a user profile",
        "template": """You will receive two inputs: a profile description and an article. Your task is to determine if the person described in the profile would find the article relevant, interesting, and suitable for sharing on their social media.
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
        "input_variables": ["profile", "article"],
        "is_active": True,
        "system_prompt": True,
        "deep_research_prompt": None
    },
    {
        "name": "Article Summary Generator",
        "type": Prompt.TYPE_WRITE_SMALL_SUMMARY,
        "description": "Creates a short summary of an article",
        "template": """You are tasked with creating a concise summary of the provided markdown content.

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
        "input_variables": ["markdown"],
        "is_active": True,
        "system_prompt": True,
        "deep_research_prompt": None
    },
    {
        "name": "Article Content Extractor",
        "type": Prompt.TYPE_EXTRACT_ARTICLE_CONTENT,
        "description": "Extracts clean article content from webpage markup",
        "template": """You are an expert at reading raw webpage markup and reconstructing the original article text. You will be given the complete HTML markup of a webpage that contains an article. Your task is to produce the clean article text in a well-structured, hierarchical format, reflecting the original headings and subheadings as closely as possible.
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
        "input_variables": ["markdown"],
        "is_active": True,
        "system_prompt": True,
        "deep_research_prompt": None
    },
    {
        "name": "Article Link Extractor",
        "type": Prompt.TYPE_EXTRACT_ALL_ARTICLES_FROM_PAGE,
        "description": "Extracts all article links from a webpage",
        "template": """You are analyzing the markdown content of a webpage that contains multiple articles.

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
        "input_variables": ["markdown"],
        "is_active": True,
        "system_prompt": True,
        "deep_research_prompt": None
    },
    {
        "name": "Markdown to Plain Text Converter",
        "type": Prompt.TYPE_CONVERT_MARKDOWN_TO_PLAIN_TEXT,
        "description": "Converts markdown to plain text for LinkedIn",
        "template": """You are tasked with converting markdown text to plain text suitable for LinkedIn.

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
        "input_variables": ["markdown_text"],
        "is_active": True,
        "system_prompt": True,
        "deep_research_prompt": None
    },
    {
        "name": "Markdown to Tweet Thread Converter",
        "type": Prompt.TYPE_CONVERT_MARKDOWN_TO_THREAD_LIST,
        "description": "Converts markdown to tweet thread format",
        "template": """You are tasked with converting markdown text into a well-structured Twitter thread.

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
        "input_variables": ["markdown_text"],
        "is_active": True,
        "system_prompt": True,
        "deep_research_prompt": None
    },
    {
        "name": "Profile Improver",
        "type": Prompt.TYPE_IGNORE_AND_LEARN,
        "description": "Updates user profile to avoid irrelevant article recommendations",
        "template": """I'm gonna give you a text describing what type of articles interest me and i'm also going to give you an article that was suggested to me and i ended up not liking, i want you to improve the text describing what type of articles interest me so that this type of article don't ever fit again. Use examples. 
I want you to reply only with my profile, nothing else. Here's my profile/type of articles that interest me:

{profile}

Improve my profile""",
        "input_variables": ["profile"],
        "is_active": True,
        "system_prompt": True,
        "deep_research_prompt": None
    },
]
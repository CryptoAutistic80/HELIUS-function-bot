import httpx
import json
import yfinance as yf
import pandas as pd
import aiohttp
import os
import datetime 
import asyncio
import re

from main import NEWS_API_KEY
from main import WOLFRAM_ID

async def query_wolfram_alpha(queries):
    base_url = "https://www.wolframalpha.com/api/v1/llm-api"
    results = {}

    def remove_urls(text):
        return re.sub(r'http\S+', '', text)

    async with httpx.AsyncClient() as client:
        for query in queries:
            params = {
                "input": query,
                "appid": WOLFRAM_ID
            }
            response = await client.get(base_url, params=params)
            response_text_no_urls = remove_urls(response.text)
            if response.status_code == 200:
                try:
                    results[query] = json.loads(response_text_no_urls)
                except json.JSONDecodeError:
                    results[query] = {"error": "Failed to decode JSON", "response_text": response_text_no_urls}
            elif response.status_code == 502:
                results[query] = {"error": "502 Bad Gateway from Wolfram Alpha"}
            else:
                results[query] = {"error": f"Failed to query Wolfram Alpha, received HTTP {response.status_code}"}

    return results


async def get_stock_info(tickers, info_types):
    result = {}

    for ticker in tickers:
        stock_info = yf.Ticker(ticker)
        ticker_result = {}

        try:
            if "current_price" in info_types:
                stock_history = stock_info.history(period="1d")
                ticker_result["current_price"] = stock_history["Close"].iloc[0]

            if "dividends" in info_types:
                dividends_df = stock_info.dividends.reset_index()
                dividends_df['Date'] = dividends_df['Date'].astype(str)
                ticker_result["dividends"] = dividends_df.to_dict(orient='list')

            if "splits" in info_types:
                splits_df = stock_info.splits.reset_index()
                splits_df['Date'] = splits_df['Date'].astype(str)
                ticker_result["splits"] = splits_df.to_dict(orient='list')

            if "company_info" in info_types:
                ticker_result["company_info"] = stock_info.info

            if "financials" in info_types:
                financials_df = stock_info.financials.reset_index()
                financials_df['Date'] = financials_df['Date'].astype(str)
                ticker_result["financials"] = financials_df.to_dict(orient='list')

            if "sustainability" in info_types:
                sustainability_df = stock_info.sustainability.reset_index()
                ticker_result["sustainability"] = sustainability_df.to_dict(orient='list')

            if "recommendations" in info_types:
                rec = stock_info.recommendations
                if isinstance(rec, pd.DataFrame):
                    rec = rec.reset_index()
                    rec['Date'] = rec['Date'].astype(str)
                    ticker_result["recommendations"] = rec.to_dict(orient='list')
                elif isinstance(rec, dict):
                    ticker_result["recommendations"] = rec
                else:
                    ticker_result["recommendations"] = str(rec)

            result[ticker] = ticker_result

        except Exception as e:
            result[ticker] = {"error": str(e)}

    return result



async def fetch_news_articles(session, query=None, sources=None, domains=None, from_date=None, to_date=None, 
                         language='en', sort_by='relevancy', page=1, category=None, country=None):
    """
    Fetch articles based on the given parameters.

    Parameters:
    query (str, optional): The query string for searching articles.
    sources (str, optional): A comma-separated string of news sources.
    domains (str, optional): A comma-separated string of domains.
    from_date (str, optional): The start date for fetching articles (format: 'YYYY-MM-DD').
    to_date (str, optional): The end date for fetching articles (format: 'YYYY-MM-DD').
    language (str, optional): The language of the articles. Defaults to 'en'.
    sort_by (str, optional): The criterion for sorting articles. Defaults to 'relevancy'.
    page (int, optional): The page number for paginated results. Defaults to 1.
    category (str, optional): The category of news.
    country (str, optional): The country of news sources.

    Returns:
    dict: A dictionary containing the fetched articles.
    """
    url = 'https://newsapi.org/v2/top-headlines' if category or country else 'https://newsapi.org/v2/everything'
    params = {
        'apiKey': NEWS_API_KEY,
        'q': query,
        'sources': sources,
        'domains': domains,
        'from': from_date,
        'to': to_date,
        'language': language,
        'sortBy': sort_by,
        'page': page,
        'category': category,
        'country': country
    }
    try:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                articles = await resp.json()
                return articles
            else:
                print(f"An error occurred: {resp.status}")
                return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
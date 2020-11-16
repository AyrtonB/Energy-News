from __future__ import absolute_import

import os
import json
import shutil
import requests
import numpy as np
import pandas as pd
from .scrapers import carbonbrief, bbc

"""
Scraping & Saving from Individual Sources
"""
filepath_to_scraper_func = {
    'carbon_brief': {
        'daily_briefing.json': carbonbrief.extract_daily_briefing,
        'current_articles.json': carbonbrief.retrieve_all_current_articles,        
    },
    'bbc': {
        'current_articles.json': bbc.retrieve_all_current_articles 
    },
}

def scrape_and_save_data(data_dir, filepath_to_scraper_func=filepath_to_scraper_func):
    for source in filepath_to_scraper_func.keys():
        if os.path.isdir(f'{data_dir}/{source}') == False:
            os.mkdir(f'{data_dir}/{source}')
        
        for filename, scraper_func in filepath_to_scraper_func[source].items():
            articles = scraper_func()
            
            if filename == 'current_articles.json':
                for article in articles:
                    article.update( {'source': source})

            with open(f'{data_dir}/{source}/{filename}', 'w') as fp:
                json.dump(articles, fp)
                
    return
                
def update_readme_time(readme_fp, 
                       splitter='Last updated: ', 
                       dt_format='%Y-%m-%d %H:%M'):
    
    with open(readme_fp, 'r') as readme:
        txt = readme.read()
    
    start, end = txt.split(splitter)
    old_date = end[:16]
    end = end.split(old_date)[1]
    new_date = pd.Timestamp.now().strftime(dt_format)
    
    new_txt = start + splitter + new_date + end
    
    with open(readme_fp, 'w') as readme:
        readme.write(new_txt)
        
    return


"""
Combining Articles from Different Sources
"""
def format_tags(df_articles):
    tag_source_cols = ['category', 'source', 'section']
    all_tags = []

    for row in df_articles.itertuples():
        row_tags = []

        for tag_source_col in tag_source_cols:
            tag = getattr(row, tag_source_col)

            if tag is not np.nan:
                tag = tag.lower().replace('_', ' ').replace('-', ' ').strip()
                row_tags += [tag]

        row_tags_str = '\n  - '+'\n  - '.join(row_tags)
        all_tags += [row_tags_str]
        
    df_articles['tags'] = pd.Series(all_tags, index=df_articles.index)
        
    return df_articles

def retrieve_local_current_articles(data_path, sources):
    current_articles = []
    
    for source in sources:
        assert 'current_articles.json' in os.listdir(f'{data_path}/{source}'), 'current_articles.json is not in the source directory'
        with open(f'{data_path}/{source}/current_articles.json', 'r') as fp:
            current_articles += json.load(fp)
            
    return current_articles

def retrieve_github_current_articles(sources):
    current_articles = []
    
    for source in sources:
        articles_url = f'https://raw.githubusercontent.com/AyrtonB/Energy-News/main/data/{source}/current_articles.json'
        articles_json = requests.get(articles_url).text
        current_articles += json.loads(articles_json)     
    
    return current_articles

def combine_current_articles(data_path=None, sources=filepath_to_scraper_func.keys()):
    # Retrieving articles
    if data_path is not None:
        current_articles = retrieve_local_current_articles(data_path, sources)
    else:
        current_articles = retrieve_github_current_articles(sources)
        
    # Sorting on date
    cols_to_keep = ['title', 'date', 'lead', 'article_url', 'image_url', 'source', 'tags']
    current_articles = list(pd
                            .DataFrame(current_articles)
                            .sort_values('date', ascending=False)
                            .pipe(lambda df: df.assign(title=df['title'].str.replace(':', ' - ')))
                            .pipe(format_tags)
                            [cols_to_keep]
                            .fillna('')
                            .T
                            .to_dict()
                            .values()
                           )
    
    return current_articles

article_to_md_txt = lambda article: f"""---
title: {article['title']}
date: {article['date']}
tags: {article['tags']}
source: {article['source']}
image_url: {article['image_url']}
lead: {article['lead']}
article_url: {article['article_url']}
---

---
"""


"""
Saving Markdown
"""
def rebuild_posts(current_articles, docs_dir):        
    posts_dir = f'{docs_dir}/_posts'
    
    if os.path.exists(posts_dir):
        shutil.rmtree(posts_dir)
    
    if os.path.exists(docs_dir) == False:
        os.mkdir(docs_dir)
        
    os.mkdir(posts_dir)
        
    for idx, current_article in enumerate(current_articles):
        article_md_txt = article_to_md_txt(current_article)
        
        try:
            with open(f'{posts_dir}/{idx}.md', 'w', encoding='utf-8') as article_md:
                article_md.write(article_md_txt)
        except:
            print(f"{current_article['title']} could not be processed")
        
    return
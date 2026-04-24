#!/usr/bin/env python3
"""
Telegram Bot Username Copier - Username → Source → Clone
Authorized Pentest Tool Only
"""

import asyncio
import aiohttp
import re
import os
import json
from github import Github
from pathlib import Path
import logging

class BotUsernameCopier:
    def __init__(self, github_token):
        self.gh = Github(github_token)
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, *args):
        await self.session.close()
    
    async def search_bot_repos(self, bot_username):
        """Search GitHub for exact bot source by username"""
        queries = [
            f'"{bot_username}" bot token',
            f'"{bot_username}" pyTelegramBotAPI',
            f'"{bot_username}" python-telegram-bot',
            f'"{bot_username}" telegram.ext',
            f'"{bot_username}" TeleBot',
            f'"{bot_username}" in:path main.py',
        ]
        
        all_repos = []
        for query in queries:
            try:
                results = self.gh.search_repositories(
                    query=query, 
                    sort='updated', 
                    order='desc'
                )
                all_repos.extend(list(results)[:10])
            except:
                continue
        
        # Filter & rank by relevance
        ranked_repos = []
        for repo in all_repos:
            score = 0
            desc_lower = repo.description.lower() if repo.description else ''
            if bot_username.lower() in desc_lower:
                score += 10
            if 'telegram' in desc_lower or 'bot' in desc_lower:
                score += 5
                
            ranked_repos.append((repo, score))
        
        return sorted(ranked_repos, key=lambda x: x[1], reverse=True)
    
    async def download_repo(self, repo_url, temp_dir):
        """Download repo contents"""
        async with self.session.get(repo_url) as resp:
            if resp.status != 200:
                return None
                
            zip_content = await resp.read()
            zip_path = f"{temp_dir}/repo.zip"
            
            with open(zip_path, 'wb') as f:
                f.write(zip_content)
            
            extract_dir = f"{temp_dir}/extracted"
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            os.remove(zip_path)
            return extract_dir
    
    def extract_bot_token(self, code):
        """Extract Telegram bot token"""
        pattern = r'bot[:\s]*["\']([0-9]{9,12}:[A-Za-z0-9_-]{35})["\']'
        matches = re.findall(pattern, code, re.IGNORECASE | re.MULTILINE)
        return matches[0] if matches else None
    
    def analyze_source(self, source_dir):
        """Complete source analysis"""
        python_files = []
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        python_files.append({
                            'path': filepath,
                            'content': content,
                            'token': self.extract_bot_token(content)
                        })
        
        # Framework detection
        frameworks = {
            'ptb20': 'Application.builder' in ' '.join(f['content'] for f in python_files),
            'ptb13': 'Updater' in ' '.join(f['content'] for f in python_files),
            'telebot': 'TeleBot' in ' '.join(f['content'] for f in python_files)
        }
        
        return {
            'files': python_files,
            'framework': max(frameworks, key=frameworks.get) if any(frameworks.values()) else 'unknown',
            'token_found': any(f['token'] for f in python_files),
            'total_files': len(python_files)
        }
    
    async def create_clone(self, analysis, clone_dir, new_token):
        """Create identical clone with your token"""
        os.makedirs(clone_dir, exist_ok=True)
        
        # Copy all files
        for file_info in analysis['files']:
            target_path = file_info['path'].replace('/extracted/', f"/{clone_dir}/")
            Path(target_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Replace token with yours
            content = file_info['content']
            if new_token:
                old_token = file_info.get('token')
                if old_token:
                    content = re.sub(
                        rf'["\']{re.escape(old_token)}["\']',
                        f'"{new_token}"',
                        content
                    )
            
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # Create requirements.txt
        reqs = self.generate_requirements(analysis['framework'])
        with open(f"{clone_dir}/requirements.txt", 'w') as f:
            f.write(reqs)
        
        return clone_dir
    
    def generate_requirements(self, framework):
        """Generate correct requirements"""
        mapping = {
            'ptb20': 'python-telegram-bot>=20.0',
            'ptb13': 'python-telegram-bot==13.15',
            'telebot': 'pyTelegramBotAPI'
        }
        return mapping.get(framework, 'python-telegram-bot')
    
    async def copy_bot(self, bot_username, new_token=None, github_token=None):
        """Main: username → clone"""
        repos = await self.search_bot_repos(bot_username)
        
        if not repos:
            print("❌ No source found for", bot_username)
            return None
        
        print(f"🔍 Found {len(repos)} potential sources for @{bot_username}")
        
        for i, (repo, score) in enumerate(repos[:5]):
            print(f"\n[{i+1}] {repo.full_name} (score: {score})")
            print(f"   Stars: {repo.stargazers_count} | Updated: {repo.updated_at}")
            
            temp_dir = f"temp_{i}"
            os.makedirs(temp_dir, exist_ok=True)
            
            try:
                # Download repo
                zip_url = repo.get_archive_url(archive_format='zipball')
                source_dir = await self.download_repo(zip_url, temp_dir)
                
                if not source_dir:
                    continue
                
                # Analyze
                analysis = self.analyze_source(source_dir)
                print(f"   Files: {analysis['total_files']} | Framework: {analysis['framework']}")
                print(f"   Token: {'✅' if analysis['token_found'] else '❌'}")
                
                if analysis['total_files'] > 0:
                    # CREATE CLONE
                    clone_dir = f"clone_{bot_username}_{i}"
                    await self.create_clone(analysis, clone_dir, new_token)
                    
                    print(f"✅ CLONE READY: {clone_dir}/")
                    print(f"   Run: cd {clone_dir} && pip install -r requirements.txt && python **/*.py")
                    
                    # Cleanup temp
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    
                    return clone_dir
                    
            except Exception as e:
                print(f"   ❌ Failed: {e}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                continue
        
        print("❌ No working source found")
        return None

# 🔥 ONE-LINE USAGE
async def main():
    async with BotUsernameCopier("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") as copier:
        # Just username!
        clone = await copier.copy_bot("@targetbot", new_token="8625672345:AAGHlK4qjYjhQ2Qn6Qd_x9PKAJrTQBpKpFE")
        
        if clone:
            print(f"\n🎉 Pentest clone ready: {clone}")

if __name__ == "__main__":
    asyncio.run(main())

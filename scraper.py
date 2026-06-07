import asyncio
import os
import re
import requests
from playwright.async_api import async_playwright

WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')

SEARCH_KEYWORDS = [
    '商品',
    'ショッピング',
    'コスメ',
    'ファッション',
    '食品',
    'サプリ',
    'スキンケア',
    'アクセサリー',
]

async def scrape_keyword(page, keyword):
    ads = []
    captured = []

    async def handle_response(response):
        if response.status == 200:
            try:
                text = await response.text()
                if 'page_name' in text and 'page_id' in text and len(text) > 200:
                    captured.append(text)
            except:
                pass

    page.on('response', handle_response)
    url = f'https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=JP&media_type=all&q={keyword}'

    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(4000)

        for _ in range(8):
            await page.evaluate('window.scrollBy(0, window.innerHeight)')
            await page.wait_for_timeout(1500)

        for text in captured:
            names = re.findall(r'"page_name"\s*:\s*"([^"]+)"', text)
            ids   = re.findall(r'"page_id"\s*:\s*"?(\d+)"?', text)
            for i, name in enumerate(names):
                name = name.strip()
                if name and len(name) > 1 and len(name) < 80:
                    page_id = ids[i] if i < len(ids) else ''
                    fb_url  = f'https://www.facebook.com/{page_id}' if page_id else ''
                    ads.append({'name': name, 'fbUrl': fb_url})

        if not ads:
            dom_ads = await page.evaluate('''
                () => {
                    const results = [];
                    const seen = new Set();
                    document.querySelectorAll('a[role="link"]').forEach(el => {
                        const href = el.href || '';
                        const text = (el.innerText || '').trim();
                        if (text && text.length > 1 && text.length < 80 &&
                            href.includes('facebook.com/') &&
                            !href.includes('/ads/library') &&
                            !href.includes('/help') &&
                            !href.includes('/privacy') &&
                            !href.includes('/policies')) {
                            const key = text.toLowerCase();
                            if (!seen.has(key)) {
                                seen.add(key);
                                results.push({ name: text, fbUrl: href.split('?')[0] });
                            }
                        }
                    });
                    return results;
                }
            ''')
            ads.extend(dom_ads)

    except Exception as e:
        print(f'[ERROR] keyword={keyword}: {e}')
    finally:
        page.remove_listener('response', handle_response)

    return ads


async def main():
    all_rows = []
    seen_names = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            locale='ja-JP',
            timezone_id='Asia/Tokyo',
        )
        page = await context.new_page()

        for keyword in SEARCH_KEYWORDS:
            print(f'検索中: {keyword}')
            ads = await scrape_keyword(page, keyword)
            print(f'  取得: {len(ads)}件')

            for ad in ads:
                name = ad['name'].strip()
                if name and name not in seen_names:
                    seen_names.add(name)
                    all_rows.append([
                        '', name, '', '', ad.get('fbUrl', ''), '', 'インスタ広告', '', '', '', ''
                    ])

            await asyncio.sleep(3)

        await browser.close()

    print(f'合計: {len(all_rows)}件')

    if all_rows and WEBHOOK_URL:
        try:
            res = requests.post(WEBHOOK_URL, json={'rows': all_rows}, timeout=30)
            print(f'Webhook: {res.status_code} / {res.text[:200]}')
        except Exception as e:
            print(f'Webhook エラー: {e}')

if __name__ == '__main__':
    asyncio.run(main())

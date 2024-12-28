import aiohttp
from lxml import etree
import asyncio
from charset_normalizer import from_bytes
import re


def is_valid_proxy(proxy):
    match = re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}$', proxy)
    return bool(match)


async def fetch_proxies_jhao(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/96.0.4664.110 Safari/537.36",
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    # 读取二进制内容
                    content = await response.read()
                    # 使用 charset-normalizer 检测编码
                    result = from_bytes(content).best()
                    html_text = str(result)
                    html = etree.HTML(html_text)
                    proxies = []
                    for row in html.xpath('//table//tr'):
                        try:
                            ip = row.xpath('./td[1]/text()')[0].strip()
                            port = row.xpath('./td[2]/text()')[0].strip()
                            proxy = f"{ip}:{port}"
                            if is_valid_proxy(proxy):
                                proxies.append(proxy)
                        except IndexError:
                            continue
                    return proxies
        except Exception as e:
            print(f"抓取失败: {e}")
        return []


async def test_proxy(semaphore, proxy, test_url='https://httpbin.org/get', proxy_type='http'):
    async with semaphore:
        print(f"正在测试代理 {proxy}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        test_url,
                        proxy=f'{proxy_type}://{proxy}',
                        timeout=5
                ) as response:
                    if response.status == 200:
                        print(f"代理 {proxy} 有效")
                        return True
                    else:
                        print(f"代理 {proxy} 无效，状态码: {response.status}")
                        return False
        except Exception as e:
            print(f"测试代理 {proxy} 时出错: {e}")
            return False


async def main():
    url = "http://www.ip3366.net/free/?stype=1"  # 示例代理源
    proxies = await fetch_proxies_jhao(url)
    print(f"抓取到的代理: {proxies}")

    semaphore = asyncio.Semaphore(10)  # 限制并发数为10
    tasks = [test_proxy(semaphore, proxy, test_url='https://httpbin.org/get', proxy_type='http') for proxy in proxies]
    results = await asyncio.gather(*tasks)
    valid_proxies = [proxy for proxy, is_valid in zip(proxies, results) if is_valid]
    print(f"有效的代理: {valid_proxies}")


if __name__ == "__main__":
    asyncio.run(main())

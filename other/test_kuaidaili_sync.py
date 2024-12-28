import requests
from lxml import etree

def fetch_proxies_jhao(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/96.0.4664.110 Safari/537.36",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            html = etree.HTML(response.text)
            proxies = []
            for row in html.xpath('//table//tr'):
                try:
                    ip = row.xpath('./td[1]/text()')[0].strip()
                    port = row.xpath('./td[2]/text()')[0].strip()
                    proxies.append(f"{ip}:{port}")
                except IndexError:
                    continue
            return proxies
    except Exception as e:
        print(f"抓取失败: {e}")
    return []


url = "http://www.ip3366.net/free/?stype=1"  # 示例代理源
proxies = fetch_proxies_jhao(url)
print(f"抓取到的代理: {proxies}")

import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import random
import os

# 目标网站的 URL
base_url = "https://pic.netbian.com"

# 设置请求头
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive'
}

# 抓取网页内容
def fetch_page_content(url):
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gbk'
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"获取页面失败: {e}")
        return None

# 解析网页内容，提取图片 URL
def extract_image_urls(page_content):
    if not page_content:
        return []
    try:
        soup = BeautifulSoup(page_content, 'html.parser')
        # 找到图片列表区域
        image_divs = soup.select('.slist ul li a img')
        # 提取图片URL，并进行处理
        image_urls = []
        for img in image_divs:
            if 'src' in img.attrs:
                src = img['src']
                # 确保URL格式正确
                if not src.startswith('http'):
                    if not src.startswith('/'):
                        src = '/' + src
                    image_urls.append(src)
        return image_urls
    except Exception as e:
        print(f"解析页面失败: {e}")
        return []

# 下载图片并转换为 PNG 格式
def download_and_convert_image(image_url):
    try:
        full_url = base_url + image_url if not image_url.startswith('http') else image_url
        print(f"正在下载图片: {full_url}")
        
        response = requests.get(full_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        image_data = BytesIO(response.content)
        image = Image.open(image_data)
        
        # 固定文件名为 moyun.png
        png_path = "moyun.png"
        image.save(png_path, "PNG")
        print(f"图片已成功转换并保存为 {png_path}")
    except requests.RequestException as e:
        print(f"下载图片失败: {e}")
    except Exception as e:
        print(f"处理图片失败: {e}")

# 主函数
def main():
    try:
        # 使用4K专区的URL
        page_content = fetch_page_content(base_url + "/4kfengjing/")
        if not page_content:
            return
        
        image_urls = extract_image_urls(page_content)
        if image_urls:
            print(f"找到 {len(image_urls)} 张图片")
            random_image_url = random.choice(image_urls)
            download_and_convert_image(random_image_url)
        else:
            print("未找到图片 URL")
    except Exception as e:
        print(f"程序执行出错: {e}")

if __name__ == "__main__":
    main()
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import random
import os
import time
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 支持的网站配置
SITES = {
    'netbian': {
        'base_url': "https://pic.netbian.com",
        'referer': "https://pic.netbian.com/",
        'encoding': 'gbk'
    },
    'toopic': {
        'base_url': "https://www.toopic.cn",
        'referer': "https://www.toopic.cn/4kbz/",
        'encoding': 'utf-8'
    }
}

def get_headers(site_key='netbian'):
    base_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    }
    
    if site_key == 'toopic':
        base_headers.update({
            'Host': 'www.toopic.cn',
            'Referer': SITES[site_key]['referer']
        })
    
    return base_headers

def fetch_page_content(url, site_key='netbian'):
    headers = get_headers(site_key)
    site_config = SITES[site_key]
    
    try:
        session = requests.Session()
        print(f"访问页面: {url}")
        response = session.get(url, headers=headers, timeout=10, verify=False)
        response.encoding = site_config['encoding']
        
        print(f"响应状态码: {response.status_code}")
        return response.text
    except Exception as e:
        print(f"获取页面失败: {e}")
        return None

def extract_image_urls_toopic(page_content):
    if not page_content:
        return []
    
    try:
        soup = BeautifulSoup(page_content, 'html.parser')
        image_urls = []
        
        # 打印页面结构以进行调试
        print("\n页面结构预览:")
        print(soup.prettify()[:1000])
        
        # 方法1: 查找所有图片容器
        img_containers = soup.find_all('div', class_='list-pic')
        for container in img_containers:
            # 查找图片链接
            img = container.find('img')
            if img:
                src = img.get('data-original') or img.get('src')  # 先尝试 data-original 属性
                if src:
                    if not src.startswith('http'):
                        src = SITES['toopic']['base_url'] + src
                    image_urls.append(src)
                    print(f"找到图片URL: {src}")
        
        # 方法2: 查找所有图片列表项
        list_items = soup.find_all('li', class_='item')
        for item in list_items:
            img = item.find('img')
            if img:
                src = img.get('data-original') or img.get('src')
                if src:
                    if not src.startswith('http'):
                        src = SITES['toopic']['base_url'] + src
                    if src not in image_urls:
                        image_urls.append(src)
                        print(f"找到图片URL: {src}")
            
            # 查找详情页链接
            detail_link = item.find('a')
            if detail_link:
                href = detail_link.get('href')
                if href:
                    if not href.startswith('http'):
                        href = SITES['toopic']['base_url'] + href
                    print(f"找到详情页链接: {href}")
                    # 获取详情页内容
                    detail_content = fetch_page_content(href, 'toopic')
                    if detail_content:
                        detail_soup = BeautifulSoup(detail_content, 'html.parser')
                        # 查找高清图片下载链接
                        download_link = detail_soup.find('a', class_='download-btn')
                        if download_link:
                            download_href = download_link.get('href')
                            if download_href:
                                if not download_href.startswith('http'):
                                    download_href = SITES['toopic']['base_url'] + download_href
                                if download_href not in image_urls:
                                    image_urls.append(download_href)
                                    print(f"找到高清图片下载链接: {download_href}")
        
        # 方法3: 查找所有图片标签
        all_images = soup.find_all('img')
        for img in all_images:
            src = img.get('data-original') or img.get('src')
            if src and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                if not src.startswith('http'):
                    src = SITES['toopic']['base_url'] + src
                if src not in image_urls:
                    image_urls.append(src)
                    print(f"找到图片URL: {src}")
        
        print(f"\n总共找到 {len(image_urls)} 张图片")
        return image_urls
    except Exception as e:
        print(f"解析页面失败: {e}")
        print("错误详情:", str(e))
        return []

def download_and_convert_image(image_url, site_key='netbian'):
    headers = get_headers(site_key)
    headers.update({
        'Accept': 'image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Sec-Fetch-Dest': 'image',
        'Sec-Fetch-Mode': 'no-cors',
    })
    
    try:
        print(f"正在下载图片: {image_url}")
        session = requests.Session()
        response = session.get(image_url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()
        
        content_type = response.headers.get('content-type', '')
        print(f"响应Content-Type: {content_type}")
        
        image_data = BytesIO(response.content)
        image = Image.open(image_data)
        
        # 修改为固定的文件名和路径
        png_path = "img.png"  # 直接保存在根目录下
        
        image.save(png_path, "PNG")
        print(f"图片已成功保存为: {png_path}")
        
        if os.path.exists(png_path):
            print(f"文件创建成功！大小: {os.path.getsize(png_path)} 字节")
    except Exception as e:
        print(f"处理图片失败: {e}")
        if 'response' in locals():
            print(f"响应状态码: {response.status_code}")
            print(f"响应头: {dict(response.headers)}")

def main():
    try:
        # 添加更多的 toopic.cn 入口页面
        toopic_urls = [
            f"{SITES['toopic']['base_url']}/4kbz/",
            f"{SITES['toopic']['base_url']}/4kbz/4K壁纸/",
            f"{SITES['toopic']['base_url']}/4kbz/自然风景/",
            f"{SITES['toopic']['base_url']}/4kbz/卡通动漫/",
            f"{SITES['toopic']['base_url']}/4kbz/index_1.html",  # 添加分页链接
            f"{SITES['toopic']['base_url']}/4kbz/index_2.html"
        ]
        
        for url in toopic_urls:
            print(f"\n尝试访问 toopic.cn: {url}")
            page_content = fetch_page_content(url, 'toopic')
            
            if not page_content:
                print("获取页面内容失败，尝试下一个URL")
                time.sleep(2)  # 添加延迟
                continue
            
            # 打印页面内容预览以便调试
            print("\n页面内容预览:")
            print(page_content[:500])
                
            image_urls = extract_image_urls_toopic(page_content)
            
            if image_urls:
                random_image_url = random.choice(image_urls)
                print(f"随机选择的图片URL: {random_image_url}")
                download_and_convert_image(random_image_url, 'toopic')
                break
            else:
                print("未找到图片 URL，尝试下一个URL")
                time.sleep(2)  # 添加延迟
        else:
            print("所有URL都尝试失败")
    except Exception as e:
        print(f"程序执行出错: {e}")
        print("错误详情:", str(e))

if __name__ == "__main__":
    main()
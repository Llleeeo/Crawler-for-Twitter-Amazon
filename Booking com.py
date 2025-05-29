import os
import time
import random
import uuid
import logging
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from PIL import Image
from io import BytesIO
from bs4 import BeautifulSoup
import concurrent.futures
import json
import xlwt

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('booking_images.log'),
        logging.StreamHandler()
    ]
)

# 创建图片保存目录
image_dir = 'booking_attractions_images'
if not os.path.exists(image_dir):
    os.makedirs(image_dir)
    logging.info(f"创建图片保存目录: {image_dir}")

# 设置请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Accept': 'image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.booking.com/',
    'Connection': 'keep-alive',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache'
}


def setup_driver():
    """配置和初始化Chrome WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1400,900")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--lang=en-US")

    # 设置用户代理
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    chrome_options.add_argument(f'user-agent={user_agent}')

    # 初始化WebDriver
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except WebDriverException as e:
        logging.error(f"WebDriver初始化失败: {str(e)}")
        raise


def extract_image_urls(html_content):
    """从HTML内容中提取所有图片URL"""
    soup = BeautifulSoup(html_content, 'html.parser')
    image_urls = []

    # 查找所有图片标签
    img_tags = soup.find_all('img')
    logging.info(f"找到 {len(img_tags)} 个图片标签")

    for img in img_tags:
        try:
            # 获取图片URL - 优先使用data-src属性（延迟加载图片）
            img_url = img.get('data-src') or img.get('src')

            # 跳过无效URL
            if not img_url or 'data:image' in img_url or 'base64' in img_url:
                continue

            # 确保URL完整
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            elif img_url.startswith('/'):
                img_url = 'https://www.booking.com' + img_url

            # 添加到列表
            if img_url not in image_urls:
                image_urls.append(img_url)
        except Exception as e:
            logging.error(f"处理图片标签时出错: {str(e)}")
            continue

    return image_urls


def download_single_image(img_url, max_retries=3):
    """下载并保存单个图片"""
    for attempt in range(max_retries):
        try:
            response = requests.get(img_url, headers=HEADERS, timeout=10)
            response.raise_for_status()

            # 检查图片格式
            content_type = response.headers.get('Content-Type', '')
            if 'image' not in content_type:
                logging.warning(f"URL不是图片: {img_url} (Content-Type: {content_type})")
                return None

            # 打开图片并保存
            image = Image.open(BytesIO(response.content))

            # 生成唯一文件名
            filename = f"{uuid.uuid4().hex[:8]}.jpg"
            filepath = os.path.join(image_dir, filename)

            # 保存为JPEG
            image.save(filepath, "JPEG")
            logging.info(f"图片下载成功: {filename} (原始URL: {img_url})")
            return filepath
        except requests.exceptions.RequestException as e:
            logging.warning(f"图片下载失败 (尝试 {attempt + 1}/{max_retries}): {img_url} - {str(e)}")
            time.sleep(random.uniform(1, 3))
        except Exception as e:
            logging.error(f"处理图片时出错: {img_url} - {str(e)}")
            break

    return None


def download_images_concurrently(image_urls, max_workers=8):
    """使用线程池并发下载图片"""
    downloaded_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(download_single_image, url): url for url in image_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                if result:
                    downloaded_count += 1
            except Exception as e:
                logging.error(f"图片下载异常: {url} - {str(e)}")

    return downloaded_count


def save_image_urls_to_excel(image_urls, filename):
    """将图片URL保存到Excel"""
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("图片URL")

    # 设置列标题
    sheet.write(0, 0, "序号")
    sheet.write(0, 1, "图片URL")

    # 写入数据
    for i, url in enumerate(image_urls, 1):
        sheet.write(i, 0, i)
        sheet.write(i, 1, url)

    workbook.save(filename)
    logging.info(f"图片URL已保存到 {filename}")


def scroll_to_load_more(driver, max_scrolls=50):
    """滚动页面以加载更多内容"""
    seen_image_urls = set()
    all_image_urls = []

    # 循环控制参数
    no_new_data_count = 0
    max_no_new_rounds = 5

    logging.info("开始滚动页面以加载更多内容...")

    for scroll_count in range(1, max_scrolls + 1):
        # 滚动到页面底部
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)
        logging.info(f"执行滚动 #{scroll_count}")

        # 随机等待时间 (模拟人类浏览)
        wait_time = random.uniform(2, 4)
        time.sleep(wait_time)

        # 检查是否有新内容加载
        try:
            # 获取当前页面HTML
            html_content = driver.page_source

            # 提取当前图片URL
            current_image_urls = extract_image_urls(html_content)

            # 计算新图片数量
            new_urls = [url for url in current_image_urls if url not in seen_image_urls]

            if new_urls:
                logging.info(f"滚动 #{scroll_count} 后加载了 {len(new_urls)} 张新图片")

                # 更新已见集合和所有图片列表
                seen_image_urls.update(new_urls)
                all_image_urls.extend(new_urls)

                # 重置无新内容计数器
                no_new_data_count = 0
            else:
                no_new_data_count += 1
                logging.info(f"滚动 #{scroll_count} 后没有加载新图片 (连续 {no_new_data_count} 次)")

                # 检查是否达到停止条件
                if no_new_data_count >= max_no_new_rounds:
                    logging.info(f"连续 {max_no_new_rounds} 次滚动没有新内容，停止滚动")
                    break

                # 随机等待更长时间，避免频繁滚动
                time.sleep(random.uniform(3, 5))

                # 尝试滚动回顶部再滚动到底部，以触发更多内容加载
                if no_new_data_count % 2 == 0:
                    driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.HOME)
                    time.sleep(random.uniform(1, 2))

        except Exception as e:
            logging.error(f"滚动处理出错: {str(e)}")
            time.sleep(3)

    logging.info(f"滚动完成，共发现 {len(all_image_urls)} 张图片")
    return all_image_urls


def main():
    # 初始化WebDriver
    logging.info("初始化浏览器...")
    driver = setup_driver()

    # 目标URL
    target_url = "https://www.booking.com/attractions/searchresults/jp/osaka.html?adplat=www-searchresults_irene-web_shell_header-attraction-missing_creative-2ib34fEzYYgPNhzHDqbp6C&aid=304142&label=gen173nr-1FCAEoggI46AdIM1gEaMkBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuAL16tLABsACAdICJGYxMjNhYWEyLThhNjktNGU4Ny05NDA3LTgyZWIyOTJkZGRmN9gCBeACAQ&client_name=b-web-shell-bff&distribution_id=2ib34fEzYYgPNhzHDqbp6C&start_date=2025-06-13&end_date=2025-06-13&source=search_box&filter_by_ufi%5B%5D=-231169"

    try:
        # 访问目标URL
        logging.info(f"访问URL: {target_url}")
        driver.get(target_url)

        # 等待页面加载
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "img"))
        )
        logging.info("页面初始加载完成")

        # 随机等待，避免被检测
        time.sleep(random.uniform(2, 4))

        # 滚动页面以加载所有内容
        all_image_urls = scroll_to_load_more(driver)

        # 保存图片URL到Excel
        save_image_urls_to_excel(all_image_urls, "booking_image_urls.xls")

        # 下载所有图片
        logging.info("开始下载图片...")
        start_time = time.time()
        downloaded_count = download_images_concurrently(all_image_urls)
        elapsed_time = time.time() - start_time

        logging.info("\n" + "=" * 60)
        logging.info(f"图片下载完成! 总共尝试下载: {len(all_image_urls)} 张, 成功下载: {downloaded_count} 张")
        logging.info(f"耗时: {elapsed_time:.2f}秒 (平均 {elapsed_time / max(1, downloaded_count):.2f}秒/张)")

    except TimeoutException:
        logging.error("页面加载超时")
    except NoSuchElementException as e:
        logging.error(f"元素未找到: {str(e)}")
    except Exception as e:
        logging.exception(f"程序运行出错: {str(e)}")
    finally:
        # 关闭浏览器
        driver.quit()
        logging.info("浏览器已关闭")


if __name__ == "__main__":
    main()

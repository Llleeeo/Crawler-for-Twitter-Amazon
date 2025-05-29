from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
from bs4 import BeautifulSoup
import requests
import os
import time
import random
import uuid
from PIL import Image
import io
import logging
import time as time_module

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 创建图片保存目录
if not os.path.exists('allrecipes_images'):
    os.makedirs('allrecipes_images')


def download_image(img_url):
    """下载并保存食谱图片"""
    try:
        # 设置请求头模拟浏览器
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.allrecipes.com/'
        }

        # 发送图片请求
        response = requests.get(img_url, headers=headers)
        response.raise_for_status()

        # 检查图片格式并保存
        image = Image.open(io.BytesIO(response.content))
        filename = f"allrecipes_images/{uuid.uuid4().hex[:6]}.jpg"
        image.save(filename, "JPEG")
        logging.info(f"图片下载成功: {filename}")
        return filename
    except Exception as e:
        logging.error(f"下载图片失败: {img_url} - 错误: {str(e)}")
        return None


def get_image_urls(html):
    """从页面HTML中提取所有图片URL"""
    soup = BeautifulSoup(html, 'html.parser')
    image_urls = []

    # 找到所有img标签
    img_tags = soup.find_all('img')
    logging.info(f"找到 {len(img_tags)} 个图片标签")

    for img in img_tags:
        try:
            # 获取图片URL - 优先使用data-src属性（延迟加载图片）
            img_url = img.get('data-src') or img.get('src')

            # 跳过无效URL
            if not img_url or 'data:image' in img_url:
                continue

            # 确保URL完整
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            elif img_url.startswith('/'):
                img_url = 'https://www.allrecipes.com' + img_url

            # 替换为高分辨率版本
            if '_960_' in img_url:
                img_url = img_url.replace('_960_', '_2000_')
            elif '_720_' in img_url:
                img_url = img_url.replace('_720_', '_2000_')
            elif '._' in img_url:
                base_url = img_url.split('._')[0] + '._'
                img_url = base_url + 'AR-2000-1-1.jpg'

            image_urls.append(img_url)
        except Exception as e:
            logging.error(f"处理图片标签时出错: {str(e)}")
            continue

    return image_urls


def scroll_to_bottom(driver):
    """更平滑的滚动到页面底部"""
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        # 随机滚动距离模拟人类行为
        scroll_distance = random.randint(800, 1500)
        driver.execute_script(f"window.scrollBy(0, {scroll_distance});")
        time.sleep(random.uniform(0.8, 1.5))

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def go_to_next_page(driver, current_offset):
    """使用URL参数翻页或按钮点击"""
    # 方法1: 直接构造下一页URL（主要方法）
    try:
        new_offset = current_offset + 24

        # 如果已经达到96（第5页），不再翻页
        if new_offset > 96:
            logging.info("已达到最大offset(96)，停止翻页")
            return False, current_offset

        current_url = driver.current_url

        # 替换URL中的offset参数
        if 'offset=' in current_url:
            # 查找offset参数位置并替换
            parts = current_url.split('?')
            base_url = parts[0]
            query_params = parts[1] if len(parts) > 1 else ""

            # 解析查询参数
            params = {}
            if query_params:
                for param in query_params.split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        params[key] = value

            # 更新offset参数
            params['offset'] = str(new_offset)

            # 重建URL
            new_query = '&'.join([f"{k}={v}" for k, v in params.items()])
            new_url = f"{base_url}?{new_query}"
        else:
            # 如果URL中没有offset参数，添加它
            separator = '&' if '?' in current_url else '?'
            new_url = f"{current_url}{separator}offset={new_offset}"

        # 访问新URL
        driver.get(new_url)
        logging.info(f"通过URL参数翻页: offset={current_offset} -> {new_offset}")

        # 等待新页面加载
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "img"))
        )
        logging.info("新页面加载完成")
        return True, new_offset

    except Exception as e:
        logging.warning(f"URL翻页失败: {str(e)}")
        logging.info("尝试使用按钮点击方法...")

    # 方法2: 使用按钮点击（备用方法）
    max_retries = 2
    attempts = 0

    while attempts < max_retries:
        try:
            # 如果已经达到96（第5页），不再翻页
            new_offset = current_offset + 24
            if new_offset > 96:
                logging.info("已达到最大offset(96)，停止翻页")
                return False, current_offset

            # 策略1: 使用CSS选择器查找
            next_buttons = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[data-testid='pagination-link-next']"))
            )
            if next_buttons:
                next_button = next_buttons[0]
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                                      next_button)
                time.sleep(random.uniform(0.8, 1.5))
                driver.execute_script("arguments[0].click();", next_button)
                logging.info("通过CSS选择器找到下一页按钮并点击")
                return True, new_offset

            # 策略2: 使用类名查找
            next_buttons = driver.find_elements(By.CLASS_NAME, 's-pagination-next')
            if next_buttons:
                next_button = next_buttons[0]
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(random.uniform(0.5, 1.5))
                driver.execute_script("arguments[0].click();", next_button)
                logging.info("通过类名找到下一页按钮并点击")
                return True, new_offset

            # 策略3: 使用链接文本查找
            next_links = driver.find_elements(By.PARTIAL_LINK_TEXT, 'Next')
            if next_links:
                next_link = next_links[0]
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_link)
                time.sleep(random.uniform(0.5, 1.5))
                driver.execute_script("arguments[0].click();", next_link)
                logging.info("通过链接文本找到下一页按钮并点击")
                return True, new_offset

            # 策略4: 使用XPath查找
            next_buttons = driver.find_elements(By.XPATH, "//a[contains(@class, 's-pagination-next')]")
            if next_buttons:
                next_button = next_buttons[0]
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(random.uniform(0.5, 1.5))
                driver.execute_script("arguments[0].click();", next_button)
                logging.info("通过XPath找到下一页按钮并点击")
                return True, new_offset

            logging.warning("所有方法均未找到下一页按钮")
            return False, current_offset

        except StaleElementReferenceException:
            logging.warning("元素状态过期，重新尝试...")
            attempts += 1
            time.sleep(1)

        except (NoSuchElementException, TimeoutException):
            logging.info("未找到下一页按钮 - 可能已是最后一页")
            return False, current_offset

        except Exception as e:
            logging.error(f"翻页时出错: {str(e)}")
            return False, current_offset

    logging.warning("达到最大重试次数仍未成功翻页")
    return False, current_offset


def main():
    # 浏览器配置
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    options.add_argument(f'user-agent={user_agent}')

    driver = webdriver.Chrome(options=options)

    try:
        search_url = "https://www.allrecipes.com/search?q=Pizza"
        driver.get(search_url)
        logging.info("访问初始页面: %s", search_url)

        # 设置页面加载超时
        driver.set_page_load_timeout(40)

        # 等待页面主要内容加载
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "img"))
            )
        except TimeoutException:
            logging.warning("页面主要内容加载超时，继续执行...")

        # 初始化offset值
        current_offset = 0
        if 'offset=' in driver.current_url:
            try:
                offset_str = driver.current_url.split('offset=')[1].split('&')[0]
                current_offset = int(offset_str)
                logging.info(f"初始offset值: {current_offset}")
            except:
                logging.warning("无法解析初始offset值，使用0作为默认值")
                current_offset = 0
        else:
            logging.info("URL中没有offset参数，使用0作为初始值")

        total_downloaded = 0
        page_count = 0
        max_pages = 5  # 只爬取5页
        seen_urls = set()  # 用于跟踪已处理的图片URL

        # 开始计时
        start_time = time_module.time()

        # 处理所有页面
        while page_count < max_pages:
            page_count += 1
            logging.info("\n" + "=" * 50)
            logging.info("开始处理第 %d 页 (offset=%d)", page_count, current_offset)

            # 滚动加载所有内容
            scroll_to_bottom(driver)
            time.sleep(random.uniform(2, 3))

            # 获取当前页面内容
            html = driver.page_source
            image_urls = get_image_urls(html)

            # 下载当前页面的图片
            page_downloaded = 0
            for img_url in image_urls:
                if img_url not in seen_urls:
                    if download_image(img_url):
                        page_downloaded += 1
                        total_downloaded += 1
                        seen_urls.add(img_url)

            logging.info("第 %d 页完成，下载图片: %d 张，累计下载: %d 张",
                         page_count, page_downloaded, total_downloaded)

            # 如果已经是最后一页（第5页），停止翻页
            if page_count >= max_pages:
                logging.info("已达到5页，停止爬取")
                break

            # 尝试翻到下一页
            success, new_offset = go_to_next_page(driver, current_offset)
            if not success:
                logging.info("没有下一页了，停止翻页")
                break
            current_offset = new_offset

            # 随机等待一段时间，避免被检测
            time.sleep(random.uniform(2, 4))

        end_time = time_module.time()  # 结束计时
        elapsed_time = end_time - start_time  # 计算耗时
        logging.info("\n" + "=" * 50)
        logging.info("爬取完成! 共处理 %d 页，下载 %d 张图片",
                     page_count, total_downloaded)
        logging.info("最终offset值: %d", current_offset)
        logging.info("工作时间: %.2f 秒 (约 %.2f 分钟)",
                     elapsed_time, elapsed_time / 60)

    except Exception as e:
        logging.exception("程序运行出错")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
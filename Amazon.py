from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import requests
import os
import time
import random
import uuid
from PIL import Image
import io
import logging
import time as time_module  # Importing time module for timing

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 创建图片保存目录
if not os.path.exists('amazon_images'):
    os.makedirs('amazon_images')


def download_image(img_url, asin):
    """下载并保存商品图片"""
    try:
        # 设置请求头模拟浏览器
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.amazon.com/'
        }

        # 发送图片请求
        response = requests.get(img_url, headers=headers)
        response.raise_for_status()

        # 检查图片格式并保存
        image = Image.open(io.BytesIO(response.content))
        filename = f"amazon_images/{asin}_{uuid.uuid4().hex[:6]}.jpg"
        image.save(filename, "JPEG")
        logging.info(f"图片下载成功: {filename}")
        return filename
    except Exception as e:
        logging.error(f"下载图片失败: {img_url} - 错误: {str(e)}")
        return None


def get_product_data(html):
    """解析亚马逊商品数据并返回图片URL列表"""
    soup = BeautifulSoup(html, 'html.parser')
    products = soup.find_all('div', {'data-component-type': 's-search-result'})
    image_urls = []

    for product in products:
        try:
            # 获取商品唯一ID (ASIN)
            asin = product.get('data-asin')
            if not asin:
                continue

            # 查找商品图片
            img_container = product.find('img', {'class': 's-image'})
            if img_container:
                img_url = img_container.get('src')
                if img_url and 'images' in img_url:  # 验证是否为图片URL
                    # 尝试获取更高分辨率的图片
                    high_res_url = img_url.replace('._AC_UL320_.', '._AC_UL1500_.')
                    image_urls.append((high_res_url, asin))
        except Exception as e:
            logging.error(f"解析商品时出错: {str(e)}")
            continue

    return image_urls


def scroll_to_bottom(driver):
    """滚动到页面底部"""
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(random.uniform(1.5, 2.5))


def find_and_click_next_page(driver):
    """查找并点击下一页按钮"""
    try:
        next_buttons = driver.find_elements(By.CSS_SELECTOR, 'a.s-pagination-next')
        if next_buttons:
            next_button = next_buttons[0]
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            time.sleep(random.uniform(0.5, 1.5))
            driver.execute_script("arguments[0].click();", next_button)
            logging.info("通过CSS选择器找到下一页按钮并点击")
            return True

        next_buttons = driver.find_elements(By.CLASS_NAME, 's-pagination-next')
        if next_buttons:
            next_button = next_buttons[0]
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            time.sleep(random.uniform(0.5, 1.5))
            driver.execute_script("arguments[0].click();", next_button)
            logging.info("通过类名找到下一页按钮并点击")
            return True

        next_links = driver.find_elements(By.PARTIAL_LINK_TEXT, 'Next')
        if next_links:
            next_link = next_links[0]
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_link)
            time.sleep(random.uniform(0.5, 1.5))
            driver.execute_script("arguments[0].click();", next_link)
            logging.info("通过链接文本找到下一页按钮并点击")
            return True

        try:
            next_button = driver.find_element(By.XPATH, "//a[contains(@class, 's-pagination-next')]")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            time.sleep(random.uniform(0.5, 1.5))
            driver.execute_script("arguments[0].click();", next_button)
            logging.info("通过XPath找到下一页按钮并点击")
            return True
        except:
            pass

        logging.warning("所有方法均未找到下一页按钮")
        return False

    except Exception as e:
        logging.error(f"查找下一页按钮时出错: {str(e)}")
        return False


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
        search_url = "https://www.amazon.com/s?k=household+cleaning+tools&i=hpc&rh=n%3A3760901%2Cp_123%3A237711&dc&ds=v1%3AHlBzaO8xfIaSn0MCKp%2BRBs1VDSmcdVfE%2BNnNIzcT6Zc&qid=1746167441&rnid=23991400011&ref=sr_nr_p_n_feature_six_browse-bin_1"
        driver.get(search_url)
        logging.info("访问初始页面: %s", search_url)

        driver.set_page_load_timeout(40)

        total_downloaded = 0
        page_count = 1

        # Start the timer
        start_time = time_module.time()

        while True:
            logging.info("\n" + "=" * 50)
            logging.info("开始处理第 %d 页", page_count)

            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]'))
                )
            except Exception as e:
                logging.warning("等待商品加载超时: %s", str(e))

            scroll_to_bottom(driver)
            time.sleep(random.uniform(2, 3))

            html = driver.page_source
            image_urls = get_product_data(html)

            page_downloaded = 0
            for img_url, asin in image_urls:
                if download_image(img_url, asin):
                    page_downloaded += 1
                    total_downloaded += 1

            logging.info("第 %d 页完成，下载图片: %d 张，累计下载: %d 张", page_count, page_downloaded, total_downloaded)

            try:
                if not find_and_click_next_page(driver):
                    logging.info("无法找到下一页按钮，爬取结束")
                    break

                page_count += 1
                logging.info("翻页到第 %d 页", page_count)

                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]'))
                )

                time.sleep(random.uniform(3, 5))

            except Exception as e:
                logging.error("翻页过程中出错: %s", str(e))
                logging.info("爬取结束")
                break

            if page_count > 9:
                logging.info("已达到最大页数限制(50页)，爬取结束")
                break

        end_time = time_module.time()  # End the timer
        elapsed_time = end_time - start_time  # Calculate elapsed time
        logging.info("\n" + "=" * 50)
        logging.info("爬取完成! 共处理 %d 页, 下载 %d 张图片", page_count, total_downloaded)
        logging.info("工作时间: %.2f 秒", elapsed_time)  # Log the elapsed time

    except Exception as e:
        logging.exception("程序运行出错")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

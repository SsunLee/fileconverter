import requests
from bs4 import BeautifulSoup
import re
import os
import time
from urllib.parse import urlparse, unquote
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import logging
import subprocess
import json
import tempfile
import http.cookiejar

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_chrome_version():
    try:
        # Windows에서 Chrome 버전 확인
        cmd = 'reg query "HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon" /v version'
        output = subprocess.check_output(cmd, shell=True)
        version = output.decode('utf-8').strip().split()[-1]
        major_version = int(version.split('.')[0])
        logger.info(f"감지된 Chrome 버전: {version}")
        return major_version
    except Exception as e:
        logger.warning(f"Chrome 버전 감지 실패: {str(e)}")
        return None

def get_driver():
    try:
        chrome_version = get_chrome_version()
        
        options = uc.ChromeOptions()
        # 기본 옵션 설정
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--lang=ko-KR")
        
        # User-Agent 설정
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        logger.info("Chrome 드라이버 초기화 중...")
        
        # Chrome 버전에 맞는 드라이버 생성
        driver = uc.Chrome(
            options=options,
            version_main=chrome_version if chrome_version else 135,  # 감지된 버전 또는 기본값 사용
            use_subprocess=True,
            suppress_welcome=True
        )
        
        # JavaScript 실행을 통한 자동화 감지 우회
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        logger.info("Chrome 드라이버 초기화 완료")
        
        return driver
    except Exception as e:
        logger.error(f"브라우저 초기화 중 오류 발생: {str(e)}")
        return None

def safe_quit_driver(driver):
    try:
        if driver:
            driver.quit()
            logger.info("브라우저 종료 완료")
    except Exception as e:
        logger.error(f"브라우저 종료 중 오류 발생: {str(e)}")

def crawl_media_content(url, driver):
    try:
        logger.info(f"URL 크롤링 시작: {url}")
        if not driver:
            logger.error("브라우저를 시작할 수 없습니다")
            return [], None
        
        # 페이지 로드
        logger.info("페이지 로드 중...")
        driver.get(url)
        
        # Cloudflare 체크
        try:
            # 기본 페이지 로드 대기
            wait = WebDriverWait(driver, 30)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            logger.info("기본 페이지 로드 완료")
            
            # JavaScript 실행 완료 대기
            time.sleep(5)
            
            # DOM이 완전히 로드될 때까지 대기
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            logger.info("페이지 DOM 로드 완료")
            
            # 동적 컨텐츠 로드 대기
            time.sleep(10)
            
            # 재생 버튼 클릭 시도
            try:
                # 더 구체적인 재생 버튼 선택자 (이미지 기반 업데이트)
                play_button_selectors = [
                    "//button[contains(@class, 'play')]",  # 일반적인 재생 버튼
                    "//div[contains(@class, 'play-button')]", # 재생 버튼 컨테이너
                    "//span[contains(@class, 'play-icon')]", # 재생 아이콘 스팬
                    "//i[contains(@class, 'play')]", # 아이콘 폰트 사용 시
                    "//div[contains(@class, 'vjs-big-play-button')]", # Video.js 플레이어
                    "//button[@aria-label='Play']", # 접근성 레이블
                    "//div[contains(@class, 'player__play-button')]", # 특정 플레이어 클래스
                    "//div[contains(@class, 'play-overlay')]", # 재생 오버레이
                    "//svg[contains(@class, 'play-icon')]", # SVG 재생 아이콘
                    "//*[local-name()='svg'][contains(@class, 'icon-play')]", # 다른 SVG 아이콘 형태
                    "//div[contains(@class, 'play') and contains(@style, 'background')]", # 배경색 스타일 포함
                    "//button[contains(@title, 'Play') or contains(@data-title, 'Play')]", # Title 속성 기반
                    "//div[@role='button' and contains(@aria-label, 'Play')]", # Role 및 Aria 레이블
                    "//*[contains(@style, 'blue') and contains(@class, 'play')]" # 기존 파란색 + play 클래스
                ]
                
                play_button = None
                for selector in play_button_selectors:
                    try:
                        play_button = driver.find_element(By.XPATH, selector)
                        if play_button and play_button.is_displayed():
                            logger.info(f"재생 버튼 발견: {selector}")
                            break
                    except:
                        continue
                
                if play_button and play_button.is_displayed():
                    logger.info("재생 버튼 클릭 시도 중...")
                    # JavaScript를 사용하여 클릭 (더 안정적)
                    driver.execute_script("arguments[0].click();", play_button)
                    logger.info("재생 버튼 클릭 완료")
                    # 재생 후 미디어 로드를 위한 대기
                    time.sleep(5)
                else:
                    logger.warning("재생 버튼을 찾을 수 없거나 클릭할 수 없습니다")
            except Exception as e:
                logger.warning(f"재생 버튼 클릭 실패: {str(e)}")
            
            # 재생 버튼 클릭 후, 페이지 소스 및 JS 다시 로드하여 미디어 검색
            logger.info("재생 버튼 클릭 후 미디어 URL 재검색...")
            time.sleep(5) # 미디어 로드 대기 시간 추가

            page_source = driver.page_source
            js_content = driver.execute_script("return document.documentElement.outerHTML")
            soup = BeautifulSoup(page_source, 'html.parser')
            media_elements = [] # 미디어 목록 초기화

            logger.info(f"재검색 후 페이지 소스 크기: {len(page_source)} bytes")

            # Cloudflare 체크 확인 (재검색 후에도 필요할 수 있음)
            if "Checking your browser" in page_source:
                logger.info("Cloudflare 체크 감지됨, 추가 대기...")
                time.sleep(10)
                # 페이지 소스 다시 가져오기
                page_source = driver.page_source
                js_content = driver.execute_script("return document.documentElement.outerHTML")
                soup = BeautifulSoup(page_source, 'html.parser')

            # 스트리밍 URL 찾기 (정규식 패턴 확장)
            streaming_patterns = [
                r'https?://[^\s<>"]+?\.(?:ts|m3u8|mp4|webm)[^\s<>"]*',
                r'https?://[^\s<>"]+?/(?:video|media|stream)/[^\s<>"]*',
                r'https?://cdn[^\s<>"]+?/[^\s<>"]*'
            ]
            
            streaming_urls = set()
            for pattern in streaming_patterns:
                urls = re.findall(pattern, js_content)
                streaming_urls.update(urls)
            
            logger.info(f"스트리밍 URL 발견: {len(streaming_urls)}개")
            
            for stream_url in streaming_urls:
                # blob: URL 필터링
                if stream_url.startswith('blob:'):
                    logger.info(f"Blob URL 건너뜀: {stream_url}")
                    continue
                # .css URL 필터링
                if stream_url.endswith('.css'):
                    logger.info(f"CSS URL 건너뜀: {stream_url}")
                    continue
                logger.info(f"스트리밍 URL 발견: {stream_url}")
                media_elements.append({
                    'type': '스트리밍',
                    'url': stream_url,
                    'format': stream_url.split('.')[-1] if '.' in stream_url else 'unknown'
                })
            
            # 이미지 찾기
            images = soup.find_all('img')
            logger.info(f"이미지 태그 발견: {len(images)}개")
            
            for img in images:
                src = img.get('src')
                if src:
                    # blob: URL 필터링
                    if src.startswith('blob:'):
                        logger.info(f"Blob 이미지 URL 건너뜀: {src}")
                        continue
                    # .css URL 필터링
                    if src.endswith('.css'):
                        logger.info(f"CSS 이미지 URL 건너뜀: {src}")
                        continue
                    media_elements.append({
                        'type': '이미지',
                        'url': src,
                        'alt': img.get('alt', '')
                    })
            
            # 비디오 찾기 (video, iframe, source 태그)
            videos = soup.find_all(['video', 'iframe', 'source'])
            logger.info(f"비디오/iframe/source 태그 발견: {len(videos)}개")
            
            for video in videos:
                src = video.get('src') or video.get('data-src')
                if src:
                    # blob: URL 필터링
                    if src.startswith('blob:'):
                        logger.info(f"Blob 비디오/임베드 URL 건너뜀: {src}")
                        continue
                    # .css URL 필터링
                    if src.endswith('.css'):
                        logger.info(f"CSS 비디오/임베드 URL 건너뜀: {src}")
                        continue
                    media_elements.append({
                        'type': '비디오' if video.name in ['video', 'source'] else '임베드',
                        'url': src
                    })
            
            # 중복 URL 제거 (선택적이지만 권장)
            final_media_elements = []
            seen_urls = set()
            for media in media_elements:
                if media['url'] not in seen_urls:
                    final_media_elements.append(media)
                    seen_urls.add(media['url'])
                else:
                    logger.debug(f"중복 미디어 URL 제거: {media['url']}")

            # 쿠키 가져오기
            cookies = None
            try:
                cookies = driver.get_cookies()
                logger.info(f"브라우저에서 {len(cookies)}개의 쿠키를 가져왔습니다.")
                # logger.debug(f"가져온 쿠키: {cookies}") # 디버깅 시 쿠키 내용 확인
            except Exception as cookie_error:
                 logger.warning(f"쿠키를 가져오는 중 오류 발생: {cookie_error}")

            logger.info(f"총 {len(final_media_elements)}개의 유효한 미디어 요소 발견 (Blob 및 중복 제외)")
            # 미디어 목록과 쿠키 함께 반환
            return final_media_elements, cookies
            
        except TimeoutException:
            logger.error("페이지 로드 시간 초과")
            # 쿠키 없이 빈 목록 반환
            return [], None 
            
    except Exception as e:
        logger.error(f"크롤링 중 오류 발생: {str(e)}")
        # 쿠키 없이 빈 목록 반환
        return [], None 
    finally:
        # driver 종료는 여기서 하지 않음 (쿠키 사용 후 종료해야 할 수도 있음)
        # 대신 메인 로직에서 처리하도록 변경 필요
        # if driver:
        #     try:
        #         driver.quit()
        #         logger.info("브라우저 정상 종료 완료")
        #     except Exception as e:
        #         logger.error(f"브라우저 종료 중 오류 발생: {str(e)}")
        #         try:
        #             # 강제 종료 시도
        #             driver.quit()
        #         except:
        #             pass
        pass # finally 블록은 유지하되 driver 종료는 나중에

def download_image_with_requests(image_url, output_dir='downloads', referer_url=None, cookies=None):
    session = requests.Session() # 세션 객체 사용
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            # logger.info(f"이미지 다운로드 디렉토리 생성: {output_dir}") # 로그 중복 방지

        parsed_url = urlparse(image_url)
        origin_url = None
        if referer_url:
            parsed_referer = urlparse(referer_url)
            origin_url = f"{parsed_referer.scheme}://{parsed_referer.netloc}"
        elif image_url:
            parsed_image = urlparse(image_url)
            origin_url = f"{parsed_image.scheme}://{parsed_image.netloc}"

        path = unquote(parsed_url.path)
        filename = os.path.basename(path)
        if not filename or filename == '/':
            filename = f"image_{int(time.time())}{os.path.splitext(path)[1] or '.jpg'}"
        
        filename = re.sub(r'[\\/*?"<>|:]', "_", filename)
        filename = filename[:200]
        file_path = os.path.join(output_dir, filename)

        logger.info(f"이미지 다운로드 시도 (requests): {image_url}")
        logger.info(f"저장 경로: {file_path}")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
        }
        if referer_url:
            headers['Referer'] = referer_url
        if origin_url:
            headers['Origin'] = origin_url

        # 세션에 헤더 설정
        session.headers.update(headers)

        # Selenium 쿠키를 requests 세션 쿠키로 변환하여 설정
        if cookies:
            logger.debug(f"{len(cookies)}개의 쿠키를 requests 세션에 추가합니다.")
            for cookie in cookies:
                # requests 쿠키 형식에 맞게 필요한 값만 추출
                session.cookies.set(
                    name=cookie['name'],
                    value=cookie['value'],
                    domain=cookie['domain'],
                    path=cookie.get('path', '/') # path 없으면 기본값 '/'
                    # secure=cookie.get('secure', False),
                    # expires=cookie.get('expiry') # 만료 시간 처리 필요 시 추가
                )
        
        logger.debug(f"이미지 요청 헤더 (세션): {session.headers}")
        logger.debug(f"이미지 요청 쿠키 (세션): {session.cookies}")

        # 세션을 사용하여 요청 보내기
        response = session.get(image_url, stream=True, timeout=30)
        response.raise_for_status() # 오류 시 예외 발생

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        logger.info(f"이미지 다운로드 완료: {file_path}")
        return file_path

    except requests.exceptions.RequestException as e:
        logger.error(f"이미지 다운로드 중 네트워크 오류 발생: {str(e)}")
        return None
    except IOError as e:
        logger.error(f"이미지 파일 쓰기 오류 발생: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"이미지 다운로드 중 예상치 못한 오류 발생: {str(e)}", exc_info=True)
        return None
    finally:
         session.close() # 세션 닫기

def download_media(media_url, output_dir='downloads', referer_url=None, cookies=None, max_retries=3):
    # 폴더 생성
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logger.info(f"다운로드 디렉토리 생성: {output_dir}")

    logger.info(f"yt-dlp를 사용하여 다운로드 시도: {media_url}")
    
    origin_url = None
    if referer_url: # Referer URL에서 Origin 추출
        parsed_referer = urlparse(referer_url)
        origin_url = f"{parsed_referer.scheme}://{parsed_referer.netloc}"
    elif media_url: # 미디어 URL에서 Origin 추출 (대체)
        parsed_media = urlparse(media_url)
        origin_url = f"{parsed_media.scheme}://{parsed_media.netloc}"

    # yt-dlp 명령어 구성
    command = [
        'yt-dlp',
        '--no-check-certificate',
        '--no-mtime',
        # '--verbose',
    ]

    # User-Agent 추가
    command.extend(['--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0'])

    # Referer 헤더 추가
    if referer_url:
        command.extend(['--referer', referer_url])
    
    # Origin 헤더 추가
    if origin_url:
        command.extend(['--add-header', f'Origin:{origin_url}'])

    # 쿠키 처리: 임시 파일에 Netscape 형식으로 저장하고 --cookies 옵션 사용
    cookie_file_path = None
    temp_cookie_file = None
    if cookies:
        try:
            # 임시 파일 생성 (텍스트 모드, UTF-8)
            temp_cookie_file = tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', suffix='.txt')
            cookie_file_path = temp_cookie_file.name
            logger.info(f"쿠키를 임시 파일에 저장: {cookie_file_path}")
            
            # Netscape 쿠키 파일 형식 헤더 작성
            temp_cookie_file.write("# Netscape HTTP Cookie File\n")
            temp_cookie_file.write("# http://curl.haxx.se/rfc/cookie_spec.html\n")
            temp_cookie_file.write("# This is a generated file! Do not edit.\n\n")

            for cookie in cookies:
                # Selenium 쿠키를 Netscape 형식 문자열로 변환
                # 필수 필드: domain, include_subdomains, path, secure, expires, name, value
                domain = cookie.get('domain', '')
                include_subdomains = str(domain.startswith('.')).upper() # .example.com 이면 TRUE
                path = cookie.get('path', '/')
                secure = str(cookie.get('secure', False)).upper()
                # 만료 시간 (타임스탬프) 처리, 없으면 0
                expires = str(int(cookie.get('expiry', 0)))
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                
                if name: # 이름이 있는 쿠키만 처리
                    line = f"{domain}\t{include_subdomains}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n"
                    temp_cookie_file.write(line)
            
            temp_cookie_file.close() # 파일 쓰기 완료 후 닫기
            command.extend(['--cookies', cookie_file_path])

        except Exception as cookie_write_error:
            logger.error(f"쿠키 파일 생성 중 오류 발생: {cookie_write_error}")
            if temp_cookie_file: # 파일 객체가 생성되었으면 닫기 시도
                 try: temp_cookie_file.close() 
                 except: pass
            if cookie_file_path and os.path.exists(cookie_file_path):
                 try: os.remove(cookie_file_path) # 오류 시 임시 파일 삭제
                 except: pass
            cookie_file_path = None # 오류 발생 시 쿠키 사용 안 함

    # 최종 URL 인자 추가
    command.append(media_url)

    logger.info(f"실행할 yt-dlp 명령어: {' '.join(command)}")
    logger.info(f"출력 디렉토리: {output_dir}")

    process = None
    try:
        # yt-dlp 실행
        process = subprocess.Popen(command, cwd=output_dir)
        return_code = process.wait()

        if return_code == 0:
            logger.info("yt-dlp 다운로드 성공")
            return output_dir 
        else:
            logger.error(f"yt-dlp 실행 오류 (Return Code: {return_code})")
            logger.error("자세한 오류 내용은 위 터미널 출력을 확인하세요.")
            return None

    except FileNotFoundError:
        logger.error("'yt-dlp' 명령어를 찾을 수 없습니다...")
        return None
    except Exception as e:
        logger.error(f"yt-dlp 실행 중 예상치 못한 오류 발생: {str(e)}", exc_info=True)
        return None
    finally:
        # 임시 쿠키 파일 삭제
        if cookie_file_path and os.path.exists(cookie_file_path):
            try:
                os.remove(cookie_file_path)
                logger.info(f"임시 쿠키 파일 삭제: {cookie_file_path}")
            except Exception as clean_error:
                logger.warning(f"임시 쿠키 파일 삭제 실패: {clean_error}")

def save_media_info(media_elements, output_file='media_info.txt'):
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for media in media_elements:
                f.write(f"유형: {media['type']}\n")
                f.write(f"URL: {media['url']}\n")
                if 'alt' in media:
                    f.write(f"설명: {media['alt']}\n")
                if 'format' in media:
                    f.write(f"포맷: {media['format']}\n")
                f.write("-" * 50 + "\n")
        logger.info(f"미디어 정보가 {output_file}에 저장되었습니다")
    except Exception as e:
        logger.error(f"파일 저장 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    url = "https://javrank.com/bulalchingukkili-segpa-wonjechingusai-segpa-2v-2" # 테스트용 다른 URL
    logger.info("크롤링 프로세스 시작")
    
    # crawl_media_content 호출 및 driver 객체 유지
    driver_instance = None # driver 인스턴스를 저장할 변수
    media_elements = []
    cookies = None
    try:
        # get_driver를 여기서 호출하여 driver 인스턴스 얻기
        driver_instance = get_driver()
        if driver_instance:
             media_elements, cookies = crawl_media_content(url, driver_instance) # driver 전달
        else:
             logger.error("드라이버 초기화 실패")

        if media_elements:
            logger.info(f"총 {len(media_elements)}개의 미디어 요소를 찾았습니다")
            save_media_info(media_elements)
            
            download = input("미디어 파일을 다운로드하시겠습니까? (y/n): ").lower()
            if download == 'y':
                logger.info("다운로드 프로세스 시작")
                m3u8_url = None
                other_videos = []
                images = []
                for media in media_elements:
                    media_url_lower = media['url'].lower()
                    if media_url_lower.startswith('blob:') or media_url_lower.endswith(('.js', '.css')):
                        logger.info(f"지원하지 않는 URL 건너뜀 (초기 분류): {media['url']}")
                        continue

                    if media['type'] == '스트리밍' and (media_url_lower.endswith('.m3u8') or '.m3u8?' in media_url_lower):
                        m3u8_url = media['url']
                        logger.info(f"HLS 플레이리스트(.m3u8) 발견: {m3u8_url}")
                        break
                    elif media['type'] in ['스트리밍', '비디오'] and media_url_lower.endswith(('.mp4', '.webm', '.ts')):
                        other_videos.append(media['url'])
                    elif media['type'] == '이미지' and media_url_lower.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        images.append(media['url'])
                    else:
                        logger.info(f"처리 대상 아닌 미디어 건너뜀: {media['url']} (Type: {media['type']})")

                # 다운로드 실행 (쿠키 전달)
                downloaded_something = False
                if m3u8_url:
                    logger.info(f"HLS 스트림 다운로드 시작 (yt-dlp): {m3u8_url}")
                    result_path = download_media(m3u8_url, referer_url=url, cookies=cookies)
                    if result_path:
                        logger.info(f"HLS 스트림 다운로드 완료 (결과 폴더: {result_path})")
                        downloaded_something = True
                    else:
                        logger.error(f"HLS 스트림 다운로드 실패: {m3u8_url}")
                else:
                    logger.info("HLS(.m3u8) 플레이리스트를 찾지 못했습니다...")
                    for video_url in other_videos:
                        if video_url.lower().endswith('.ts'):
                             logger.warning(f".m3u8 없이 개별 .ts 파일 다운로드 시도 (yt-dlp): {video_url}")
                        else:
                             logger.info(f"비디오 파일 다운로드 시도 (yt-dlp): {video_url}")
                        result_path = download_media(video_url, referer_url=url, cookies=cookies)
                        if result_path:
                            logger.info(f"비디오 다운로드 완료 (결과 폴더: {result_path})")
                            downloaded_something = True
                        else:
                            logger.error(f"비디오 다운로드 실패: {video_url}")
                
                if images:
                     logger.info(f"총 {len(images)}개의 이미지 다운로드를 시작합니다.")
                     for image_url in images:
                         file_path = download_image_with_requests(image_url, referer_url=url, cookies=cookies)
                         if file_path:
                             logger.info(f"이미지 다운로드 완료: {file_path}")
                             downloaded_something = True
                         else:
                             logger.error(f"이미지 다운로드 실패: {image_url}")

                if not downloaded_something:
                     logger.warning("다운로드할 유효한 미디어를 찾지 못했거나 모든 다운로드에 실패했습니다.")

        else:
            logger.warning("미디어 요소를 찾을 수 없습니다")
            
    finally:
         # 모든 작업 완료 후 드라이버 종료
         if driver_instance:
             safe_quit_driver(driver_instance) 
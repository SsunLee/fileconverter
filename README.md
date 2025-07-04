# M3U8 to MP4 Converter

M3U8 파일을 MP4로 변환하는 Python GUI 애플리케이션입니다.

## 기능

### 🎯 주요 기능
- **단일 파일 변환**: 하나의 M3U8 파일을 MP4로 변환
- **다중 파일 변환**: 여러 M3U8 파일을 동시에 선택하여 변환
- **배치 처리**: 폴더 내 모든 M3U8 파일을 자동으로 찾아서 변환
- **실시간 진행률**: 변환 과정을 실시간으로 모니터링
- **자동 원본 삭제**: 변환 완료 후 원본 M3U8 파일 자동 삭제 옵션

### 🎨 사용자 인터페이스
- **모던한 GUI**: ttk 위젯을 사용한 깔끔한 디자인
- **직관적인 레이아웃**: 파일 선택, 설정, 진행상황, 로그 섹션으로 구분
- **실시간 피드백**: 진행률 바와 상태 표시
- **로그 시스템**: 모든 작업 내역을 실시간으로 기록

### ⚙️ 설정 옵션
- **파일명 형식 선택**:
  - 원본명_날짜시간 (예: video_2024_03_15_143045.mp4)
  - 날짜시간만 (예: 2024_03_15_143045.mp4)
- **원본 파일 삭제**: 변환 완료 후 원본 파일 자동 삭제 여부
- **로그 관리**: 로그 지우기 및 파일로 저장

## 설치 및 실행

### 필수 요구사항
- Python 3.6 이상
- FFmpeg (시스템에 설치되어 있어야 함)

### FFmpeg 설치
#### Windows
1. [FFmpeg 공식 사이트](https://ffmpeg.org/download.html)에서 다운로드
2. 압축 해제 후 bin 폴더를 시스템 PATH에 추가

#### macOS
```bash
# Homebrew 설치 (권장)
brew install ffmpeg

# 또는 MacPorts 사용
sudo port install ffmpeg

# 설치 확인
ffmpeg -version
```

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install ffmpeg
```

### 실행 방법
```bash
# Windows/Linux
python m3u8_fileto_improved.py

# macOS
python3 m3u8_fileto_improved.py
```

## macOS 사용자를 위한 추가 정보

### 시스템 요구사항
- macOS 10.14 (Mojave) 이상 권장
- Python 3.6 이상
- FFmpeg (Homebrew로 설치 권장)

### macOS 특별 기능
- **Retina 디스플레이 지원**: 고해상도 화면에서 선명한 표시
- **macOS 메뉴바 통합**: 네이티브 macOS 앱처럼 동작
- **파일 권한**: 보안 설정에서 필요한 권한 허용

### 문제 해결
1. **FFmpeg 명령어를 찾을 수 없는 경우**:
   ```bash
   # PATH 확인
   echo $PATH
   
   # FFmpeg 재설치
   brew reinstall ffmpeg
   ```

2. **Python 실행 오류**:
   ```bash
   # Python3 사용
   python3 m3u8_fileto_improved.py
   
   # 또는 가상환경 사용
   python3 -m venv venv
   source venv/bin/activate
   python m3u8_fileto_improved.py
   ```

3. **파일 권한 오류**:
   - 시스템 환경설정 > 보안 및 개인정보 보호에서 권한 허용

## 사용법

1. **파일 선택**
   - "단일 파일 선택": 하나의 M3U8 파일 선택
   - "여러 파일 선택": 여러 M3U8 파일 동시 선택
   - "폴더 선택 (배치)": 폴더 내 모든 M3U8 파일 자동 선택

2. **출력 설정**
   - "폴더 선택" 버튼으로 출력 디렉토리 지정

3. **옵션 설정**
   - 파일명 형식 선택
   - 원본 파일 삭제 여부 설정

4. **변환 실행**
   - "변환 시작" 버튼 클릭
   - 진행상황을 실시간으로 확인
   - 필요시 "변환 중지" 버튼으로 중단 가능

## 📦 실행 파일 빌드 (Build)

Python이 설치되지 않은 환경에서도 프로그램을 실행할 수 있도록 독립 실행 파일을 만들 수 있습니다.

**참고:** 안티바이러스 소프트웨어의 오탐(바이러스로 잘못 감지하는 현상)을 피하기 위해, 하나의 파일로 묶는 것보다 폴더 형태로 빌드하는 것을 권장합니다.

### 1. PyInstaller 설치
```bash
pip install pyinstaller
```

### 2. 빌드 명령어 실행 (권장 방식)

#### Windows (.exe)
터미널에서 다음 명령어를 실행하세요.
```bash
pyinstaller --windowed --name M3U8_Converter --icon=app_icon.ico m3u8_fileto_improved.py
```

#### macOS (.app)
macOS에서 다음 명령어를 실행하세요.
```bash
pyinstaller --windowed --name M3U8_Converter --icon=app_icon.icns m3u8_fileto_improved.py
```

### 3. 결과 확인 및 배포
빌드가 완료되면 `dist` 폴더 안에 **`M3U8_Converter` 폴더**가 생성됩니다.

*   **실행**: 폴더 안의 `M3U8_Converter.exe`(Windows) 또는 `M3U8_Converter.app`(macOS)을 실행하세요.
*   **배포**: 다른 사람에게 전달할 때는 **`M3U8_Converter` 폴더 전체를 압축**하여 보내야 합니다.

## 파일 구조

```
test_vi/
├── m3u8_fileto.py              # 기본 버전
├── m3u8_fileto_improved.py     # 향상된 버전 (GUI + 배치 처리)
└── README.md                   # 프로젝트 설명서
```

## 버전 정보

### v1.0 (기본 버전)
- 단일 파일 변환
- 기본 GUI (파일 선택 다이얼로그)
- 원본 파일 삭제 기능

### v2.0 (향상된 버전)
- 다중 파일 및 배치 처리
- 모던한 GUI 인터페이스
- 실시간 진행률 표시
- 로그 시스템
- 향상된 에러 처리
- 변환 중지 기능

## 기술 스택

- **Python**: 메인 프로그래밍 언어
- **Tkinter**: GUI 프레임워크
- **FFmpeg**: 비디오 변환 엔진
- **Threading**: 비동기 처리

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여

버그 리포트나 기능 제안은 이슈로 등록해 주세요.

## 변경 이력

- **2024-03-15**: v2.0 릴리스 (향상된 GUI 및 배치 처리)
- **2024-03-15**: v1.0 릴리스 (기본 기능) 
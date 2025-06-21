import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import os
import threading
from datetime import datetime
import queue
import sys
import re

class M3U8Converter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("M3U8 to MP4 Converter - 향상된 버전")
        self.root.geometry("800x800")
        self.root.resizable(True, True)
        
        # 변수 초기화
        self.selected_files = []
        self.output_directory = ""
        self.conversion_queue = queue.Queue()
        self.is_converting = False
        self.current_process = None
        
        # GUI 구성
        self.setup_gui()
        
        # 스타일 설정
        self.setup_styles()
        
        # 아이콘 설정
        try:
            icon_path = 'app_icon.ico'
            if sys.platform == "darwin": # macOS
                icon_path = 'app_icon.icns'
            
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
            else:
                self.log_message("아이콘 파일을 찾을 수 없습니다: app_icon.ico / app_icon.icns")
        except Exception as e:
            self.log_message(f"아이콘 설정 오류: {e}")
        
        # macOS 최적화
        if sys.platform == "darwin":  # macOS
            self.root.tk.call('tk', 'scaling', 2.0)  # Retina 디스플레이 지원
            # macOS 메뉴바 통합
            self.root.createcommand('tk::mac::Quit', self.root.quit)
        
    def setup_styles(self):
        """GUI 스타일 설정"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 버튼 스타일
        style.configure('Action.TButton', 
                       padding=10, 
                       font=('Arial', 10, 'bold'))
        
        # 프레임 스타일
        style.configure('Title.TLabel', 
                       font=('Arial', 12, 'bold'),
                       foreground='#2c3e50')
        
        # 프로그레스바 스타일 추가 (초록색)
        style.configure('Green.Horizontal.TProgressbar',
                       troughcolor='#f0f0f0',    # 배경 트랙 색상
                       background='#2ecc71',   # 진행 바 색상 (밝은 녹색)
                       thickness=15,           # 두께
                       borderwidth=0)          # 테두리 제거
        
    def setup_gui(self):
        """GUI 구성 요소 설정"""
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 제목
        title_label = ttk.Label(main_frame, 
                               text="M3U8 to MP4 변환기", 
                               style='Title.TLabel')
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # 파일 선택 섹션
        self.setup_file_selection(main_frame)
        
        # 출력 디렉토리 섹션
        self.setup_output_selection(main_frame)
        
        # 옵션 섹션
        self.setup_options(main_frame)
        
        # 변환 버튼
        self.setup_convert_buttons(main_frame)
        
        # 진행 상황 표시
        self.setup_progress_section(main_frame)
        
        # 로그 출력
        self.setup_log_section(main_frame)
        
        # 그리드 가중치 설정
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(6, weight=1)
        
    def setup_file_selection(self, parent):
        """파일 선택 섹션 설정"""
        # 파일 선택 프레임
        file_frame = ttk.LabelFrame(parent, text="파일 선택", padding="10")
        file_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 단일 파일 선택
        ttk.Button(file_frame, 
                  text="단일 파일 선택", 
                  command=self.select_single_file,
                  style='Action.TButton').grid(row=0, column=0, padx=(0, 10))
        
        # 여러 파일 선택
        ttk.Button(file_frame, 
                  text="여러 파일 선택", 
                  command=self.select_multiple_files,
                  style='Action.TButton').grid(row=0, column=1, padx=(0, 10))
        
        # 폴더 선택 (배치 처리)
        ttk.Button(file_frame, 
                  text="폴더 선택 (배치)", 
                  command=self.select_folder,
                  style='Action.TButton').grid(row=0, column=2)
        
        # 선택된 파일 목록
        list_frame = ttk.Frame(file_frame)
        list_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.file_listbox = tk.Listbox(list_frame, height=6)
        self.file_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.file_listbox.configure(yscrollcommand=scrollbar.set)
        
        # 파일 제거 버튼
        ttk.Button(list_frame, 
                  text="선택 항목 제거", 
                  command=self.remove_selected_file).grid(row=1, column=0, pady=(5, 0))
        
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        file_frame.columnconfigure(0, weight=1)
        
    def setup_output_selection(self, parent):
        """출력 디렉토리 선택 섹션 설정"""
        output_frame = ttk.LabelFrame(parent, text="출력 디렉토리", padding="10")
        output_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_var, state='readonly')
        self.output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Button(output_frame, 
                  text="폴더 선택", 
                  command=self.select_output_directory).grid(row=0, column=1)
        
        output_frame.columnconfigure(0, weight=1)
        
    def setup_options(self, parent):
        """옵션 설정 섹션"""
        options_frame = ttk.LabelFrame(parent, text="변환 옵션", padding="10")
        options_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 원본 파일 삭제 옵션
        self.delete_original = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, 
                       text="변환 완료 후 원본 파일 삭제", 
                       variable=self.delete_original).grid(row=0, column=0, sticky=tk.W)
        
        # 파일명 형식 옵션
        ttk.Label(options_frame, text="파일명 형식:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.filename_format = tk.StringVar(value="original_date")
        ttk.Radiobutton(options_frame, 
                       text="원본명_날짜시간", 
                       variable=self.filename_format, 
                       value="original_date").grid(row=2, column=0, sticky=tk.W)
        ttk.Radiobutton(options_frame, 
                       text="날짜시간만", 
                       variable=self.filename_format, 
                       value="date_only").grid(row=3, column=0, sticky=tk.W)
        
    def setup_convert_buttons(self, parent):
        """변환 버튼 설정"""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=4, column=0, columnspan=3, pady=(0, 10))
        
        self.convert_button = ttk.Button(button_frame, 
                                       text="변환 시작", 
                                       command=self.start_conversion,
                                       style='Action.TButton')
        self.convert_button.grid(row=0, column=0, padx=(0, 10))
        
        self.stop_button = ttk.Button(button_frame, 
                                    text="변환 중지", 
                                    command=self.stop_conversion,
                                    state='disabled',
                                    style='Action.TButton')
        self.stop_button.grid(row=0, column=1)
        
    def setup_progress_section(self, parent):
        """진행 상황 표시 섹션"""
        progress_frame = ttk.LabelFrame(parent, text="진행 상황", padding="10")
        progress_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 전체 진행률
        ttk.Label(progress_frame, text="전체 진행률:").grid(row=0, column=0, sticky=tk.W)
        self.overall_progress = ttk.Progressbar(progress_frame, mode='determinate', style='Green.Horizontal.TProgressbar')
        self.overall_progress.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        
        # 현재 파일 진행률
        ttk.Label(progress_frame, text="현재 파일:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.current_progress = ttk.Progressbar(progress_frame, mode='determinate', style='Green.Horizontal.TProgressbar')
        self.current_progress.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))
        
        # 상태 라벨
        self.status_label = ttk.Label(progress_frame, text="대기 중...")
        self.status_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))
        
        progress_frame.columnconfigure(1, weight=1)
        
    def setup_log_section(self, parent):
        """로그 출력 섹션"""
        log_frame = ttk.LabelFrame(parent, text="변환 로그", padding="10")
        log_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 로그 제어 버튼
        log_control_frame = ttk.Frame(log_frame)
        log_control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        ttk.Button(log_control_frame, 
                  text="로그 지우기", 
                  command=self.clear_log).grid(row=0, column=0)
        
        ttk.Button(log_control_frame, 
                  text="로그 저장", 
                  command=self.save_log).grid(row=0, column=1, padx=(10, 0))
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
    def log_message(self, message):
        """로그 메시지 추가"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def clear_log(self):
        """로그 지우기"""
        self.log_text.delete(1.0, tk.END)
        
    def save_log(self):
        """로그 저장"""
        log_content = self.log_text.get(1.0, tk.END)
        if log_content.strip():
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(log_content)
                    messagebox.showinfo("성공", "로그가 저장되었습니다.")
                except Exception as e:
                    messagebox.showerror("오류", f"로그 저장 중 오류가 발생했습니다: {str(e)}")
        
    def select_single_file(self):
        """단일 파일 선택"""
        file_path = filedialog.askopenfilename(
            title="M3U8 파일을 선택하세요",
            filetypes=[("M3U8 files", "*.m3u8"), ("All files", "*.*")]
        )
        if file_path:
            # 파일 경로 인코딩 처리
            try:
                file_path = os.path.abspath(file_path)
                self.selected_files = [file_path]
                self.update_file_list()
                self.log_message(f"단일 파일 선택됨: {os.path.basename(file_path)}")
            except Exception as e:
                self.log_message(f"파일 경로 처리 오류: {str(e)}")
                messagebox.showerror("오류", f"파일 경로 처리 중 오류가 발생했습니다: {str(e)}")
            
    def select_multiple_files(self):
        """여러 파일 선택"""
        file_paths = filedialog.askopenfilenames(
            title="M3U8 파일들을 선택하세요",
            filetypes=[("M3U8 files", "*.m3u8"), ("All files", "*.*")]
        )
        if file_paths:
            try:
                # 파일 경로 인코딩 처리
                valid_paths = []
                for path in file_paths:
                    abs_path = os.path.abspath(path)
                    valid_paths.append(abs_path)
                
                self.selected_files.extend(valid_paths)
                self.update_file_list()
                self.log_message(f"{len(valid_paths)}개 파일 추가됨")
            except Exception as e:
                self.log_message(f"파일 경로 처리 오류: {str(e)}")
                messagebox.showerror("오류", f"파일 경로 처리 중 오류가 발생했습니다: {str(e)}")
            
    def select_folder(self):
        """폴더 선택 (배치 처리)"""
        folder_path = filedialog.askdirectory(title="M3U8 파일이 있는 폴더를 선택하세요")
        if folder_path:
            try:
                # 폴더 경로 인코딩 처리
                abs_folder_path = os.path.abspath(folder_path)
                m3u8_files = []
                
                for root, dirs, files in os.walk(abs_folder_path):
                    for file in files:
                        if file.lower().endswith('.m3u8'):
                            file_path = os.path.join(root, file)
                            m3u8_files.append(file_path)
                
                if m3u8_files:
                    self.selected_files.extend(m3u8_files)
                    self.update_file_list()
                    self.log_message(f"폴더에서 {len(m3u8_files)}개 M3U8 파일 발견")
                else:
                    messagebox.showwarning("경고", "선택한 폴더에서 M3U8 파일을 찾을 수 없습니다.")
            except Exception as e:
                self.log_message(f"폴더 처리 오류: {str(e)}")
                messagebox.showerror("오류", f"폴더 처리 중 오류가 발생했습니다: {str(e)}")
                
    def update_file_list(self):
        """파일 목록 업데이트"""
        self.file_listbox.delete(0, tk.END)
        for file_path in self.selected_files:
            try:
                filename = os.path.basename(file_path)
                self.file_listbox.insert(tk.END, filename)
            except Exception as e:
                # 파일명 처리 오류 시 경로 전체 표시
                self.file_listbox.insert(tk.END, file_path)
                self.log_message(f"파일명 처리 오류: {str(e)}")
            
    def remove_selected_file(self):
        """선택된 파일 제거"""
        selection = self.file_listbox.curselection()
        if selection:
            try:
                index = selection[0]
                removed_file = self.selected_files.pop(index)
                self.update_file_list()
                filename = os.path.basename(removed_file)
                self.log_message(f"파일 제거됨: {filename}")
            except Exception as e:
                self.log_message(f"파일 제거 오류: {str(e)}")
            
    def select_output_directory(self):
        """출력 디렉토리 선택"""
        directory = filedialog.askdirectory(title="출력 폴더를 선택하세요")
        if directory:
            try:
                # 디렉토리 경로 인코딩 처리
                abs_directory = os.path.abspath(directory)
                self.output_directory = abs_directory
                self.output_var.set(abs_directory)
                self.log_message(f"출력 디렉토리 설정: {abs_directory}")
            except Exception as e:
                self.log_message(f"출력 디렉토리 처리 오류: {str(e)}")
                messagebox.showerror("오류", f"출력 디렉토리 처리 중 오류가 발생했습니다: {str(e)}")
            
    def start_conversion(self):
        """변환 시작"""
        if not self.selected_files:
            messagebox.showwarning("경고", "변환할 파일을 선택해주세요.")
            return
            
        if not self.output_directory:
            messagebox.showwarning("경고", "출력 디렉토리를 선택해주세요.")
            return
            
        if self.is_converting:
            messagebox.showwarning("경고", "이미 변환이 진행 중입니다.")
            return
            
        # 변환 스레드 시작
        self.is_converting = True
        self.convert_button.config(state='disabled')
        self.stop_button.config(state='normal')
        
        conversion_thread = threading.Thread(target=self.conversion_worker)
        conversion_thread.daemon = True
        conversion_thread.start()
        
    def stop_conversion(self):
        """변환 중지"""
        if self.is_converting:
            self.is_converting = False
            if self.current_process:
                try:
                    self.current_process.kill()
                    self.log_message("FFmpeg 프로세스를 중지했습니다.")
                except Exception as e:
                    self.log_message(f"FFmpeg 프로세스 중지 중 오류 발생: {e}")
        
        self.convert_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.log_message("변환이 중지되었습니다.")
        
    def conversion_worker(self):
        """변환 작업 스레드"""
        try:
            total_files = len(self.selected_files)
            successful_conversions = 0
            failed_conversions = 0
            
            self.overall_progress['maximum'] = total_files
            self.overall_progress['value'] = 0
            
            for i, m3u8_file in enumerate(self.selected_files):
                if not self.is_converting:
                    break
                    
                try:
                    # 파일명 안전하게 처리
                    safe_filename = os.path.basename(m3u8_file)
                    self.status_label.config(text=f"변환 중: {safe_filename} ({i+1}/{total_files})")
                except Exception as e:
                    self.status_label.config(text=f"변환 중: 파일 {i+1}/{total_files}")
                
                self.current_progress['value'] = 0
                
                try:
                    # 출력 파일명 생성 (인코딩 안전)
                    if self.filename_format.get() == "original_date":
                        try:
                            original_filename = os.path.splitext(os.path.basename(m3u8_file))[0]
                        except Exception:
                            original_filename = f"file_{i+1}"
                        current_time = datetime.now().strftime("%Y_%m_%d_%H%M%S")
                        output_filename = f"{original_filename}_{current_time}.mp4"
                    else:
                        current_time = datetime.now().strftime("%Y_%m_%d_%H%M%S")
                        output_filename = f"{current_time}.mp4"
                    
                    output_path = os.path.join(self.output_directory, output_filename)
                    
                    # 변환 실행
                    success = self.convert_single_file(m3u8_file, output_path)
                    
                    if success:
                        successful_conversions += 1
                        try:
                            safe_filename = os.path.basename(m3u8_file)
                            self.log_message(f"✓ 성공: {safe_filename}")
                        except Exception:
                            self.log_message(f"✓ 성공: 파일 {i+1}")
                    else:
                        failed_conversions += 1
                        try:
                            safe_filename = os.path.basename(m3u8_file)
                            self.log_message(f"✗ 실패: {safe_filename}")
                        except Exception:
                            self.log_message(f"✗ 실패: 파일 {i+1}")
                        
                except Exception as e:
                    failed_conversions += 1
                    try:
                        safe_filename = os.path.basename(m3u8_file)
                        self.log_message(f"✗ 오류: {safe_filename} - {str(e)}")
                    except Exception:
                        self.log_message(f"✗ 오류: 파일 {i+1} - {str(e)}")
                
                self.overall_progress['value'] = i + 1
                
            # 변환 완료
            self.status_label.config(text="변환 완료")
            self.log_message(f"변환 완료: 성공 {successful_conversions}개, 실패 {failed_conversions}개")
            
            if successful_conversions > 0:
                messagebox.showinfo("완료", f"변환이 완료되었습니다.\n성공: {successful_conversions}개\n실패: {failed_conversions}개")
            
        except Exception as e:
            self.log_message(f"변환 작업 중 오류 발생: {str(e)}")
            messagebox.showerror("오류", f"변환 작업 중 오류가 발생했습니다: {str(e)}")
            
        finally:
            self.is_converting = False
            self.convert_button.config(state='normal')
            self.stop_button.config(state='disabled')
            
    def convert_single_file(self, m3u8_path, output_path):
        """단일 파일 변환"""
        try:
            self.log_message(f"변환 시작: {os.path.basename(m3u8_path)}")
            
            # ffmpeg 명령어 구성
            command = [
                'ffmpeg',
                '-protocol_whitelist', 'file,http,https,tcp,tls,crypto',
                '-i', m3u8_path,
                '-c', 'copy',
                '-bsf:a', 'aac_adtstoasc',
                '-y',  # 기존 파일 덮어쓰기
                '-v', 'verbose', # 상세 로그 출력
                output_path
            ]

            # ffmpeg 실행 (인코딩 문제 해결)
            popen_args = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
                "bufsize": 1,
                "universal_newlines": True
            }
            if sys.platform == "win32":
                popen_args['encoding'] = 'utf-8'
                popen_args['errors'] = 'ignore'

            self.current_process = subprocess.Popen(command, **popen_args)
            
            duration_seconds = 0
            self.current_progress['value'] = 0
            self.root.update_idletasks()

            # 실시간 출력 처리
            for line in iter(self.current_process.stderr.readline, ''):
                if not self.is_converting:
                    break

                if "Duration:" in line and duration_seconds == 0:
                    match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
                    if match:
                        h, m, s, ms = map(int, match.groups())
                        duration_seconds = h * 3600 + m * 60 + s + ms / 100
                        self.log_message(f"영상 길이 감지: {duration_seconds:.2f}초")
                
                if "time=" in line and duration_seconds > 0:
                    match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
                    if match:
                        h, m, s, ms = map(int, match.groups())
                        current_seconds = h * 3600 + m * 60 + s + ms / 100
                        progress = (current_seconds / duration_seconds) * 100
                        self.current_progress['value'] = min(progress, 100) # 100%를 넘지 않도록
                        self.root.update_idletasks()

            return_code = self.current_process.wait()
            self.current_process = None

            if not self.is_converting:
                return False

            if return_code == 0:
                self.current_progress['value'] = 100
                self.root.update_idletasks()
                # 변환 성공 시 원본 파일 삭제
                if self.delete_original.get():
                    try:
                        os.remove(m3u8_path)
                        self.log_message(f"원본 파일 삭제됨: {os.path.basename(m3u8_path)}")
                    except Exception as e:
                        self.log_message(f"원본 파일 삭제 실패: {str(e)}")
                
                return True
            else:
                self.log_message(f"변환 실패 (종료 코드: {return_code})")
                return False
                
        except Exception as e:
            self.log_message(f"변환 중 오류: {str(e)}")
            if self.current_process:
                self.current_process.kill()
                self.current_process = None
            return False
            
    def run(self):
        """애플리케이션 실행"""
        self.log_message("M3U8 to MP4 변환기가 시작되었습니다.")
        self.root.mainloop()

if __name__ == "__main__":
    app = M3U8Converter()
    app.run()

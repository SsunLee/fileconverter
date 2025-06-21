import tkinter as tk
from tkinter import filedialog
import subprocess
import os
from datetime import datetime

def convert_m3u8_to_mp4(m3u8_path, output_path):
    try:
        print(f"입력 파일: {m3u8_path}")
        print(f"출력 파일: {output_path}")
        
        # ffmpeg를 사용하여 변환
        command = [
            'ffmpeg',
            '-protocol_whitelist', 'file,http,https,tcp,tls,crypto',
            '-i', m3u8_path,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            output_path
        ]
        
        print("실행할 명령어:", ' '.join(command))
        
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        
        print("=== 표준 출력 ===")
        print(stdout)
        print("=== 오류 출력 ===")
        print(stderr)
        
        if process.returncode == 0:
            print(f"변환이 완료되었습니다. 저장된 파일: {output_path}")
            
            # 변환 성공 시 원본 m3u8 파일 삭제
            try:
                os.remove(m3u8_path)
                print(f"원본 파일이 삭제되었습니다: {m3u8_path}")
            except Exception as delete_error:
                print(f"원본 파일 삭제 중 오류가 발생했습니다: {str(delete_error)}")
        else:
            print(f"오류가 발생했습니다. 종료 코드: {process.returncode}")
            
    except Exception as e:
        print(f"오류가 발생했습니다: {str(e)}")
        import traceback
        print(traceback.format_exc())

def select_file():
    root = tk.Tk()
    root.withdraw()  # 기본 창 숨기기
    
    # m3u8 파일 선택
    m3u8_file = filedialog.askopenfilename(
        title="m3u8 파일을 선택하세요",
        filetypes=[("m3u8 files", "*.m3u8"), ("All files", "*.*")]
    )
    
    if m3u8_file:
        print(f"선택된 m3u8 파일: {m3u8_file}")
        
        # 저장할 디렉토리 선택
        output_dir = filedialog.askdirectory(
            title="저장할 폴더를 선택하세요"
        )
        
        if output_dir:
            # 원본 파일명에서 확장자 제거
            original_filename = os.path.splitext(os.path.basename(m3u8_file))[0]
            # 현재 날짜와 시간으로 파일명 생성
            current_time = datetime.now().strftime("%Y_%m_%d_%H%M%S")
            output_file = os.path.join(output_dir, f"{original_filename}_{current_time}.mp4")
            
            print(f"선택된 출력 파일: {output_file}")
            # 변환 실행
            convert_m3u8_to_mp4(m3u8_file, output_file)
        else:
            print("출력 폴더가 선택되지 않았습니다.")
    else:
        print("입력 파일이 선택되지 않았습니다.")
    
    root.destroy()

if __name__ == "__main__":
    print("프로그램 시작")
    select_file()
    print("프로그램 종료")

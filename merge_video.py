import os
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
import subprocess

def create_timestamp_filename():
    """Create a filename with current timestamp"""
    now = datetime.now()
    return now.strftime("%Y_%m_%d_%H%M%S")

def create_file_list(input_dir, files):
    """Create a temporary file containing the list of input files"""
    list_file = os.path.join(input_dir, "file_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for file in files:
            f.write(f"file '{file}'\n")
    return list_file

def merge_tts_videos(input_dir, output_dir):
    """
    Merge multiple TTS video files into a single video file.
    
    Args:
        input_dir (str): Directory containing TTS video files
        output_dir (str): Directory for the output file
    """
    # Get all TTS files from the input directory
    video_files = [f for f in os.listdir(input_dir) if f.endswith('.tts')]
    video_files.sort()  # Sort files to ensure correct order
    
    if not video_files:
        messagebox.showwarning("경고", "입력 폴더에 TTS 파일이 없습니다!")
        return
    
    try:
        # Create output filename with timestamp
        output_file = os.path.join(output_dir, f"{create_timestamp_filename()}.mp4")
        
        # Create a file containing the list of input files
        list_file = create_file_list(input_dir, video_files)
        
        # Construct the ffmpeg command
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',
            output_file
        ]
        
        # Execute the command
        process = subprocess.run(cmd, 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE,
                              text=True)
        
        # Remove the temporary file list
        os.remove(list_file)
        
        if process.returncode == 0:
            messagebox.showinfo("완료", f"{len(video_files)}개의 TTS 파일이 성공적으로 합쳐졌습니다!\n저장 위치: {output_file}")
        else:
            messagebox.showerror("오류", f"파일을 합치는 중 오류가 발생했습니다:\n{process.stderr}")
            
    except Exception as e:
        messagebox.showerror("오류", f"파일을 합치는 중 오류가 발생했습니다: {str(e)}")

def select_folder():
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    # Select input folder
    input_dir = filedialog.askdirectory(title="TTS 파일이 있는 폴더를 선택하세요")
    if not input_dir:
        return
    
    # Select output directory
    output_dir = filedialog.askdirectory(title="저장할 폴더를 선택하세요")
    if not output_dir:
        return
    
    # Merge the files
    merge_tts_videos(input_dir, output_dir)

if __name__ == "__main__":
    select_folder()

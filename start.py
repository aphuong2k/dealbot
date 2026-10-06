"""Script khởi động đồng thời Backend FastAPI và Frontend Angular Dealbot.
Cách dùng: python start.py
Nhấn Ctrl+C để tắt đồng thời cả 2 tiến trình.
"""
import os, sys, time, subprocess, webbrowser

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BE_DIR = os.path.join(CURRENT_DIR, "dealbot")
FE_DIR = os.path.join(CURRENT_DIR, "dealbot-ui")

def main():
    print("=" * 65)
    print("       🚀 KHỞI ĐỘNG HỆ THỐNG DEALBOT STUDIO (BE + FE)")
    print("=" * 65)

    # 1. Khởi động Backend
    print("\n[1/3] Đang khởi động Backend FastAPI tại http://127.0.0.1:8000 ...")
    be_cmd = [sys.executable, "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8000", "--reload"]
    be_proc = subprocess.Popen(be_cmd, cwd=BE_DIR)

    # 2. Khởi động Frontend
    print("[2/3] Đang khởi động Frontend Angular tại http://localhost:4200 ...")
    fe_proc = subprocess.Popen("npm start", cwd=FE_DIR, shell=True)

    # 3. Mở trình duyệt
    print("[3/3] Chờ máy chủ sẵn sàng để mở trình duyệt...")
    time.sleep(5)
    webbrowser.open("http://localhost:4200")

    print("\n" + "=" * 65)
    print(" ✅ Hệ thống Dealbot Studio đã khởi chạy!")
    print(" 👉 Giao diện Frontend: http://localhost:4200")
    print(" 👉 Backend REST API  : http://127.0.0.1:8000")
    print(" 👉 Swagger Docs API  : http://127.0.0.1:8000/docs")
    print(" 💡 Nhấn Ctrl + C để tắt toàn bộ hệ thống.")
    print("=" * 65 + "\n")

    try:
        while True:
            time.sleep(1)
            # Kiểm tra nếu 1 trong 2 tiến trình bị dừng
            if be_proc.poll() is not None:
                print("⚠️ Backend API đã dừng.")
                break
            if fe_proc.poll() is not None:
                print("⚠️ Frontend UI đã dừng.")
                break
    except KeyboardInterrupt:
        print("\n🛑 Đang tắt toàn bộ tiến trình Dealbot Studio...")
    finally:
        be_proc.terminate()
        fe_proc.terminate()
        try:
            be_proc.wait(timeout=3)
            fe_proc.wait(timeout=3)
        except Exception:
            be_proc.kill()
            fe_proc.kill()
        print("✅ Đã tắt hoàn tất!")

if __name__ == "__main__":
    main()

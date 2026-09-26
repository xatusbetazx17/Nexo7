"""Desktop entry point for the bundled Python interpreter."""
import sys

if __name__ == '__main__':
    try:
        from nexo7.desktop import main
        # PyInstaller changes DLL search paths; let external Docker use its own libraries.
        if sys.platform == 'win32' and getattr(sys, 'frozen', False):
            import ctypes
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        if "--native-worker" in sys.argv:
            from nexo7.native_worker import main as worker_main
            worker_main()
        elif "--avatar-worker" in sys.argv:
            from nexo7.avatar import main as avatar_main
            avatar_main()
        elif "--voice-worker" in sys.argv:
            from nexo7.voice import worker_main
            worker_main()
        elif "--telegram" in sys.argv:
            from nexo7.telegram_bridge import main as telegram_main
            telegram_main()
        elif "--image-worker" in sys.argv:
            from nexo7.vision import worker_main
            worker_main()
        elif "--document-worker" in sys.argv:
            from nexo7.documents import worker_main
            worker_main()
        else:
            main()
    except Exception:
        import traceback
        from nexo7.desktop import data_directory
        log = data_directory() / 'startup-error.log'
        log.write_text(traceback.format_exc(), encoding='utf-8')
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'Nexo could not start or close cleanly. Details are saved in:\n'+str(log), 'Nexo 7', 0x10)
        elif sys.stderr:
            traceback.print_exc()
        sys.exit(1)

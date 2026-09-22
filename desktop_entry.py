"""Desktop entry point for the bundled Python interpreter."""
import sys

if __name__ == '__main__':
    try:
        from nexo7.desktop import main
        # PyInstaller changes DLL search paths; let external Docker use its own libraries.
        if sys.platform == 'win32' and getattr(sys, 'frozen', False):
            import ctypes
            ctypes.windll.kernel32.SetDllDirectoryW(None)
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

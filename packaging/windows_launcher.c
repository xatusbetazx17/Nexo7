/* MIT licensed. Starts the adjacent official CPython runtime without a shell. */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <wchar.h>

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR arguments, int show) {
    (void)instance; (void)previous; (void)show;
    wchar_t base[32768], python[32768], command[32768];
    DWORD count = GetModuleFileNameW(NULL, base, 32768);
    if (!count || count >= 32000) return 1;
    wchar_t *slash = wcsrchr(base, L'\\');
    if (!slash) return 1;
    *slash = 0;
    if (swprintf(python, 32768, L"%ls\\runtime\\pythonw.exe", base) < 0 ||
        swprintf(command, 32768, L"\"%ls\" \"%ls\\app\\desktop_entry.py\" %ls", python, base, arguments) < 0) {
        MessageBoxW(NULL, L"The application path or command line is too long.", L"Nexo 7", MB_OK | MB_ICONERROR);
        return 1;
    }
    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process = {0};
    startup.cb = sizeof(startup);
    if (!CreateProcessW(python, command, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, base, &startup, &process)) {
        MessageBoxW(NULL, L"Could not start the bundled Python runtime. Extract the entire archive before opening Nexo7.exe.", L"Nexo 7", MB_OK | MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD status = 1;
    GetExitCodeProcess(process.hProcess, &status);
    CloseHandle(process.hProcess);
    return (int)status;
}
